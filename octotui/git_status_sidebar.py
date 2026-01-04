from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set, FrozenSet, Iterable
import re
import tempfile
import os
import git
from dataclasses import dataclass
from datetime import datetime
import time
from collections import defaultdict

# Import for backward compatibility with existing code


@dataclass
class Hunk:
    """Represents a diff hunk with header and line information."""

    header: str
    lines: List[str]

    def __post_init__(self):
        # Remove the newline at the end of header if present
        if self.header.endswith("\n"):
            self.header = self.header[:-1]


@dataclass
class CommitInfo:
    """Represents commit information for history display."""

    sha: str
    message: str
    author: str
    date: datetime

    def __post_init__(self):
        # Remove the newline at the end of message if present
        if self.message.endswith("\n"):
            self.message = self.message[:-1]


class GitStatusSidebar:
    """Manages git repository status and file tree display."""

    def __init__(self, repo_path: Optional[str] = None):
        """Initialize the git status sidebar.

        Args:
            repo_path: Path to the git repository. If None, uses current directory.
        """
        try:
            self.repo = git.Repo(repo_path or ".", search_parent_directories=True)
            self.repo_path = Path(self.repo.working_dir)
        except git.InvalidGitRepositoryError:
            self.repo = None
            self.repo_path = Path("")
        except Exception:
            self.repo = None
            self.repo_path = Path("")

        # Cache for expensive git operations
        self._cache = {}
        self._cache_timestamps = {}
        self._cache_ttl = 5.0  # Cache TTL in seconds

        # Track which files were affected by recent operations
        self._recently_modified_files = set()

    def _get_cache_key(self, method_name: str, *args) -> str:
        """Generate cache key for method calls."""
        return f"{method_name}:{':'.join(map(str, args))}"

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache entry is still valid."""
        if cache_key not in self._cache_timestamps:
            return False
        return (time.time() - self._cache_timestamps[cache_key]) < self._cache_ttl

    def _get_cached(self, cache_key: str):
        """Get cached value if valid."""
        if self._is_cache_valid(cache_key):
            return self._cache.get(cache_key)
        return None

    def _set_cache(self, cache_key: str, value):
        """Set cache value with timestamp."""
        self._cache[cache_key] = value
        self._cache_timestamps[cache_key] = time.time()

    def _invalidate_cache(self, pattern: Optional[str] = None):
        """Invalidate cache entries matching pattern, or all if pattern is None."""
        if pattern is None:
            self._cache.clear()
            self._cache_timestamps.clear()
        else:
            keys_to_remove = [k for k in self._cache.keys() if pattern in k]
            for key in keys_to_remove:
                self._cache.pop(key, None)
                self._cache_timestamps.pop(key, None)

    def _mark_file_modified(self, file_path: str):
        """Mark a file as recently modified to optimize future updates."""
        self._recently_modified_files.add(file_path)
        # Invalidate relevant caches
        self._invalidate_cache("get_file_statuses")
        self._invalidate_cache("get_files_with_unstaged_changes")
        self._invalidate_cache("get_staged_files")
        self._invalidate_cache("get_file_tree")
        # Invalidate diff hunks for this specific file
        self._invalidate_cache(f"get_diff_hunks:{file_path}")

    def get_recently_modified_files(self) -> set:
        """Get and clear the set of recently modified files."""
        modified_files = self._recently_modified_files.copy()
        self._recently_modified_files.clear()
        return modified_files

    def has_recent_modifications(self) -> bool:
        """Check if there are any recent modifications."""
        return len(self._recently_modified_files) > 0

    def get_file_statuses(self) -> Dict[str, FrozenSet[str]]:
        """Get git status flags for files in the repository.

        Returns:
            Dictionary mapping file paths to frozen sets of git status flags.
            Flags include "staged", "modified", and "untracked".
        """
        if not self.repo:
            return {}

        cache_key = self._get_cache_key("get_file_statuses")
        cached_result = self._get_cached(cache_key)
        if cached_result is not None:
            return cached_result

        statuses: Dict[str, Set[str]] = defaultdict(set)

        try:
            # Get staged changes (index vs HEAD)
            for diff in self.repo.index.diff("HEAD"):
                statuses[diff.b_path].add("staged")

            # Get unstaged changes (working tree vs index)
            for diff in self.repo.index.diff(None):
                statuses[diff.b_path].add("modified")

            # Get untracked files
            for file_path in self.repo.untracked_files:
                statuses[file_path].add("untracked")
        except Exception:
            # Return empty dict on error, but don't cache it
            return {}

        frozen_statuses: Dict[str, FrozenSet[str]] = {
            path: frozenset(flags) for path, flags in statuses.items()
        }

        self._set_cache(cache_key, frozen_statuses)
        return frozen_statuses

    def get_staged_files(self) -> List[str]:
        """Get list of staged files in the repository.

        Returns:
            List of file paths that are staged
        """
        if not self.repo:
            return []

        cache_key = self._get_cache_key("get_staged_files")
        cached_result = self._get_cached(cache_key)
        if cached_result is not None:
            return cached_result

        try:
            staged_files = self.repo.index.diff("HEAD")
            result = [diff.b_path for diff in staged_files]
            self._set_cache(cache_key, result)
            return result
        except Exception:
            return []

    def get_unstaged_files(self) -> List[str]:
        """Get a list of unstaged (modified) files.

        Returns:
            List of file paths that are modified but not staged
        """
        if not self.repo:
            return []

        try:
            unstaged_files = self.repo.index.diff(None)
            return [diff.b_path for diff in unstaged_files]
        except Exception:
            return []

    def _resolve_primary_status(self, status_flags: Iterable[str]) -> str:
        """Pick a single status that best represents the file for tree display."""
        flags = set(status_flags)
        for candidate in ("staged", "modified", "untracked"):
            if candidate in flags:
                return candidate
        return "unchanged"

    def collect_file_data(self) -> Dict[str, any]:
        """Collect consolidated file and directory data for minimal git calls.

        Returns:
            Dict containing:
              - files: List of tuples (file_path, git_status)
              - directories: Set of directory paths
              - staged_files: List of staged file paths
              - unstaged_files: List of modified file paths
              - untracked_files: List of untracked file paths
        """
        if not self.repo:
            return {
                "files": [],
                "directories": set(),
                "staged_files": [],
                "unstaged_files": [],
                "untracked_files": [],
            }

        try:
            # Get file statuses once
            statuses = self.get_file_statuses()

            # Files from git listing
            tracked_files = self.repo.git.ls_files().splitlines()
            files = [
                (f, self._resolve_primary_status(statuses.get(f, frozenset())))
                for f in tracked_files
            ]

            # Add untracked files to list explicitly (not part of tracked files)
            untracked_files = [
                f for f, status_flags in statuses.items() if "untracked" in status_flags
            ]
            files.extend(
                [(f, "untracked") for f in untracked_files if f not in tracked_files]
            )

            # Directories via git ls-tree, more reliable than Path walk fallback
            try:
                ls_tree_dirs = self.repo.git.ls_tree(
                    "--full-tree", "-d", "--name-only", "HEAD"
                )
                directories = set(ls_tree_dirs.splitlines()) if ls_tree_dirs else set()
            except Exception:
                directories = set()

            # Always ensure .git paths excluded no matter what
            files = [(f, s) for f, s in files if ".git" not in f.split("/")]
            directories = {d for d in directories if ".git" not in d.split("/")}

            return {
                "files": files,
                "directories": directories,
                "staged_files": [
                    f for f, flags in statuses.items() if "staged" in flags
                ],
                "unstaged_files": [
                    f
                    for f, flags in statuses.items()
                    if "modified" in flags or "untracked" in flags
                ],
                "untracked_files": [
                    f for f, flags in statuses.items() if "untracked" in flags
                ],
            }
        except Exception:
            return {
                "files": [],
                "directories": set(),
                "staged_files": [],
                "unstaged_files": [],
                "untracked_files": [],
            }

    def get_file_tree(self) -> List[Tuple[str, str, str]]:
        """Get a flattened list of all files with their git status.

        Returns:
            List of tuples (file_path, file_type, git_status) where file_type is "file" or "directory"
            and git_status is "staged", "modified", "untracked", or "unchanged"
        """
        file_data = self.collect_file_data()
        file_entries = [
            (f_path, "file", status) for f_path, status in file_data["files"]
        ]
        dir_entries = [
            (d_path, "directory", "unchanged") for d_path in file_data["directories"]
        ]
        return sorted(
            file_entries + dir_entries, key=lambda x: (x[1] != "directory", x[0])
        )

    def get_diff_hunks(self, file_path: str, staged: bool = False) -> List[Hunk]:
        """Get diff hunks for a specific file.

        Args:
            file_path: Path to the file relative to repository root
            staged: Whether to get staged diff

        Returns:
            List of Hunk objects representing the diff hunks
        """
        if not self.repo:
            return []

        # Check cache first for diff hunks
        cache_key = self._get_cache_key("get_diff_hunks", file_path, staged)
        cached_result = self._get_cached(cache_key)
        if cached_result is not None:
            return cached_result

        try:
            diff_cmd = ["--", file_path]
            if staged:
                diff_cmd.insert(0, "--cached")
            diff = self.repo.git.diff(*diff_cmd)
            if not diff:
                status = self.get_file_status(file_path)
                if staged:
                    result = []
                elif status == "untracked":
                    with (self.repo_path / file_path).open("r") as f:
                        content = f.read()
                    lines = ["+" + line for line in content.splitlines()]
                    result = [Hunk("@@ -0,0 +1," + str(len(lines)) + " @@", lines)]
                elif status == "unchanged":
                    with (self.repo_path / file_path).open("r") as f:
                        content = f.read()
                    lines = content.splitlines()
                    result = [Hunk("", lines)]
                else:
                    result = []
            else:
                hunks = self._parse_diff_into_hunks(diff)
                if file_path.endswith(".md"):
                    hunks = self._filter_whitespace_hunks(hunks)
                result = hunks

            # Cache the result
            self._set_cache(cache_key, result)
            return result
        except Exception:
            return []

    def _is_whitespace_only_change(self, old_line: str, new_line: str) -> bool:
        """Check if a change is only whitespace differences.

        Args:
            old_line: The original line
            new_line: The new line

        Returns:
            True if the change is only whitespace, False otherwise
        """
        # Strip the lines to compare content
        old_stripped = old_line.strip()
        new_stripped = new_line.strip()

        # If stripped lines are identical, it's a whitespace-only change
        if old_stripped == new_stripped:
            return True

        # For markdown bullet points, check if it's just leading space differences
        # But only if the bullet type is the same
        bullet_types = ["- ", "* ", "+ "]
        for bullet in bullet_types:
            if old_stripped.startswith(bullet) and new_stripped.startswith(bullet):
                # Get the content part (without the bullet)
                old_content = old_stripped[len(bullet) :]
                new_content = new_stripped[len(bullet) :]
                return old_content == new_content

        # Not a whitespace-only change
        return False

    def _filter_whitespace_hunks(self, hunks: List[Hunk]) -> List[Hunk]:
        """Filter out hunks that contain only whitespace changes.

        Args:
            hunks: List of hunks to filter

        Returns:
            List of hunks with meaningful changes
        """
        filtered_hunks = []

        for hunk in hunks:
            # We'll implement a simple filter that removes lines where the only change is whitespace
            filtered_lines = []
            i = 0
            while i < len(hunk.lines):
                line = hunk.lines[i]

                # Handle diff lines
                if (
                    line and line[:1] == "-"
                ):  # Only check first character to avoid confusion with content starting with '-'
                    # Check if there's a corresponding addition line
                    if (
                        i + 1 < len(hunk.lines)
                        and hunk.lines[i + 1]
                        and hunk.lines[i + 1][:1] == "+"
                    ):  # Only check first character
                        next_line = hunk.lines[i + 1]

                        # Check if they're only whitespace different
                        if self._is_whitespace_only_change(
                            line[1:], next_line[1:]
                        ):  # Skip the +/- prefix
                            # Skip both lines (filter out this whitespace change)
                            i += 2
                            continue
                        else:
                            filtered_lines.append(line)
                            filtered_lines.append(next_line)
                            i += 2
                            continue
                    else:
                        filtered_lines.append(line)
                        i += 1
                elif (
                    line and line[:1] == "+"
                ):  # Only check first character to avoid confusion with content starting with '+'
                    # Check if there's a corresponding removal line
                    if (
                        i > 0 and hunk.lines[i - 1] and hunk.lines[i - 1][:1] == "-"
                    ):  # Only check first character
                        # This line was already processed with the previous line, skip it
                        i += 1
                        continue
                    else:
                        # This is an addition without a corresponding removal
                        filtered_lines.append(line)
                        i += 1
                else:
                    # Context line (unchanged)
                    filtered_lines.append(line)
                    i += 1

            # Only add hunk if it has meaningful content
            filtered_hunks.append(Hunk(header=hunk.header, lines=filtered_lines))

        return filtered_hunks

    def _parse_diff_into_hunks(self, diff: str) -> List[Hunk]:
        """Parse a unified diff string into hunks.

        Args:
            diff: Unified diff string

        Returns:
            List of Hunk objects
        """
        hunks = []
        lines = diff.splitlines()

        current_hunk_lines = []
        current_hunk_header = ""

        for line in lines:
            if line.startswith("@@"):
                # If we have a previous hunk, save it
                if current_hunk_header and current_hunk_lines:
                    hunks.append(
                        Hunk(header=current_hunk_header, lines=current_hunk_lines)
                    )
                    current_hunk_lines = []

                # Start new hunk
                current_hunk_header = line
            elif current_hunk_header:
                # Add line to current hunk
                current_hunk_lines.append(line)

        # Don't forget the last hunk
        if current_hunk_header and current_hunk_lines:
            hunks.append(Hunk(header=current_hunk_header, lines=current_hunk_lines))

        # If no hunks were found, return empty hunk
        if not hunks and lines:
            hunks.append(Hunk(header="", lines=lines))

        return hunks

    def get_file_status(self, file_path: str) -> str:
        """Get the git status of a specific file.

        Args:
            file_path: Relative path to the file

        Returns:
            Git status: "modified", "staged", "untracked", or "unchanged"
        """
        # Check staged changes first (index vs HEAD)
        try:
            diff_index = self.repo.index.diff("HEAD")
            for diff in diff_index:
                if diff.b_path == file_path:
                    return "staged"
        except Exception:
            pass

        # Check unstaged changes (working tree vs index)
        try:
            diff_working = self.repo.index.diff(None)
            for diff in diff_working:
                if diff.b_path == file_path:
                    return "modified"
        except Exception:
            pass

        # Check untracked files
        try:
            if file_path in self.repo.untracked_files:
                return "untracked"
        except Exception:
            pass

        return "unchanged"

    def stage_file(self, file_path: str) -> bool:
        """Stage a file.

        Args:
            file_path: Path to the file relative to repository root

        Returns:
            True if successful, False otherwise
        """
        if not self.repo:
            return False

        try:
            self.repo.index.add([file_path])
            return True
        except Exception:
            return False

    def unstage_file(self, file_path: str) -> bool:
        """Unstage a file from the index (remove all entries for the file from staging).

        This uses `git restore --staged` which is safer for partials.
        """
        if not self.repo:
            return False
        try:
            # Safer than index.remove for mixed states
            self.repo.git.restore("--staged", "--", file_path)
            return True
        except Exception:
            return False

    def unstage_file_all(self, file_path: str) -> bool:
        """Unstage all changes for a file using git restore --staged."""
        return self.unstage_file(file_path)

    def discard_file_changes(self, file_path: str) -> bool:
        """Discard changes to a file.

        Args:
            file_path: Path to the file relative to repository root

        Returns:
            True if successful, False otherwise
        """
        if not self.repo:
            return False

        try:
            self.repo.git.checkout("--", file_path)
            return True
        except Exception:
            return False

    def get_commit_history(self) -> List[CommitInfo]:
        """Get commit history.

        Returns:
            List of CommitInfo objects
        """
        if not self.repo:
            return []

        try:
            commits = list(self.repo.iter_commits("HEAD"))
            commit_info_list = []

            for commit in commits:
                commit_info = CommitInfo(
                    sha=commit.hexsha[:8],  # Short SHA
                    message=commit.message.strip(),
                    author=commit.author.name,
                    date=commit.committed_datetime,
                )
                commit_info_list.append(commit_info)

            return commit_info_list
        except Exception:
            return []

    def get_current_branch(self) -> str:
        """Get the current branch name.

        Returns:
            Current branch name or 'unknown' if not in a repo
        """
        if not self.repo:
            return "unknown"

        try:
            return self.repo.active_branch.name
        except Exception:
            return "unknown"

    def get_branches(self) -> list[str]:
        """Get list of all local branch names.

        Returns:
            List of branch names, sorted with current branch first
        """
        if not self.repo:
            return []

        try:
            current = self.get_current_branch()
            branches = [head.name for head in self.repo.heads]
            # Sort with current branch first
            branches.sort(key=lambda b: (b != current, b))
            return branches
        except Exception:
            return []

    def commit_staged_changes(self, message: str) -> bool:
        """Commit staged changes.

        Args:
            message: Commit message

        Returns:
            True if successful, False otherwise
        """
        if not self.repo:
            return False

        try:
            self.repo.index.commit(message)
            return True
        except Exception:
            return False

    def get_all_branches(self) -> List[str]:
        """Get all branch names in the repository.

        Returns:
            List of branch names
        """
        if not self.repo:
            return []

        try:
            # Try a simpler approach using git branch command
            branches_output = self.repo.git.branch()
            branches = [branch.strip() for branch in branches_output.split("\n")]
            # Remove the '*' marker from current branch and filter out empty lines
            branches = [
                branch.replace("*", "").strip() for branch in branches if branch.strip()
            ]
            return branches
        except Exception:
            # Fallback to the previous method
            try:
                branches = [
                    ref.name
                    for ref in self.repo.refs
                    if ref.name.startswith("refs/heads/")
                ]
                # Remove the 'refs/heads/' prefix
                branches = [branch.replace("refs/heads/", "") for branch in branches]
                return branches
            except Exception:
                return []

    def _get_remote_and_branch(self) -> Tuple[str, str]:
        """Resolve the remote/branch pair for push and pull operations."""
        if not self.repo:
            raise ValueError("Not inside a git repository")

        try:
            if self.repo.head.is_detached:
                raise ValueError("Detached HEAD state; cannot infer branch")
        except Exception:
            raise ValueError("Unable to determine HEAD state")

        active_branch = self.repo.active_branch
        tracking_branch = active_branch.tracking_branch()

        if tracking_branch is not None:
            remote_name = tracking_branch.remote_name
            branch_name = tracking_branch.remote_head or active_branch.name
        else:
            remote_name = "origin"
            if remote_name not in self.repo.remotes:
                if not self.repo.remotes:
                    raise ValueError("No remotes configured")
                remote_name = self.repo.remotes[0].name
            branch_name = active_branch.name

        return remote_name, branch_name

    def push_current_branch(self) -> Tuple[bool, str]:
        """Push the current branch to its remote tracking branch."""
        if not self.repo:
            return False, "Not inside a git repository"

        try:
            remote_name, branch_name = self._get_remote_and_branch()
            self.repo.git.push(remote_name, branch_name)
            return True, f"Pushed {branch_name} to {remote_name}"
        except ValueError as err:
            return False, str(err)
        except git.GitCommandError as err:
            return False, f"Git push failed: {err}"
        except Exception as err:
            return False, f"Unexpected push failure: {err}"

    def pull_current_branch(self) -> Tuple[bool, str]:
        """Pull the latest changes for the current branch."""
        if not self.repo:
            return False, "Not inside a git repository"

        try:
            remote_name, branch_name = self._get_remote_and_branch()
            self.repo.git.pull(remote_name, branch_name)
            return True, f"Pulled {branch_name} from {remote_name}"
        except ValueError as err:
            return False, str(err)
        except git.GitCommandError as err:
            return False, f"Git pull failed: {err}"
        except Exception as err:
            return False, f"Unexpected pull failure: {err}"

    def is_dirty(self) -> bool:
        """Check if the repository has modified or staged changes.

        Returns:
            True if repository is dirty, False otherwise
        """
        if not self.repo:
            return False

        try:
            # Check for staged changes
            if self.get_staged_files():
                return True

            # Check for unstaged changes
            if self.get_unstaged_files():
                return True

            return False
        except Exception:
            return False

    def switch_branch(self, branch_name: str) -> bool:
        """Switch to a different branch.

        Args:
            branch_name: Name of the branch to switch to

        Returns:
            True if successful, False otherwise
        """
        if not self.repo or self.is_dirty():
            return False

        try:
            self.repo.git.checkout(branch_name)
            return True
        except Exception:
            return False

    def _reverse_hunk_header(self, header: str) -> str:
        match = re.match(r"@@ -(\d+),(\d+) \+(\d+),(\d+) @@", header)
        if match:
            old_start, old_len, new_start, new_len = map(int, match.groups())
            return f"@@ -{new_start},{new_len} +{old_start},{old_len} @@"
        return header

    def _create_patch_from_hunk(
        self, file_path: str, hunk: Hunk, reverse: bool = False
    ) -> str:
        # Create a proper unified diff header
        diff_header = f"--- a/{file_path}\n+++ b/{file_path}\n"

        if reverse:
            header = self._reverse_hunk_header(hunk.header)
            reversed_lines = []
            for line in hunk.lines:
                if line.startswith("+"):
                    reversed_lines.append("-" + line[1:])
                elif line.startswith("-"):
                    reversed_lines.append("+" + line[1:])
                else:
                    reversed_lines.append(line)
            lines = [header] + reversed_lines
        else:
            lines = [hunk.header] + hunk.lines

        # Combine the diff header and hunk content
        patch_content = diff_header + "\n".join(lines) + "\n"
        return patch_content

    def _apply_patch(
        self,
        patch: str,
        cached: bool = False,
        reverse: bool = False,
        index: bool = False,
    ) -> bool:
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
            tmp.write(patch)
            tmp_path = tmp.name
        args = []
        if reverse:
            args.append("-R")
        if cached:
            args.append("--cached")
        if index:
            args.append("--index")
        args.append(tmp_path)

        try:
            self.repo.git.apply(*args)
            return True
        except git.GitCommandError as e:
            # More specific error handling for git apply
            error_msg = str(e)
            if "error: patch failed" in error_msg:
                print(f"Patch failed: {error_msg}")
            elif "error: unable to write" in error_msg:
                print(f"Unable to write patch: {error_msg}")
            else:
                print(f"Git command error applying patch: {error_msg}")
            return False
        except Exception as e:
            print(f"Unexpected error applying patch: {e}")
            return False
        finally:
            os.unlink(tmp_path)

    def stage_hunk(self, file_path: str, hunk_index: int) -> bool:
        try:
            hunks = self.get_diff_hunks(file_path, staged=False)
            if hunk_index >= len(hunks):
                return False
            hunk = hunks[hunk_index]
            patch = self._create_patch_from_hunk(file_path, hunk)
            success = self._apply_patch(patch, cached=True)
            if success:
                self._mark_file_modified(file_path)
            return success
        except Exception as e:
            print(f"Error in stage_hunk: {e}")
            return False

    def unstage_hunk(self, file_path: str, hunk_index: int) -> bool:
        try:
            hunks = self.get_diff_hunks(file_path, staged=True)
            if hunk_index >= len(hunks):
                return False
            hunk = hunks[hunk_index]
            patch = self._create_patch_from_hunk(file_path, hunk)
            success = self._apply_patch(patch, cached=True, reverse=True)
            if success:
                self._mark_file_modified(file_path)
            return success
        except Exception as e:
            print(f"Error in unstage_hunk: {e}")
            return False

    def discard_hunk(self, file_path: str, hunk_index: int) -> bool:
        try:
            hunks = self.get_diff_hunks(file_path, staged=False)
            if hunk_index >= len(hunks):
                return False
            hunk = hunks[hunk_index]
            patch = self._create_patch_from_hunk(file_path, hunk, reverse=True)
            success = self._apply_patch(patch)
            if success:
                self._mark_file_modified(file_path)
            return success
        except Exception as e:
            print(f"Error in discard_hunk: {e}")
            return False

    def stage_all_changes(self) -> Tuple[bool, str]:
        """Stage all unstaged changes in the repository.

        Returns:
            Tuple of (success, message)
        """
        if not self.repo:
            return False, "Not in a git repository"

        try:
            # Get all unstaged files (including modified, untracked, and deleted)
            unstaged_files = self.get_unstaged_files()
            untracked_files = self.repo.untracked_files

            files_to_stage = []

            # Handle regular unstaged files (modified and deleted)
            for file_path in unstaged_files:
                files_to_stage.append(file_path)

            # Handle untracked files
            for file_path in untracked_files:
                files_to_stage.append(file_path)

            if not files_to_stage:
                return True, "No changes to stage"

            # Stage all changes using git add --update for modified/deleted and git add for untracked
            if unstaged_files:
                # This handles modified and deleted files
                self.repo.git.add("--update")

            if untracked_files:
                # This handles untracked files
                self.repo.git.add("--", *untracked_files)

            # Mark all modified files as recently modified
            for file_path in files_to_stage:
                self._mark_file_modified(file_path)

            return True, f"Staged {len(files_to_stage)} files"

        except Exception as e:
            return False, f"Failed to stage all changes: {str(e)}"

    def unstage_all_changes(self) -> Tuple[bool, str]:
        """Unstage all staged changes in the repository.

        Returns:
            Tuple of (success, message)
        """
        if not self.repo:
            return False, "Not in a git repository"

        try:
            staged_files = self.get_staged_files()

            if not staged_files:
                return True, "No staged changes to unstage"

            # Use git reset to unstage all changes
            self.repo.git.reset("--")

            # Mark all modified files as recently modified
            for file_path in staged_files:
                self._mark_file_modified(file_path)

            return True, f"Unstaged {len(staged_files)} files"

        except Exception as e:
            return False, f"Failed to unstage all changes: {str(e)}"

    def get_git_status(self) -> str:
        """Get git status output as string for GAC.

        Returns:
            Git status output as string
        """
        if not self.repo:
            return ""

        try:
            return self.repo.git.status()
        except Exception:
            return ""

    def get_staged_diff(self) -> str:
        """Get staged changes diff for GAC.

        Returns:
            Staged diff as string
        """
        if not self.repo:
            return ""

        try:
            return self.repo.git.diff("--cached")
        except Exception:
            return ""

    def get_full_diff(self) -> str:
        """Get full diff (staged + unstaged) for GAC.

        Returns:
            Full diff as string
        """
        if not self.repo:
            return ""

        try:
            # Get both staged and unstaged changes
            staged_diff = self.repo.git.diff("--cached")
            unstaged_diff = self.repo.git.diff()

            if staged_diff and unstaged_diff:
                return f"# Staged changes:\n{staged_diff}\n\n# Unstaged changes:\n{unstaged_diff}"
            elif staged_diff:
                return staged_diff
            elif unstaged_diff:
                return unstaged_diff
            else:
                return ""
        except Exception:
            return ""

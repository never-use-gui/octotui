"""Actions that can be performed on commits in the graph.

This module provides implementations for interactive actions like
checkout, branch creation, merging, rebasing, etc.
"""

from typing import Optional, Tuple
import git
from textual.screen import ModalScreen
from textual.app import ComposeResult
from textual.widgets import Static, Input, Button, Label, Select
from textual.containers import Container, Vertical, Horizontal
from textual.binding import Binding

from octotui.graph_data import CommitNode


class InputModal(ModalScreen):
    """Generic modal for text input."""
    
    DEFAULT_CSS = """
    InputModal {
        align: center middle;
    }
    
    InputModal > Container {
        width: 60;
        height: auto;
        border: solid #6c7086;
        background: #1a1b26;
        padding: 2;
    }
    
    InputModal Label {
        width: 100%;
        margin: 0 0 1 0;
        color: #bb9af7;
        text-style: bold;
    }
    
    InputModal Input {
        width: 100%;
        margin: 0 0 2 0;
    }
    
    InputModal Button {
        margin: 0 1;
    }
    """
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]
    
    def __init__(self, title: str, prompt: str, default_value: str = ""):
        """Initialize input modal.
        
        Args:
            title: Modal title
            prompt: Prompt text
            default_value: Default input value
        """
        super().__init__()
        self.title = title
        self.prompt = prompt
        self.default_value = default_value
    
    def compose(self) -> ComposeResult:
        """Create modal layout."""
        with Container():
            yield Label(self.title)
            yield Label(self.prompt, classes="prompt")
            yield Input(value=self.default_value, id="modal-input")
            with Horizontal():
                yield Button("OK", id="ok-button", variant="primary")
                yield Button("Cancel", id="cancel-button")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "ok-button":
            input_widget = self.query_one("#modal-input", Input)
            self.dismiss(input_widget.value)
        else:
            self.dismiss(None)
    
    def action_cancel(self) -> None:
        """Cancel the modal."""
        self.dismiss(None)


class ConfirmModal(ModalScreen):
    """Modal for confirmation dialogs."""
    
    DEFAULT_CSS = """
    ConfirmModal {
        align: center middle;
    }
    
    ConfirmModal > Container {
        width: 60;
        height: auto;
        border: solid #6c7086;
        background: #1a1b26;
        padding: 2;
    }
    
    ConfirmModal Label {
        width: 100%;
        margin: 0 0 2 0;
        color: #c0caf5;
    }
    
    ConfirmModal .title {
        color: #bb9af7;
        text-style: bold;
        margin: 0 0 1 0;
    }
    
    ConfirmModal Button {
        margin: 0 1;
    }
    """
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]
    
    def __init__(self, title: str, message: str, confirm_text: str = "Confirm"):
        """Initialize confirmation modal.
        
        Args:
            title: Modal title
            message: Confirmation message
            confirm_text: Text for confirm button
        """
        super().__init__()
        self.title = title
        self.message = message
        self.confirm_text = confirm_text
    
    def compose(self) -> ComposeResult:
        """Create modal layout."""
        with Container():
            yield Label(self.title, classes="title")
            yield Label(self.message)
            with Horizontal():
                yield Button(self.confirm_text, id="confirm-button", variant="primary")
                yield Button("Cancel", id="cancel-button")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        self.dismiss(event.button.id == "confirm-button")
    
    def action_cancel(self) -> None:
        """Cancel the modal."""
        self.dismiss(False)


class GraphActions:
    """Handler for commit graph actions."""
    
    def __init__(self, repo: git.Repo):
        """Initialize actions handler.
        
        Args:
            repo: GitPython repository instance
        """
        self.repo = repo
    
    def checkout_commit(self, commit: CommitNode, create_branch: bool = False) -> Tuple[bool, str]:
        """Checkout a specific commit.
        
        Args:
            commit: Commit to checkout
            create_branch: Whether to create a branch at this commit
            
        Returns:
            Tuple of (success, message)
        """
        try:
            if create_branch:
                return False, "Use create_branch action to create a new branch"
            
            # Checkout the commit (detached HEAD)
            self.repo.git.checkout(commit.sha)
            return True, f"Checked out commit {commit.short_sha} (detached HEAD)"
        except git.GitCommandError as e:
            return False, f"Checkout failed: {str(e)}"
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def create_branch(self, commit: CommitNode, branch_name: str, checkout: bool = True) -> Tuple[bool, str]:
        """Create a new branch at the specified commit.
        
        Args:
            commit: Commit to create branch at
            branch_name: Name of the new branch
            checkout: Whether to checkout the new branch
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Validate branch name
            if not branch_name or not branch_name.strip():
                return False, "Branch name cannot be empty"
            
            branch_name = branch_name.strip()
            
            # Check if branch already exists
            if branch_name in [b.name for b in self.repo.branches]:
                return False, f"Branch '{branch_name}' already exists"
            
            # Create the branch
            new_branch = self.repo.create_head(branch_name, commit.sha)
            
            if checkout:
                new_branch.checkout()
                return True, f"Created and checked out branch '{branch_name}' at {commit.short_sha}"
            else:
                return True, f"Created branch '{branch_name}' at {commit.short_sha}"
        
        except git.GitCommandError as e:
            return False, f"Failed to create branch: {str(e)}"
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def delete_branch(self, branch_name: str, force: bool = False) -> Tuple[bool, str]:
        """Delete a branch.
        
        Args:
            branch_name: Name of branch to delete
            force: Force delete even if not fully merged
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Check if branch exists
            branch = None
            for b in self.repo.branches:
                if b.name == branch_name:
                    branch = b
                    break
            
            if not branch:
                return False, f"Branch '{branch_name}' not found"
            
            # Don't delete current branch
            if not self.repo.head.is_detached and self.repo.active_branch.name == branch_name:
                return False, "Cannot delete the currently checked out branch"
            
            # Delete the branch
            self.repo.delete_head(branch, force=force)
            return True, f"Deleted branch '{branch_name}'"
        
        except git.GitCommandError as e:
            return False, f"Failed to delete branch: {str(e)}"
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def merge_commit(self, commit: CommitNode, no_ff: bool = False) -> Tuple[bool, str]:
        """Merge a commit into the current branch.
        
        Args:
            commit: Commit to merge
            no_ff: Force creation of merge commit (no fast-forward)
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Check if HEAD is detached
            if self.repo.head.is_detached:
                return False, "Cannot merge while in detached HEAD state"
            
            # Perform the merge
            if no_ff:
                self.repo.git.merge(commit.sha, no_ff=True)
            else:
                self.repo.git.merge(commit.sha)
            
            return True, f"Merged {commit.short_sha} into {self.repo.active_branch.name}"
        
        except git.GitCommandError as e:
            # Check if it's a merge conflict
            if "conflict" in str(e).lower():
                return False, f"Merge conflict! Resolve conflicts and commit manually."
            return False, f"Merge failed: {str(e)}"
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def cherry_pick(self, commit: CommitNode) -> Tuple[bool, str]:
        """Cherry-pick a commit onto the current branch.
        
        Args:
            commit: Commit to cherry-pick
            
        Returns:
            Tuple of (success, message)
        """
        try:
            if self.repo.head.is_detached:
                return False, "Cannot cherry-pick while in detached HEAD state"
            
            self.repo.git.cherry_pick(commit.sha)
            return True, f"Cherry-picked {commit.short_sha}"
        
        except git.GitCommandError as e:
            if "conflict" in str(e).lower():
                return False, "Cherry-pick conflict! Resolve conflicts and commit manually."
            return False, f"Cherry-pick failed: {str(e)}"
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def revert_commit(self, commit: CommitNode) -> Tuple[bool, str]:
        """Revert a commit (create inverse commit).
        
        Args:
            commit: Commit to revert
            
        Returns:
            Tuple of (success, message)
        """
        try:
            if self.repo.head.is_detached:
                return False, "Cannot revert while in detached HEAD state"
            
            self.repo.git.revert(commit.sha, no_edit=True)
            return True, f"Reverted {commit.short_sha}"
        
        except git.GitCommandError as e:
            if "conflict" in str(e).lower():
                return False, "Revert conflict! Resolve conflicts and commit manually."
            return False, f"Revert failed: {str(e)}"
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def reset_to_commit(self, commit: CommitNode, mode: str = "mixed") -> Tuple[bool, str]:
        """Reset current branch to a commit.
        
        Args:
            commit: Commit to reset to
            mode: Reset mode ('soft', 'mixed', 'hard')
            
        Returns:
            Tuple of (success, message)
        """
        try:
            if self.repo.head.is_detached:
                return False, "Cannot reset while in detached HEAD state"
            
            valid_modes = ['soft', 'mixed', 'hard']
            if mode not in valid_modes:
                return False, f"Invalid reset mode. Must be one of: {', '.join(valid_modes)}"
            
            if mode == 'soft':
                self.repo.git.reset('--soft', commit.sha)
                msg = f"Soft reset to {commit.short_sha} (changes staged)"
            elif mode == 'mixed':
                self.repo.git.reset('--mixed', commit.sha)
                msg = f"Mixed reset to {commit.short_sha} (changes unstaged)"
            else:  # hard
                self.repo.git.reset('--hard', commit.sha)
                msg = f"Hard reset to {commit.short_sha} (changes discarded)"
            
            return True, msg
        
        except git.GitCommandError as e:
            return False, f"Reset failed: {str(e)}"
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def tag_commit(self, commit: CommitNode, tag_name: str, message: Optional[str] = None) -> Tuple[bool, str]:
        """Create a tag at the specified commit.
        
        Args:
            commit: Commit to tag
            tag_name: Name of the tag
            message: Optional tag message (creates annotated tag)
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Validate tag name
            if not tag_name or not tag_name.strip():
                return False, "Tag name cannot be empty"
            
            tag_name = tag_name.strip()
            
            # Check if tag already exists
            if tag_name in [t.name for t in self.repo.tags]:
                return False, f"Tag '{tag_name}' already exists"
            
            # Create the tag
            if message:
                self.repo.create_tag(tag_name, ref=commit.sha, message=message)
                return True, f"Created annotated tag '{tag_name}' at {commit.short_sha}"
            else:
                self.repo.create_tag(tag_name, ref=commit.sha)
                return True, f"Created lightweight tag '{tag_name}' at {commit.short_sha}"
        
        except git.GitCommandError as e:
            return False, f"Failed to create tag: {str(e)}"
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def get_commit_diff(self, commit: CommitNode) -> Optional[str]:
        """Get the diff for a commit.
        
        Args:
            commit: Commit to get diff for
            
        Returns:
            Diff string or None if error
        """
        try:
            if commit.is_initial():
                # Initial commit - show all files as added
                return self.repo.git.show(commit.sha, format="")
            else:
                # Regular commit - show diff with parent
                return self.repo.git.show(commit.sha)
        except Exception:
            return None

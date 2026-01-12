"""Layout algorithm for commit graph visualization.

This module implements the lane assignment algorithm that calculates
the visual position (lane/column) for each commit in the graph, ensuring
that parallel branches are displayed side-by-side without overlap.
"""

from typing import Dict, List, Set, Optional
from collections import defaultdict
import git
from octotui.graph_data import (
    CommitGraph, CommitNode, GraphEdge, GitRef, RefType, CommitType
)
from octotui.profiler import profile


class GraphLayoutEngine:
    """Engine for calculating commit graph layout."""
    
    def __init__(self, repo: git.Repo):
        """Initialize the layout engine.
        
        Args:
            repo: GitPython repository instance
        """
        self.repo = repo
        self.graph = CommitGraph()
        
    @profile
    def build_graph(self, max_commits: int = 100) -> CommitGraph:
        """Build the complete commit graph with layout.
        
        Args:
            max_commits: Maximum number of commits to include
            
        Returns:
            CommitGraph with calculated layout
        """
        # Step 1: Load commits from repository
        self._load_commits(max_commits)
        
        # Step 2: Load references (branches, tags)
        self._load_refs()
        
        # Step 3: Calculate layout (lane assignment)
        self._calculate_layout()
        
        # Step 4: Build edges
        self._build_edges()
        
        return self.graph
    
    @profile
    def _load_commits(self, max_commits: int) -> None:
        """Load commits from repository.

        Designed to be resilient to funky repo states (e.g. merge in progress,
        detached HEAD). Failures should degrade gracefully instead of
        exploding the whole TUI.
        """
        try:
            # Get commits in topological order. In weird states (e.g. brand-new repo
            # or corrupt refs), this may raise; we catch and fall back.
            commits = list(self.repo.iter_commits('--all', max_count=max_commits))
            
            for row, commit in enumerate(commits):
                # Build parent and child relationships
                parent_shas = [parent.hexsha for parent in commit.parents]
                
                # Determine commit type
                commit_type = CommitType.NORMAL
                if len(parent_shas) == 0:
                    commit_type = CommitType.INITIAL
                elif len(parent_shas) > 1:
                    commit_type = CommitType.MERGE
                
                # Create commit node
                node = CommitNode(
                    sha=commit.hexsha,
                    short_sha=commit.hexsha[:8],
                    message=commit.message.split('\n')[0].strip(),
                    full_message=commit.message.strip(),
                    author=commit.author.name,
                    author_email=commit.author.email,
                    committer=commit.committer.name,
                    date=commit.committed_datetime,
                    parent_shas=parent_shas,
                    commit_type=commit_type,
                    row=row,
                )
                
                self.graph.add_commit(node)
            
            # Build child relationships (reverse of parent)
            for sha, commit in self.graph.commits.items():
                for parent_sha in commit.parent_shas:
                    if parent_sha in self.graph.commits:
                        self.graph.commits[parent_sha].child_shas.append(sha)
        
        except Exception:
            # If loading fails (e.g. no commits yet), keep an empty graph.
            # Caller will render a friendly message instead of crashing.
            self.graph = self.graph or CommitGraph()
    
    @profile
    def _load_refs(self) -> None:
        """Load branches and tags from repository."""
        try:
            # Get HEAD
            try:
                head_commit = self.repo.head.commit.hexsha
                self.graph.head_sha = head_commit
            except (git.GitCommandError, ValueError, TypeError):
                head_commit = None
            
            # Get current branch
            try:
                if not self.repo.head.is_detached:
                    self.graph.current_branch = self.repo.active_branch.name
            except (git.GitCommandError, TypeError):
                pass
            
            # Load local branches
            for branch in self.repo.branches:
                ref = GitRef(
                    name=branch.name,
                    ref_type=RefType.BRANCH,
                    commit_sha=branch.commit.hexsha,
                    is_current=(branch.name == self.graph.current_branch)
                )
                self.graph.add_ref(ref)
            
            # Load remote branches
            try:
                for remote in self.repo.remotes:
                    for ref in remote.refs:
                        git_ref = GitRef(
                            name=ref.name,
                            ref_type=RefType.REMOTE_BRANCH,
                            commit_sha=ref.commit.hexsha,
                        )
                        self.graph.add_ref(git_ref)
            except (git.GitCommandError, ValueError, AttributeError):
                pass
            
            # Load tags
            try:
                for tag in self.repo.tags:
                    ref = GitRef(
                        name=tag.name,
                        ref_type=RefType.TAG,
                        commit_sha=tag.commit.hexsha,
                    )
                    self.graph.add_ref(ref)
            except (git.GitCommandError, ValueError, AttributeError):
                pass
        
        except Exception:
            # Ref loading should never be fatal to the UI.
            pass
    
    def _calculate_layout(self) -> None:
        """Calculate multi-lane graph layout based on branch topology.
        
        Implements a proper lane assignment algorithm that:
        - Assigns each branch to its own lane
        - Main branch typically stays in lane 0
        - Feature branches get adjacent lanes
        - Reuses lanes when branches merge
        - Tracks active lanes at each row for rendering
        
        The algorithm processes commits top-to-bottom (topological order):
        1. For each commit, check if a lane was reserved by a child
        2. First parent continues the same lane (main line)
        3. Additional parents (merge sources) get new lanes
        4. Track active lanes and merge sources for rendering
        """
        commits = self.graph.get_commits_in_order()
        if not commits:
            self.graph.max_lanes = 1
            return
        
        # Maps parent SHA -> list of lanes that will lead to it
        # When we encounter this parent, we assign it to the first lane
        # and mark other lanes as merge sources
        parent_lane_reservations: Dict[str, List[int]] = defaultdict(list)
        
        # Currently active lanes (have a continuous line through current row)
        active_lanes: Set[int] = set()
        
        # Try to identify main branch to keep it in lane 0
        main_branch_head = self._find_main_branch_head()
        
        def get_free_lane(preferred: Optional[int] = None) -> int:
            """Get the lowest available lane number.
            
            Args:
                preferred: Preferred lane to use if available
            
            Returns:
                Available lane number
            """
            if preferred is not None and preferred not in active_lanes:
                return preferred
            lane = 0
            while lane in active_lanes:
                lane += 1
            return lane
        
        for commit in commits:
            sha = commit.sha
            
            # Store active lanes at this row BEFORE processing (for rendering)
            # This captures the state of lanes as they appear at this row
            commit.active_lanes = active_lanes.copy()
            
            # Check if any previous commit reserved a lane for this commit
            reserved_lanes = parent_lane_reservations.get(sha, [])
            
            if reserved_lanes:
                # Use the first reserved lane (typically the "main" line)
                # Sort to prefer lower lane numbers for main line
                reserved_lanes_sorted = sorted(reserved_lanes)
                commit.lane = reserved_lanes_sorted[0]
                
                # Other reserved lanes are merge source lanes (they converge here)
                if len(reserved_lanes_sorted) > 1:
                    commit.merge_source_lanes = reserved_lanes_sorted[1:]
                    # Release the merge source lanes (they end at this commit)
                    for lane in reserved_lanes_sorted[1:]:
                        active_lanes.discard(lane)
            else:
                # New branch head - no child reserved a lane for us
                # Prefer lane 0 for main branch
                if main_branch_head and sha == main_branch_head:
                    commit.lane = get_free_lane(preferred=0)
                else:
                    commit.lane = get_free_lane()
                active_lanes.add(commit.lane)
            
            # Determine if this commit continues down (has parents in our graph)
            has_parents_in_graph = any(
                p_sha in self.graph.commits for p_sha in commit.parent_shas
            )
            commit.continues_down = has_parents_in_graph
            
            # Reserve lanes for this commit's parents
            if commit.parent_shas:
                # First parent continues in the same lane (main development line)
                first_parent = commit.parent_shas[0]
                if first_parent in self.graph.commits:
                    parent_lane_reservations[first_parent].append(commit.lane)
                
                # Additional parents (merge sources) get new lanes
                # Track these lanes ON THE MERGE COMMIT so the renderer can draw merge lines
                merge_source_lanes_for_commit = []
                for parent_sha in commit.parent_shas[1:]:
                    if parent_sha in self.graph.commits:
                        # Allocate new lane for the merge source branch
                        merge_lane = get_free_lane()
                        active_lanes.add(merge_lane)
                        parent_lane_reservations[parent_sha].append(merge_lane)
                        merge_source_lanes_for_commit.append(merge_lane)
                
                # Store merge source lanes on this commit for rendering
                if merge_source_lanes_for_commit:
                    commit.merge_source_lanes = merge_source_lanes_for_commit
            else:
                # No parents - this is an initial commit, release its lane
                active_lanes.discard(commit.lane)
            
            # Assign color based on lane for consistent branch coloring
            commit.color_index = commit.lane % len(self.graph.colors)
        
        # Calculate max lanes used
        if commits:
            self.graph.max_lanes = max(
                max(c.lane for c in commits) + 1,
                max((max(c.active_lanes) + 1 if c.active_lanes else 1) for c in commits)
            )
        else:
            self.graph.max_lanes = 1
    
    def _find_main_branch_head(self) -> Optional[str]:
        """Find the HEAD commit of the main branch (main or master).
        
        Returns:
            SHA of main branch head, or None if not found
        """
        # Look for main or master branch
        for branch_name in ['main', 'master']:
            for ref_name, ref in self.graph.refs.items():
                if ref.ref_type == RefType.BRANCH and ref.short_name() == branch_name:
                    return ref.commit_sha
        
        # Fallback: use current branch if available
        if self.graph.current_branch:
            for ref_name, ref in self.graph.refs.items():
                if ref.ref_type == RefType.BRANCH and ref.short_name() == self.graph.current_branch:
                    return ref.commit_sha
        
        # Last resort: use HEAD
        return self.graph.head_sha
    
    def _build_edges(self) -> None:
        """Build edges between commits based on parent-child relationships."""
        for commit in self.graph.commits.values():
            for parent_sha in commit.parent_shas:
                parent = self.graph.get_commit(parent_sha)
                if not parent:
                    continue
                
                # Create edge from parent to child
                edge = GraphEdge(
                    from_sha=parent.sha,
                    to_sha=commit.sha,
                    from_lane=parent.lane,
                    to_lane=commit.lane,
                    is_merge=commit.is_merge(),
                    color_index=commit.color_index,
                )
                self.graph.add_edge(edge)

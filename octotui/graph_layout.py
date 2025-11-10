"""Layout algorithm for commit graph visualization.

This module implements the lane assignment algorithm that calculates
the visual position (lane/column) for each commit in the graph, ensuring
that parallel branches are displayed side-by-side without overlap.
"""

from typing import Dict, List, Set, Optional, Tuple
from collections import deque, defaultdict
import git
from octotui.graph_data import (
    CommitGraph, CommitNode, GraphEdge, GitRef, RefType, CommitType
)


class GraphLayoutEngine:
    """Engine for calculating commit graph layout."""
    
    def __init__(self, repo: git.Repo):
        """Initialize the layout engine.
        
        Args:
            repo: GitPython repository instance
        """
        self.repo = repo
        self.graph = CommitGraph()
        
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
    
    def _load_refs(self) -> None:
        """Load branches and tags from repository."""
        try:
            # Get HEAD
            try:
                head_commit = self.repo.head.commit.hexsha
                self.graph.head_sha = head_commit
            except:
                head_commit = None
            
            # Get current branch
            try:
                if not self.repo.head.is_detached:
                    self.graph.current_branch = self.repo.active_branch.name
            except:
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
            except:
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
            except:
                pass
        
        except Exception:
            # Ref loading should never be fatal to the UI.
            pass
    
    def _calculate_layout(self) -> None:
        """Calculate simple single-column timeline layout.
        
        Creates a clean vertical timeline where each commit is in the same column,
        perfect for the requested dot-and-line visualization.
        """
        # For simple timeline, all commits go in lane 0 (single column)
        commits = self.graph.get_commits_in_order()
        
        for commit in commits:
            commit.lane = 0  # All commits in the same column
            commit.color_index = 0  # Same color for all (single branch)
        
        # Set max lanes to 1 for single column
        self.graph.max_lanes = 1
    
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


class GraphRenderer:
    """Renders the commit graph as a DAG with vertical dotted lines.
    
    This renderer creates a clean, minimalist DAG visualization showing
    parent-child relationships with vertical dotted lines and proper alignment.
    """
    
    # Graph characters for clean timeline visualization
    VERTICAL_DOTTED = "┊" # ┊ dotted vertical line for parent-child connections
    CIRCLE = "●"        # ● solid circle representing one commit
    BLANK = " "         # space for layout
    
    def __init__(self, graph: CommitGraph):
        """Initialize renderer with a graph for clean timeline visualization."""
        self.graph = graph
        self.column_spacing = 3  # Clean spacing for single column
        self._build_timeline_structure()  # Build simple timeline structure
    
    def _build_timeline_structure(self) -> None:
        """Build simple timeline structure for single-branch commit visualization.
        
        Creates a clean vertical timeline where each commit is a solid circle
        connected by dotted lines to show parent-child relationships.
        """
        # For clean timeline, we just need to ensure commits are properly ordered
        # No complex DAG structure needed for single-branch view
        pass
    
    def render_row(self, commit: CommitNode, show_details: bool = True) -> str:
        """Render a clean timeline row with circle and dotted line.
        
        Args:
            commit: Commit to render
            show_details: Whether to show commit details (message, author, etc.)
            
        Returns:
            String representation of the timeline row with proper alignment
        """
        # Build simple timeline: solid circle + dotted line + details
        circle = self.CIRCLE
        dotted_line = self.VERTICAL_DOTTED
        
        if not show_details:
            return f"{circle}"
        
        # Build commit details with proper spacing
        details_part = self._render_commit_timeline_details(commit)
        
        # Return timeline row: circle + dotted line + details
        return f"{circle} {dotted_line} {details_part}"
    
    def _render_commit_timeline_details(self, commit: CommitNode) -> str:
        """Render commit details in timeline format.
        
        Shows: SHA, message, author in a clean, aligned format.
        """
        # SHA in highlighted color
        sha_part = f"[#7dcfff]{commit.short_sha}[/#7dcfff]"
        
        # Current branch indicator if this is HEAD
        branch_indicator = ""
        for ref in commit.refs:
            if ref.is_current:
                branch_indicator = f"[bold #9ece6a]({ref.short_name()}*)[/bold #9ece6a] "
                break
        
        # Commit message (truncated if needed)
        message = commit.short_message(max_length=50)
        
        # Author name
        author_part = f"[dim] - {commit.author}[/dim]"
        
        # Combine all parts
        return f"{sha_part} {branch_indicator}{message}{author_part}"
    

    
    def _calculate_graph_width(self) -> int:
        """Calculate width needed for simple timeline (single column)."""
        # Simple timeline needs minimal width for single column
        return 1
    
    def _column_x(self, lane: int) -> int:
        """Get the X position for a given lane/column."""
        return (lane * self.column_spacing) + 2
    

    

    

"""
Git log --graph style commit graph widget for Textual TUI.

This module provides a git log --graph visualization with continuous
ASCII branch lines and properly aligned commit text.
"""

from typing import Optional, List, Dict, Set, Tuple
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static, Input, Button
from textual.containers import Horizontal, VerticalScroll
from textual.binding import Binding
import git

from octotui.graph_data import CommitGraph, CommitNode, GraphFilter
from octotui.graph_layout import GraphLayoutEngine


class GitGraphRenderer:
    """Render multi-lane commit graph with continuous branch lines.
    
    This renderer creates a GitKraken-style visualization with:
    - Multiple lanes for parallel branches
    - Continuous vertical lines for each active lane
    - Commit dots positioned in their assigned lane
    - Unicode box-drawing characters for clean visualization
    """
    
    def __init__(self, graph: 'CommitGraph' = None):
        """Initialize the renderer.
        
        Args:
            graph: CommitGraph instance for max_lanes and color palette.
                   Can be set later via set_graph().
        """
        self.graph = graph
        
        # Lane configuration
        self.LANE_WIDTH = 2  # Characters per lane
        
        # Unicode box-drawing characters for clean visualization
        self.VERTICAL_LINE = "│"     # Continuing branch line
        self.COMMIT_DOT = "●"        # Normal commit dot
        self.MERGE_DOT = "◆"         # Merge commit dot
        self.BRANCH_RIGHT = "├"      # Branch going right
        self.MERGE_LEFT = "└"        # Merge coming from left
        self.HORIZONTAL = "─"        # Horizontal line
        self.CROSS = "┼"             # Crossing lines
        self.MERGE_DOWN = "┬"        # Merge line going down
        self.SPACE = " "             # Empty space
        
        # Default color palette (used if no graph provided)
        self.default_colors = [
            "#bb9af7",  # Purple
            "#9ece6a",  # Green
            "#7dcfff",  # Blue
            "#f7768e",  # Red
            "#ff9e64",  # Orange
            "#e0af68",  # Yellow
            "#73daca",  # Cyan
            "#c0caf5",  # Light blue
        ]
        
        # Special colors
        self.merge_color = "#f38ba8"  # Red accent for merges
        
        # Legacy compatibility
        self.commit_depths = {}
        self.parent_depths = {}
        self.commits_data = {}
    
    def set_graph(self, graph: 'CommitGraph') -> None:
        """Set the commit graph for layout context.
        
        Args:
            graph: CommitGraph instance with layout information
        """
        self.graph = graph
    
    def get_color_for_lane(self, lane: int) -> str:
        """Get the color for a specific lane.
        
        Args:
            lane: Lane index (0-based)
            
        Returns:
            Hex color string for the lane
        """
        if self.graph and hasattr(self.graph, 'colors'):
            return self.graph.colors[lane % len(self.graph.colors)]
        return self.default_colors[lane % len(self.default_colors)]
    
    def get_max_lanes(self) -> int:
        """Get the maximum number of lanes in the graph.
        
        Returns:
            Maximum lane count, minimum 1
        """
        if self.graph and hasattr(self.graph, 'max_lanes'):
            return max(1, self.graph.max_lanes)
        return 1
    
    def _build_graph_columns(self, commit: CommitNode) -> str:
        """Build the multi-lane graph visualization for a commit.
        
        Creates a visual representation where:
        - Each lane is LANE_WIDTH characters wide
        - The commit dot appears in the commit's assigned lane
        - Vertical lines appear in all other active lanes
        - Merge source lanes show merge indicators
        
        Args:
            commit: The CommitNode to render
            
        Returns:
            Formatted string with Rich markup for the graph columns
            
        Example output for 3 lanes with commit in lane 1:
            │ ● │  (lane 0 has line, lane 1 has commit, lane 2 has line)
        """
        max_lanes = self.get_max_lanes()
        commit_lane = getattr(commit, 'lane', 0)
        active_lanes = getattr(commit, 'active_lanes', set())
        merge_source_lanes = getattr(commit, 'merge_source_lanes', [])
        
        # Determine commit symbol
        is_merge = commit.is_merge()
        commit_symbol = self.MERGE_DOT if is_merge else self.COMMIT_DOT
        
        # Build columns for each lane
        columns = []
        
        for lane in range(max_lanes):
            lane_color = self.get_color_for_lane(lane)
            
            if lane == commit_lane:
                # This is the commit's lane - show the commit dot
                # Use merge color accent for merge commits
                if is_merge:
                    columns.append(f"[{self.merge_color}]{commit_symbol}[/{self.merge_color}]")
                else:
                    columns.append(f"[{lane_color}]{commit_symbol}[/{lane_color}]")
            elif lane in merge_source_lanes:
                # This lane is merging into the commit
                # Show a merge indicator that curves toward the commit lane
                if lane < commit_lane:
                    # Merge from left - line ends here
                    columns.append(f"[{lane_color}]{self.MERGE_LEFT}[/{lane_color}]")
                else:
                    # Merge from right - line ends here
                    columns.append(f"[{lane_color}]{self.MERGE_LEFT}[/{lane_color}]")
            elif lane in active_lanes:
                # Active lane continues through this row
                columns.append(f"[{lane_color}]{self.VERTICAL_LINE}[/{lane_color}]")
            else:
                # Empty lane
                columns.append(self.SPACE)
        
        # Join columns with spacing for readability
        return self.SPACE.join(columns)
    
    def render_commit_line(self, commit: CommitNode, max_width: int = 80) -> str:
        """Render a commit with multi-lane graph visualization.
        
        Args:
            commit: The commit to render
            max_width: Maximum width for the entire line (default 80)
            
        Returns:
            Formatted string with multi-lane graph and commit info
        """
        try:
            # Validate commit data
            if not commit or not hasattr(commit, 'sha'):
                return "[#f38ba8]●[/#f38ba8] [#89b4fa]error[/#89b4fa] [#cdd6f4]Invalid commit data[/#cdd6f4]"
            
            # Build the graph columns (multi-lane visualization)
            try:
                graph_part = self._build_graph_columns(commit)
            except Exception:
                # Fallback to simple single-lane format
                symbol = self.MERGE_DOT if commit.is_merge() else self.COMMIT_DOT
                graph_part = f"[#89b4fa]{symbol}[/#89b4fa]"
            
            # Calculate available width for commit info
            try:
                graph_display_len = len(self._strip_markup(graph_part))
                # Account for space between graph and info
                available_width = max(20, max_width - graph_display_len - 2)
            except Exception:
                available_width = 50
            
            # Format commit info
            try:
                commit_info = self._format_commit_info(commit, available_width)
            except Exception:
                safe_sha = getattr(commit, 'short_sha', commit.sha[:8] if commit.sha else 'unknown')[:8]
                commit_info = f"[#89b4fa]{safe_sha}[/#89b4fa] [#cdd6f4]Error formatting[/#cdd6f4]"
            
            # Combine graph and commit info
            result = f"{graph_part}  {commit_info}"
            
            # Validate markup
            if not self._is_safe_markup(result):
                symbol = self.MERGE_DOT if commit.is_merge() else self.COMMIT_DOT
                safe_sha = commit.short_sha[:8] if hasattr(commit, 'short_sha') else 'unknown'
                safe_msg = commit.message[:20] if hasattr(commit, 'message') else 'Error'
                return f"[#89b4fa]{symbol}[/#89b4fa]  [#89b4fa]{safe_sha}[/#89b4fa] [#cdd6f4]{safe_msg}...[/#cdd6f4]"
            
            return result
            
        except Exception:
            # Ultimate fallback
            try:
                safe_sha = getattr(commit, 'short_sha', 'unknown')[:8]
                safe_msg = getattr(commit, 'message', 'Error')[:20]
                return f"[#89b4fa]●[/#89b4fa]  [#89b4fa]{safe_sha}[/#89b4fa] [#cdd6f4]{safe_msg}...[/#cdd6f4]"
            except:
                return "[#89b4fa]●[/#89b4fa]  [#89b4fa]error[/#89b4fa] [#cdd6f4]render error[/#cdd6f4]"
    
    def _is_safe_markup(self, text: str) -> bool:
        """Check if text contains safe Textual markup.
        
        Args:
            text: Text to validate
            
        Returns:
            True if markup appears safe
        """
        # Basic validation - check for balanced brackets
        if not text:
            return False
        
        # Count opening and closing brackets
        open_brackets = text.count('[')
        close_brackets = text.count(']')
        
        # Should have even number of brackets
        if open_brackets != close_brackets:
            return False
        
        # Check for basic markup patterns
        if '[/' in text and text.count('[/') == text.count('[') // 2:
            return True
        
        return True
    

    

    
    def reset(self) -> None:
        """Reset the renderer state for error recovery."""
        # Simple renderer has minimal state to reset
        pass
    
    def _format_commit_info(self, commit: CommitNode, max_width: int, depth: int = 0) -> str:
        """Format commit information with strict width containment.
        
        Args:
            commit: Commit to format
            max_width: Maximum width for commit info (actual display characters, not including markup)
            
        Returns:
            Formatted commit string that strictly fits within max_width
        """
        # Get safe SHA (handle potential None/empty values)
        try:
            sha_part = getattr(commit, 'short_sha', getattr(commit, 'sha', 'unknown'))[:8]
            if not sha_part or len(sha_part) == 0:
                sha_part = 'unknown'
        except Exception:
            sha_part = 'unknown'
        sha_len = len(sha_part)
        
        # Current branch indicator - truncate aggressively with error handling
        branch_part = ""
        branch_len = 0
        try:
            if hasattr(commit, 'refs') and commit.refs:
                for ref in commit.refs:
                    if hasattr(ref, 'is_current') and ref.is_current:
                        branch_name = getattr(ref, 'short_name', 'branch')
                        # Limit branch name VERY aggressively to 10 chars max
                        if len(branch_name) > 10:
                            branch_name = branch_name[:8] + "..."
                        branch_part = f"{branch_name}* "
                        branch_len = len(branch_part)
                        break
        except Exception:
            pass  # Skip branch part if any error
        
        # Author name (always limited to 6 chars) with error handling
        try:
            author = getattr(commit, 'author', 'Unknown')
            if author:
                author_short = author.split()[0][:6]
            else:
                author_short = 'Unk'
        except Exception:
            author_short = 'Unk'
        author_part = f"- {author_short}"
        author_len = len(author_part)
        
        # Calculate remaining width for message (subtract all components and spaces)
        total_fixed_len = sha_len + branch_len + author_len + (3 if branch_part else 2)  # spaces between components
        available_message_len = max_width - total_fixed_len
        
        # Ensure reasonable bounds for message
        if available_message_len < 5:
            # Not enough space, truncate other components
            available_message_len = 5
            if branch_len > 0:
                branch_part = branch_part[:max(0, branch_len - 5)]
                branch_len = len(branch_part)
                total_fixed_len = sha_len + branch_len + author_len + (3 if branch_part else 2)
                available_message_len = max_width - total_fixed_len
        
        available_message_len = min(30, max(5, available_message_len))  # Between 5-30 chars
        
        # Get safe message with error handling
        try:
            message = getattr(commit, 'message', 'No message')
            if not message:
                message = 'No message'
        except Exception:
            message = 'Error'
        
        # Truncate message to fit exactly
        if len(message) > available_message_len:
            message = message[:available_message_len - 3] + "..."
        
        # Build raw components without markup first
        raw_parts = []
        raw_parts.append(sha_part)
        if branch_part:
            raw_parts.append(branch_part)
        raw_parts.append(message)
        raw_parts.append(author_part)
        
        raw_result = ' '.join(raw_parts)
        
        # Final safety check - ensure we don't exceed width
        if len(raw_result) > max_width:
            # Emergency truncation of message
            excess = len(raw_result) - max_width
            message = message[:max(1, len(message) - excess - 3)] + "..."
            
            # Rebuild
            raw_parts = []
            raw_parts.append(sha_part)
            if branch_part:
                raw_parts.append(branch_part)
            raw_parts.append(message)
            raw_parts.append(author_part)
            raw_result = ' '.join(raw_parts)
        
        # Add markup now that we know the total size is correct
        # We need to re-add the markup to the individual parts
        parts_with_markup = []
        parts_with_markup.append(f"[#89b4fa]{sha_part}[/#89b4fa]")
        if branch_part:
            parts_with_markup.append(f"[#a6e3a1]{branch_part.rstrip()}[/#a6e3a1] ")
        parts_with_markup.append(f"[#cdd6f4]{message}[/#cdd6f4]")
        parts_with_markup.append(f"[#6C7086]{author_part}[/#6C7086]")
        
        return ''.join(parts_with_markup)
    
    def _strip_markup(self, text: str) -> str:
        """Remove Textual markup to get display length.
        
        Args:
            text: Text with markup
            
        Returns:
            Text with markup removed
        """
        try:
            import re
            if not text:
                return ''
            # Remove Textual markup [color]text[/color] patterns
            return re.sub(r'\[/?[^\]]+\]', '', text)
        except Exception:
            # Fallback to basic character count
            return text if text else ''
    
    def _calculate_commit_depth(self, commit: CommitNode) -> int:
        """Calculate the branch depth level for a commit.
        
        Args:
            commit: Commit to analyze
            
        Returns:
            Integer depth level (0 = main branch, higher = deeper branches)
        """
        # Use memoization to avoid recalculating
        if commit.sha in self.commit_depths:
            return self.commit_depths[commit.sha]
        
        # Initial commit has depth 0
        if len(commit.parent_shas) == 0:
            self.commit_depths[commit.sha] = 0
            return 0
        
        # Get parent depth
        parent_depth = self._calculate_depth_for_sha(commit.parent_shas[0])
        
        # Check if this commit branches from the main lineage
        # A commit is considered a branch if it has siblings (other commits with same parent)
        is_branch_commit = self._is_branch_commit(commit, parent_depth)
        
        if is_branch_commit:
            # This is a branch - increase depth from its parent
            depth = parent_depth + 1
        else:
            # Follow parent's depth
            depth = parent_depth
        
        # Special case: merge commits should return to depth 0 (main line)
        if commit.is_merge():
            depth = 0  # Merge commits typically bring branches back to main
        
        self.commit_depths[commit.sha] = depth
        return depth
    
    def _is_branch_commit(self, commit: CommitNode, parent_depth: int) -> bool:
        """Determine if this commit represents a branch point.
        
        Args:
            commit: Commit to analyze
            parent_depth: Depth of the parent commit
            
        Returns:
            True if this commit is a branch off the main lineage
        """
        # If parent has multiple children, this could be a branch
        if hasattr(self, 'commits_data'):
            parent_sha = commit.parent_shas[0] if commit.parent_shas else None
            if parent_sha and parent_sha in self.commits_data:
                parent_commit = self.commits_data[parent_sha]
                
                # Count children at parent's depth
                same_depth_children = 0
                for child_sha in parent_commit.child_shas:
                    if child_sha != commit.sha and child_sha in self.commits_data:
                        child_commit = self.commits_data[child_sha]
                        # If we haven't calculated child depth yet, assume it could be main
                        child_depth = self.commit_depths.get(child_sha, 0)
                        if child_depth == parent_depth:
                            same_depth_children += 1
                
                # If there are other children at the same depth (main line), this is a branch
                if same_depth_children > 0:
                    return True
        
        # Heuristic: if parent has >1 child, this might be a branch
        if len(commit.parent_shas) > 0 and hasattr(self, 'commits_data'):
            parent_sha = commit.parent_shas[0]
            if parent_sha in self.commits_data:
                parent_commit = self.commits_data[parent_sha]
                return len(parent_commit.child_shas) > 1
        
        return False
    
    def _calculate_depth_for_sha(self, parent_sha: str) -> int:
        """Helper to calculate depth for a commit by SHA.
        
        Args:
            parent_sha: SHA of parent commit
            
        Returns:
            Depth level of the parent commit
        """
        # Check if we already calculated this depth
        if parent_sha in self.commit_depths:
            return self.commit_depths[parent_sha]
        
        # Try to get from commits data if available
        if hasattr(self, 'commits_data') and parent_sha in self.commits_data:
            parent_commit = self.commits_data[parent_sha]
            return self._calculate_commit_depth(parent_commit)
        
        # If not found, assume main branch (conservative default)
        return 0
    
    def set_depth_from_graph_data(self, commits: Dict[str, CommitNode]) -> None:
        """Set up depth calculations from complete commit graph.
        
        Args:
            commits: Dictionary of all commits (sha -> CommitNode)
        """
        self.commits_data = commits
        # Pre-calculate all depths
        for commit in commits.values():
            self._calculate_commit_depth(commit)
    

    



class CommitGraphLine(Static):
    """A single line in the commit graph."""

    DEFAULT_CSS = """
    CommitGraphLine {
        width: 100%;
        height: auto;
        padding: 0 1;
        margin: 0;
        background: transparent;
        overflow: hidden;
        color: #cdd6f4;
    }
    
    CommitGraphLine:hover {
        background: #1a1b26;
    }
    """

    def __init__(self, commit: CommitNode, content: str, **kwargs):
        """Initialize a commit graph line.
        
        Args:
            commit: Commit object (may be None)
            content: Formatted content string
        """
        try:
            # Validate content before passing to parent
            if not content:
                content = "[#89b4fa]● │[/#89b4fa] [#89b4fa]error[/#89b4fa] [#cdd6f4]no content[/#cdd6f4]"
            
            super().__init__(content, **kwargs)
            self.commit = commit
        except Exception as e:
            # Ultimate fallback - create a simple static widget
            try:
                super().__init__("[#89b4fa]● │[/#89b4fa] [#89b4fa]error[/#89b4fa] [#cdd6f4]display error[/#cdd6f4]", **kwargs)
            except:
                # If even the fallback fails, create without markup
                super().__init__("● │ error display error", **kwargs)
            
            self.commit = commit


class CommitGraphWidget(Widget):
    """Git log --graph style commit graph widget."""
    
    DEFAULT_CSS = """
    CommitGraphWidget {
        width: 100%;
        height: 100%;
        background: transparent;
        layout: vertical;
    }
    
    CommitGraphWidget #graph-toolbar {
        width: 100%;
        height: auto;
        border: solid #6c7086;
        background: transparent;
        padding: 1;
        margin: 0 0 1 0;
    }
    
    CommitGraphWidget #graph-search {
        width: 1fr;
        height: 3;
        border: solid #6c7086;
        background: transparent;
        margin: 0 1 0 0;
    }
    
    CommitGraphWidget #graph-scroll {
        width: 100%;
        height: 1fr;
        border: solid #6c7086;
        background: transparent;
        overflow-y: auto;
    }
    
    CommitGraphWidget Button {
        margin: 0 1;
        height: 3;
    }
    """
    
    BINDINGS = [
        Binding("/", "focus_search", "Search", show=True),
        Binding("f", "toggle_filter", "Filter", show=True),
    ]

    def __init__(self, repo: git.Repo, max_commits: int = 100):
        """Initialize the commit graph widget.
        
        Args:
            repo: GitPython repository instance
            max_commits: Maximum number of commits to display
        """
        super().__init__()
        self.repo = repo
        self.max_commits = max_commits
        self.graph: Optional[CommitGraph] = None
        self.renderer: Optional[GitGraphRenderer] = None
        self.filter = GraphFilter(max_commits=max_commits)
    
    def compose(self) -> ComposeResult:
        """Create the widget layout."""
        with Horizontal(id="graph-toolbar"):
            yield Input(placeholder="Search commits...", id="graph-search")
            yield Button("Refresh", id="refresh-graph")
        
        yield VerticalScroll(id="graph-scroll")
    
    def on_mount(self) -> None:
        """Initialize the graph when mounted."""
        self.refresh_graph()
    
    def refresh_graph(self) -> None:
        """Refresh the commit graph from the repository."""
        try:
            # Build the graph using layout engine
            layout_engine = GraphLayoutEngine(self.repo)
            self.graph = layout_engine.build_graph(max_commits=self.max_commits)
            
            # Initialize renderer with graph context for multi-lane rendering
            self.renderer = GitGraphRenderer(graph=self.graph)
            
            # Render the graph
            self._render_graph()
        except Exception as e:
            # Show detailed error if graph building fails
            import traceback
            error_msg = f"Error loading commit graph: {str(e)}"
            self.notify(error_msg, severity="error")
            
            scroll = self.query_one("#graph-scroll", VerticalScroll)
            if scroll:
                scroll.remove_children()
                scroll.mount(Static(f"{error_msg}\n\n{traceback.format_exc()}", classes="error"))
    
    def _render_graph(self) -> None:
        """Render the graph to the scroll container."""
        if not self.graph:
            return
        
        try:
            scroll = self.query_one("#graph-scroll", VerticalScroll)
            scroll.remove_children()
            
            # Filter commits
            commits = self.graph.get_commits_in_order()
            filtered_commits = [c for c in commits if self.filter.matches(c)]
            
            if not filtered_commits:
                scroll.mount(Static("No commits match the filter", classes="info"))
                return
            
            # Create fresh renderer with graph context for multi-lane rendering
            self.renderer = GitGraphRenderer(graph=self.graph)
            
            # Also set up legacy depth calculations for backwards compatibility
            try:
                if hasattr(self.graph, 'commits') and self.graph.commits:
                    self.renderer.set_depth_from_graph_data(self.graph.commits)
            except Exception:
                # Continue without depth calculations if it fails
                pass
            
            # Render commits in order (newest to oldest)
            for commit in filtered_commits[:self.filter.max_commits]:
                try:
                    # First validate commit has minimal required data
                    if not commit or not hasattr(commit, 'sha'):
                        scroll.mount(Static("[#f38ba8]● │[/#f38ba8] [#89b4fa]error[/#89b4fa] [#cdd6f4]Invalid commit data[/#cdd6f4]", classes="error"))
                        continue
                    
                    content = self.renderer.render_commit_line(commit)
                    line = CommitGraphLine(commit, content)
                    scroll.mount(line)
                except Exception as line_error:
                    # Get safe commit ID for error message
                    try:
                        safe_sha = getattr(commit, 'short_sha', getattr(commit, 'sha', 'unknown'))[:8]
                        if not safe_sha:
                            safe_sha = 'unknown'
                    except:
                        safe_sha = 'unknown'
                    
                    # Show error but don't crash
                    error_content = f"[#f38ba8]● │[/#f38ba8] [#89b4fa]{safe_sha}[/#89b4fa] [#cdd6f4]render error[/#cdd6f4]"
                    try:
                        error_line = CommitGraphLine(commit, error_content)
                        scroll.mount(error_line)
                    except Exception:
                        # Ultimate fallback - just show static error
                        scroll.mount(Static(error_content, classes="error"))
                    
                    # Reset renderer on error to prevent cascading failures
                    if hasattr(self.renderer, 'reset'):
                        self.renderer.reset()
                    else:
                        self.renderer = GitGraphRenderer()
        
        except Exception as e:
            self.notify(f"Error rendering graph: {e}", severity="error")
            if 'scroll' in locals() and scroll:
                scroll.mount(Static(f"Render error: {e}", classes="error"))
    
    def action_focus_search(self) -> None:
        """Focus the search input."""
        search = self.query_one("#graph-search", Input)
        search.focus()
    
    def action_toggle_filter(self) -> None:
        """Toggle filter options (placeholder for future enhancement)."""
        # TODO: Implement filter dialog
        pass
    
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        if event.input.id == "graph-search":
            self.filter.search_text = event.value if event.value else None
            self._render_graph()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "refresh-graph":
            self.refresh_graph()
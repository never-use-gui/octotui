"""
Git log --graph style commit graph widget for Textual TUI.

This module provides a git log --graph visualization with continuous
ASCII branch lines and properly aligned commit text.
"""

from typing import Optional
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static, Input, Button
from textual.containers import Horizontal, VerticalScroll
from textual.binding import Binding
import git

from octotui.graph_data import CommitGraph, CommitNode, GraphFilter
from octotui.graph_layout import GraphLayoutEngine


class GitGraphRenderer:
    """Render clean single-line commit graph with lane-based branch colors."""
    
    def __init__(self):
        # Graph characters for clean single-line visualization
        self.VERTICAL_LINE = "│"     # Clean vertical line
        self.COMMIT_DOT = "●"        # Solid circle for commits
        self.MERGE_DOT = "◆"         # Diamond for merge commits
        self.BRANCH_CHAR = "├─"     # Branch indicator
        self.MERGE_CHAR = "└─"      # Merge indicator
        self.SPACE = " "             # Space character
        
        # Lane-based color palette (matches graph_data.py colors)
        # Each lane gets a consistent color throughout its lifetime
        self.lane_colors = [
            "#bb9af7",  # Purple (lane 0 - typically main branch)
            "#9ece6a",  # Green
            "#7dcfff",  # Blue
            "#f7768e",  # Red
            "#ff9e64",  # Orange
            "#e0af68",  # Yellow
            "#73daca",  # Cyan
            "#c0caf5",  # Light blue
        ]
        
        # Special color for merge commits (diamond)
        self.merge_color = "#f38ba8"  # Red for merge diamonds
    
    def _get_lane_color(self, lane: int) -> str:
        """Get color for a specific lane.
        
        Each lane maintains a consistent color throughout the graph,
        wrapping around the palette if there are more lanes than colors.
        
        Args:
            lane: Lane index (0-based)
            
        Returns:
            Hex color string for the lane
        """
        return self.lane_colors[lane % len(self.lane_colors)]
    
    def render_commit_line(self, commit: CommitNode, max_width: int = 80) -> str:
        """Render a clean single-line commit visualization with lane-based colors.
        
        Args:
            commit: The commit to render
            max_width: Maximum width for the line (default 80 for better containment)
            
        Returns:
            Formatted string with lane-colored timeline visualization
            
        Note: Includes comprehensive error handling to prevent stylesheet errors
        """
        try:
            # Validate commit data
            if not commit or not hasattr(commit, 'sha'):
                return "[error] Invalid commit data"
            
            # Get lane from commit (set by layout algorithm)
            lane = getattr(commit, 'lane', 0)
            
            # Determine commit type and corresponding symbol
            commit_symbol = self.MERGE_DOT if commit.is_merge() else self.COMMIT_DOT
            
            # Get color based on lane (merge commits keep lane color for consistency)
            lane_color = self._get_lane_color(lane)
            
            # Build graph part with lane-based coloring
            try:
                graph_part = self._build_lane_graph_part(commit, lane, commit_symbol, lane_color)
            except Exception:
                # Fallback to simple format if graph part fails
                graph_part = f"[{lane_color}]{commit_symbol} │[/{lane_color}]"
            
            # Calculate available width for commit info
            try:
                graph_part_display_len = len(self._strip_markup(graph_part))
                available_width = max(20, max_width - graph_part_display_len)  # Minimum 20 chars
            except Exception:
                available_width = 60  # Safe fallback
            
            # Format commit info with lane color for SHA
            try:
                commit_info = self._format_commit_info(commit, available_width, lane, lane_color)
            except Exception:
                # Fallback to simple format if commit info fails
                safe_sha = getattr(commit, 'short_sha', commit.sha[:8])[:8]
                commit_info = f"[{lane_color}]{safe_sha}[/{lane_color}] [#cdd6f4]Error formatting[/#cdd6f4]"
            
            # Final result with validation
            result = f"{graph_part} {commit_info}"
            
            # Validate result doesn't contain problematic characters
            if not self._is_safe_markup(result):
                return f"[{lane_color}]{commit_symbol} │[/{lane_color}] [{lane_color}]{commit.short_sha[:8]}[/{lane_color}] [#cdd6f4]{commit.message[:20]}...[/#cdd6f4]"
            
            return result
            
        except Exception:
            # Ultimate fallback
            try:
                safe_sha = getattr(commit, 'short_sha', getattr(commit, 'sha', 'unknown')[:8])[:8]
                safe_msg = getattr(commit, 'message', 'Error rendering')[:20]
                fallback_color = self.lane_colors[0]
                return f"[{fallback_color}]● │[/{fallback_color}] [{fallback_color}]{safe_sha}[/{fallback_color}] [#cdd6f4]{safe_msg}...[/#cdd6f4]"
            except Exception:
                return "[#bb9af7]● │[/#bb9af7] [#bb9af7]error[/#bb9af7] [#cdd6f4]render error[/#cdd6f4]"
    
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
    
    def _build_lane_graph_part(self, commit: CommitNode, lane: int, symbol: str, color: str) -> str:
        """Build the graph part with lane-based coloring.
        
        Args:
            commit: Commit being rendered
            lane: Lane index for this commit
            symbol: Commit symbol (● or ◆)
            color: Color for this commit's lane
            
        Returns:
            Formatted graph part with lane coloring
        """
        try:
            # Validate inputs
            if not color or not color.startswith('#'):
                color = self.lane_colors[0]  # Fallback to first color
            
            if not symbol or symbol not in [self.COMMIT_DOT, self.MERGE_DOT]:
                symbol = self.COMMIT_DOT
            
            lane = max(0, lane)  # Ensure non-negative
            
            # Use merge color for merge diamonds to make them stand out
            if commit and commit.is_merge():
                symbol_color = self.merge_color
            else:
                symbol_color = color
            
            if lane == 0:
                # Main line (lane 0) - simple clean format
                return f"[{symbol_color}]{symbol}[/{symbol_color}] [{color}]{self.VERTICAL_LINE}[/{color}]"
            else:
                # Feature branches - show lane indicator
                if commit and commit.is_merge():
                    return f"[{symbol_color}]{symbol}[/{symbol_color}] [{color}]{self.MERGE_CHAR}L{min(lane, 9)}[/{color}]"
                else:
                    return f"[{symbol_color}]{symbol}[/{symbol_color}] [{color}]{self.BRANCH_CHAR}L{min(lane, 9)}[/{color}]"
                    
        except Exception:
            # Fallback to simple format
            return f"[{self.lane_colors[0]}]{self.COMMIT_DOT} │[/{self.lane_colors[0]}]"
    

    
    def reset(self) -> None:
        """Reset the renderer state for error recovery."""
        # Simple renderer has minimal state to reset
        pass
    
    def _format_commit_info(self, commit: CommitNode, max_width: int, lane: int = 0, lane_color: str = None) -> str:
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
        # Use lane color for SHA to maintain visual consistency
        sha_color = lane_color if lane_color else self.lane_colors[0]
        
        parts_with_markup = []
        parts_with_markup.append(f"[{sha_color}]{sha_part}[/{sha_color}]")
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
        except Exception:
            # Ultimate fallback - create a simple static widget
            try:
                super().__init__("[#89b4fa]● │[/#89b4fa] [#89b4fa]error[/#89b4fa] [#cdd6f4]display error[/#cdd6f4]", **kwargs)
            except Exception:
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
            
            # Initialize fresh renderer
            self.renderer = GitGraphRenderer()
            
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
            
            # Create fresh renderer for each render
            self.renderer = GitGraphRenderer()
            
            # Render commits in order (newest to oldest)
            # Lane info is already set by the layout algorithm in graph_layout.py
            for commit in filtered_commits[:self.filter.max_commits]:
                try:
                    # First validate commit has minimal required data
                    if not commit or not hasattr(commit, 'sha'):
                        scroll.mount(Static("[#f38ba8]● │[/#f38ba8] [#89b4fa]error[/#89b4fa] [#cdd6f4]Invalid commit data[/#cdd6f4]", classes="error"))
                        continue
                    
                    content = self.renderer.render_commit_line(commit)
                    line = CommitGraphLine(commit, content)
                    scroll.mount(line)
                except Exception:
                    # Get safe commit ID for error message
                    try:
                        safe_sha = getattr(commit, 'short_sha', getattr(commit, 'sha', 'unknown'))[:8]
                        if not safe_sha:
                            safe_sha = 'unknown'
                    except Exception:
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
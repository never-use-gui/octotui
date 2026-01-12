"""
Git log --graph style commit graph widget for Textual TUI.

This module provides a git log --graph visualization with continuous
ASCII branch lines and properly aligned commit text.
"""

from typing import Optional, Dict
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static, Input, Button
from textual.containers import Horizontal, VerticalScroll
from textual.binding import Binding
import git

from octotui.graph_data import CommitGraph, CommitNode, GraphFilter
from octotui.graph_layout import GraphLayoutEngine


class GitGraphRenderer:
    """Render clean single-line commit graph with branch depth indicators."""
    
    def __init__(self, graph: 'CommitGraph' = None):
        """Initialize the renderer.
        
        Args:
            graph: Optional CommitGraph for multi-lane rendering context
        """
        # Graph context for multi-lane rendering
        self.graph = graph
        
        # Depth and hierarchy tracking
        self.commit_depths = {}  # sha -> depth level
        self.parent_depths = {}  # sha -> parent depth for calculations
        
        # Single-line with depth notation
        self.line_color = "#89b4fa"  # Blue for the main timeline
        
        # Graph characters for clean single-line visualization with depth
        self.VERTICAL_LINE = "│"     # Clean vertical line
        self.COMMIT_DOT = "●"        # Solid circle for commits
        self.MERGE_DOT = "◆"         # Diamond for merge commits
        self.BRANCH_CHAR = "├─"     # Branch indicator
        self.MERGE_CHAR = "╰─"      # Curved merge indicator
        self.MAIN_LINE = "──"        # Main timeline indicator
        self.SPACE = " "             # Space character
        
        # Multi-lane merge visualization characters (curved for smoother look)
        self.MERGE_LEFT = "╮"        # Curved merge line coming from right (vertical on right connects down)
        self.MERGE_RIGHT = "╭"       # Curved merge line coming from left (vertical on left connects down)
        self.CURVE_TOP_LEFT = "╭"    # Curved top-left (branch start)
        self.CURVE_TOP_RIGHT = "╮"   # Curved top-right (branch start)
        self.HORIZONTAL = "─"        # Horizontal merge line
        self.CROSS = "┼"             # Crossing lines
        self.BRANCH_DOWN = "┬"       # Branch going down
        self.MERGE_UP = "┴"          # Merge going up
        self.DIAGONAL_RIGHT = "╱"    # Diagonal up-right
        self.DIAGONAL_LEFT = "╲"     # Diagonal down-right
        
        # T-junction characters for GitKraken-style grouped rails
        self.T_UP = "┴"              # T-junction, vertical goes up (used at fork rail)
        self.T_DOWN = "┬"            # T-junction, vertical goes down
        self.T_LEFT = "┤"            # T-junction, horizontal goes left (rail end)
        self.T_RIGHT = "├"           # T-junction, horizontal goes right (rail start)
        self.CORNER_TOP_RIGHT = "┐"  # Corner for rail end
        self.CORNER_TOP_LEFT = "┌"   # Corner for rail start
        self.CORNER_BOTTOM_RIGHT = "┘"  # Corner for rail end (opening upward)
        
        # Depth-based colors
        self.depth_colors = [
            "#89b4fa",  # L0: Blue (main)
            "#a6e3a1",  # L1: Green (first branch level)
            "#f9e2af",  # L2: Yellow (second branch level)
            "#cba6f7",  # L3: Purple (third branch level)
            "#94e2d5",  # L4+: Cyan (deeper levels)
        ]
        
        # Default lane colors (matching graph palette)
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
        self.merge_color = "#f38ba8"  # Red for merges
        
        # HEAD indicator - VERY VISIBLE!
        self.HEAD_INDICATOR = "➤"  # Distinctive pointer symbol
        self.HEAD_COLOR = "#a6e3a1"  # Bright green for maximum visibility
    
    def set_graph(self, graph: 'CommitGraph') -> None:
        """Set the graph for multi-lane rendering.
        
        Args:
            graph: CommitGraph to use for rendering context
        """
        self.graph = graph
    
    def get_max_lanes(self) -> int:
        """Get the maximum number of lanes in the graph.
        
        Returns:
            Maximum lane count, defaults to 1 if no graph
        """
        if self.graph is not None:
            return max(1, self.graph.max_lanes)
        return 1
    
    def get_color_for_lane(self, lane: int) -> str:
        """Get color for a specific lane.
        
        Args:
            lane: Lane number
            
        Returns:
            Color hex string for this lane
        """
        if self.graph is not None and hasattr(self.graph, 'colors'):
            return self.graph.colors[lane % len(self.graph.colors)]
        return self.default_colors[lane % len(self.default_colors)]
    
    def _is_head_commit(self, commit: 'CommitNode') -> bool:
        """Check if this commit is the current HEAD.
        
        Determines if any ref attached to this commit is marked as current,
        indicating this is the HEAD commit (where we're currently checked out).
        
        Args:
            commit: The commit to check
            
        Returns:
            True if this commit is HEAD, False otherwise
        """
        try:
            refs = getattr(commit, 'refs', [])
            if not refs:
                return False
            for ref in refs:
                if getattr(ref, 'is_current', False):
                    return True
            return False
        except Exception:
            return False
    
    def _build_graph_columns(self, commit: CommitNode) -> str:
        """Build the graph column visualization for multi-lane rendering.
        
        Creates a visual representation of the graph lanes at this commit's row,
        showing:
        - Commit dot (● or ◆) in the commit's lane
        - Vertical lines (│) for active lanes
        - Merge indicators (└─) for lanes merging into this commit
        - Branch-out indicators (─╮) when a branch starts from a parent on a different lane
        
        Args:
            commit: The commit node to render
            
        Returns:
            Formatted string with colored graph columns
            
        Example outputs:
            "● │ │"  - Commit in lane 0, active lanes 1 and 2
            "│ ◆─┘"  - Merge commit in lane 1, merge from lane 2
            "│ │ ●"  - Commit in lane 2, active lanes 0 and 1
            "├─● │"  - Branch-out commit in lane 1, branching from lane 0
        """
        try:
            max_lanes = self.get_max_lanes()
            commit_lane = getattr(commit, 'lane', 0)
            active_lanes = getattr(commit, 'active_lanes', set())
            merge_source_lanes = getattr(commit, 'merge_source_lanes', [])
            
            # Determine commit symbol - HEAD gets special treatment!
            is_merge = commit.is_merge() if hasattr(commit, 'is_merge') else len(getattr(commit, 'parent_shas', [])) > 1
            is_head = self._is_head_commit(commit)
            
            if is_head:
                # HEAD commit gets VERY VISIBLE indicator
                commit_symbol = self.HEAD_INDICATOR
            elif is_merge:
                commit_symbol = self.MERGE_DOT
            else:
                commit_symbol = self.COMMIT_DOT
            
            # Detect branch-out: when commit's parent is on a different lane
            # This indicates a branch starting point (not a merge)
            # 
            # GitKraken-style: If parent is a fork point, suppress individual branch-out
            # (the rail will be drawn at the fork point instead)
            branch_from_lane = None
            parent_is_fork_point = False
            if not is_merge and self.graph is not None:
                parent_shas = getattr(commit, 'parent_shas', [])
                if parent_shas:
                    first_parent_sha = parent_shas[0]
                    if first_parent_sha in self.graph.commits:
                        parent = self.graph.commits[first_parent_sha]
                        parent_lane = getattr(parent, 'lane', 0)
                        parent_is_fork_point = getattr(parent, 'is_fork_point', False)
                        parent_forked_lanes = getattr(parent, 'forked_lanes', [])
                        
                        if parent_lane != commit_lane:
                            # Check if parent is a fork point that includes our lane
                            if parent_is_fork_point and commit_lane in parent_forked_lanes:
                                # Suppress individual branch-out - rail is at fork point
                                branch_from_lane = None
                            else:
                                # Normal branch-out (not part of grouped rail)
                                branch_from_lane = parent_lane
            
            # Check if THIS commit is a fork point (draw grouped rail)
            is_fork_point = getattr(commit, 'is_fork_point', False)
            forked_lanes = getattr(commit, 'forked_lanes', [])
            
            # Build columns for each lane
            columns = []
            
            # Determine which lanes need to be shown
            # Include: commit lane, active lanes, merge source lanes, branch source lane, forked lanes
            lanes_to_show = set([commit_lane])
            lanes_to_show.update(active_lanes)
            lanes_to_show.update(merge_source_lanes)
            if branch_from_lane is not None:
                lanes_to_show.add(branch_from_lane)
            if is_fork_point:
                lanes_to_show.update(forked_lanes)
            
            # Calculate display range (0 to max of all relevant lanes + 1)
            display_max = max(lanes_to_show) + 1 if lanes_to_show else 1
            display_max = max(display_max, max_lanes)
            
            for lane in range(display_max):
                color = self.get_color_for_lane(lane)
                
                if lane == commit_lane:
                    # This is the commit's lane - show commit symbol
                    # HEAD gets bold bright green for maximum visibility!
                    if is_head:
                        columns.append(f"[bold {self.HEAD_COLOR}]{commit_symbol}[/bold {self.HEAD_COLOR}]")
                    else:
                        columns.append(f"[{color}]{commit_symbol}[/{color}]")
                elif lane in merge_source_lanes:
                    # This lane is merging into the commit
                    # Show merge indicator pointing toward the commit
                    if lane > commit_lane:
                        # Merge coming from the right - use └ and horizontal line
                        columns.append(f"[{self.merge_color}]{self.MERGE_LEFT}[/{self.merge_color}]")
                    else:
                        # Merge coming from the left - use ┘
                        columns.append(f"[{self.merge_color}]{self.MERGE_RIGHT}[/{self.merge_color}]")
                elif branch_from_lane is not None and lane == branch_from_lane:
                    # This is where the branch comes from - show branch-out indicator
                    # Use ├ (tee) to show branch continuing down and branching right
                    branch_color = self.get_color_for_lane(commit_lane)  # Use new branch's color
                    if lane < commit_lane:
                        # Branch going right from parent lane
                        columns.append(f"[{branch_color}]{self.CURVE_TOP_LEFT}[/{branch_color}]")
                    else:
                        # Branch going left from parent lane (unusual but handle it)
                        columns.append(f"[{branch_color}]{self.CURVE_TOP_RIGHT}[/{branch_color}]")
                elif lane in active_lanes:
                    # Active lane - show vertical line
                    columns.append(f"[{color}]{self.VERTICAL_LINE}[/{color}]")
                else:
                    # Empty lane
                    columns.append(self.SPACE)
            
            # Apply merge connections (modifies columns in place)
            # NOTE: Do NOT return early - fork rail may also need to run!
            if merge_source_lanes and is_merge:
                columns = self._add_merge_connections(columns, commit_lane, merge_source_lanes, active_lanes)
            
            # Apply fork rail connections (modifies columns in place)
            # This NOW RUNS EVEN FOR MERGES - _add_fork_point_rail preserves merge corners
            if is_fork_point and forked_lanes:
                columns = self._add_fork_point_rail(columns, commit_lane, forked_lanes, active_lanes)
            
            # Join columns - use appropriate join based on what was applied
            if merge_source_lanes and is_merge and is_fork_point and forked_lanes:
                # Both merge AND fork - use combined join covering both zones
                return self._join_columns_for_merge_and_fork(columns, commit_lane, merge_source_lanes, forked_lanes)
            elif merge_source_lanes and is_merge:
                # Merge only
                return self._join_columns_for_merge(columns, commit_lane, merge_source_lanes)
            elif is_fork_point and forked_lanes:
                # Fork rail only
                return self._join_columns_for_fork_rail(columns, commit_lane, forked_lanes)
            
            # Add horizontal branch-out connections (individual style, not merge/fork)
            if branch_from_lane is not None:
                columns = self._add_branch_out_connections(columns, commit_lane, branch_from_lane, active_lanes)
                return self._join_columns_for_branch(columns, commit_lane, branch_from_lane)
            
            return " ".join(columns)
            
        except Exception as e:
            # Fallback to simple single-lane rendering
            is_head = self._is_head_commit(commit)
            if is_head:
                commit_symbol = self.HEAD_INDICATOR
                return f"[bold {self.HEAD_COLOR}]{commit_symbol} {self.VERTICAL_LINE}[/bold {self.HEAD_COLOR}]"
            else:
                commit_symbol = self.MERGE_DOT if getattr(commit, 'is_merge', lambda: False)() else self.COMMIT_DOT
                return f"[{self.line_color}]{commit_symbol} {self.VERTICAL_LINE}[/{self.line_color}]"
    
    def _add_merge_connections(self, columns: list, commit_lane: int, 
                                merge_source_lanes: list, active_lanes: set) -> list:
        """Add horizontal merge connection lines between commit and merge sources.
        
        This enhances the column visualization to show clear merge paths:
        - Horizontal lines (─) between merge commit and source lanes
        - Proper corner characters (└ ┘) at the source lanes
        
        Args:
            columns: List of column strings (already populated)
            commit_lane: The lane where the merge commit is
            merge_source_lanes: Lanes that are merging into this commit
            active_lanes: Currently active lanes
            
        Returns:
            Updated columns list with merge connections
        """
        try:
            result = []
            
            for lane, col in enumerate(columns):
                color = self.get_color_for_lane(lane)
                
                if lane == commit_lane:
                    # Commit lane - keep the merge dot
                    result.append(col)
                elif lane in merge_source_lanes:
                    # Source lane - show corner merging toward commit
                    if lane > commit_lane:
                        result.append(f"[{self.merge_color}]{self.MERGE_LEFT}[/{self.merge_color}]")
                    else:
                        result.append(f"[{self.merge_color}]{self.MERGE_RIGHT}[/{self.merge_color}]")
                elif self._is_between_merge_and_source(lane, commit_lane, merge_source_lanes):
                    # Lane is between commit and a merge source - show horizontal line
                    if lane in active_lanes:
                        # Cross with active lane
                        result.append(f"[{self.merge_color}]{self.CROSS}[/{self.merge_color}]")
                    else:
                        # Just horizontal line
                        result.append(f"[{self.merge_color}]{self.HORIZONTAL}[/{self.merge_color}]")
                else:
                    # Not involved in merge - keep original
                    result.append(col)
            
            return result
            
        except Exception:
            return columns
    
    def _is_between_merge_and_source(self, lane: int, commit_lane: int, 
                                      merge_source_lanes: list) -> bool:
        """Check if a lane is between the merge commit and any of its source lanes.
        
        Args:
            lane: Lane to check
            commit_lane: Merge commit's lane
            merge_source_lanes: List of source lanes
            
        Returns:
            True if lane is between commit and any source
        """
        for source_lane in merge_source_lanes:
            min_lane = min(commit_lane, source_lane)
            max_lane = max(commit_lane, source_lane)
            if min_lane < lane < max_lane:
                return True
        return False
    
    def _join_columns_for_merge(self, columns: list, commit_lane: int,
                                 merge_source_lanes: list) -> str:
        """Join columns with horizontal line characters for continuous merge visualization.
        
        For merge commits, we insert actual horizontal line characters (─) between
        columns in the merge zone to create a visible connection between the commit
        and its merge sources.
        
        Args:
            columns: List of column strings with Rich markup
            commit_lane: The lane where the merge commit is
            merge_source_lanes: Lanes that are merging into this commit
            
        Returns:
            Joined string with horizontal lines in merge zone, spaces elsewhere
        """
        if not columns:
            return ""
        
        # Find the full extent of the merge zone (min to max of all involved lanes)
        all_merge_lanes = [commit_lane] + list(merge_source_lanes)
        min_merge_lane = min(all_merge_lanes)
        max_merge_lane = max(all_merge_lanes)
        
        output_parts = []
        for i, col in enumerate(columns):
            output_parts.append(col)
            
            # Determine what separator to add after this column
            if i < len(columns) - 1:
                current_in_zone = min_merge_lane <= i <= max_merge_lane
                next_in_zone = min_merge_lane <= (i + 1) <= max_merge_lane
                
                # In merge zone: insert horizontal line character for visible connection
                # Outside merge zone: insert space for normal spacing
                if current_in_zone and next_in_zone:
                    output_parts.append(f"[{self.merge_color}]{self.HORIZONTAL}[/{self.merge_color}]")
                else:
                    output_parts.append(" ")
        
        return "".join(output_parts)
    
    def _join_columns_for_merge_and_fork(self, columns: list, commit_lane: int,
                                          merge_source_lanes: list, forked_lanes: list) -> str:
        """Join columns with horizontal lines for commits that are BOTH merges AND fork points.
        
        This handles the case where a commit has merge sources coming in AND branches
        forking out. The join zone is the UNION of both the merge zone and fork zone.
        
        Args:
            columns: List of column strings with Rich markup
            commit_lane: The lane where the commit is
            merge_source_lanes: Lanes that are merging into this commit
            forked_lanes: Lanes that fork off from this commit
            
        Returns:
            Joined string with horizontal lines in combined zone, spaces elsewhere
        """
        if not columns:
            return ""
        
        # Calculate merge zone extent
        all_merge_lanes = [commit_lane] + list(merge_source_lanes)
        min_merge_lane = min(all_merge_lanes)
        max_merge_lane = max(all_merge_lanes)
        
        # Calculate fork zone extent
        all_fork_lanes = [commit_lane] + list(forked_lanes)
        min_fork_lane = min(all_fork_lanes)
        max_fork_lane = max(all_fork_lanes)
        
        # Combined zone is the UNION of both zones
        zone_min = min(min_merge_lane, min_fork_lane)
        zone_max = max(max_merge_lane, max_fork_lane)
        
        output_parts = []
        for i, col in enumerate(columns):
            output_parts.append(col)
            
            # Determine what separator to add after this column
            if i < len(columns) - 1:
                current_in_zone = zone_min <= i <= zone_max
                next_in_zone = zone_min <= (i + 1) <= zone_max
                
                # In combined zone: insert horizontal line character
                # Outside zone: insert space
                if current_in_zone and next_in_zone:
                    # Use merge color for horizontal lines in combined mode
                    output_parts.append(f"[{self.merge_color}]{self.HORIZONTAL}[/{self.merge_color}]")
                else:
                    output_parts.append(" ")
        
        return "".join(output_parts)
    
    def _add_branch_out_connections(self, columns: list, commit_lane: int,
                                     branch_from_lane: int, active_lanes: set) -> list:
        """Add horizontal branch-out connection lines between parent lane and new branch.
        
        This shows where a branch starts by drawing a horizontal line from the
        parent lane to the new commit's lane.
        
        Args:
            columns: List of column strings (already populated)
            commit_lane: The lane where the new branch commit is
            branch_from_lane: The lane of the parent commit (where branch starts from)
            active_lanes: Currently active lanes
            
        Returns:
            Updated columns list with branch-out connections
        """
        try:
            result = []
            branch_color = self.get_color_for_lane(commit_lane)
            
            for lane, col in enumerate(columns):
                if lane == commit_lane:
                    # Keep the commit symbol
                    result.append(col)
                elif lane == branch_from_lane:
                    # Source lane - show branch-out corner
                    if lane < commit_lane:
                        # Branching to the right
                        result.append(f"[{branch_color}]{self.CURVE_TOP_LEFT}[/{branch_color}]")
                    else:
                        # Branching to the left (unusual but possible)
                        result.append(f"[{branch_color}]{self.CURVE_TOP_RIGHT}[/{branch_color}]")
                elif self._is_between_branch_and_parent(lane, commit_lane, branch_from_lane):
                    # Lane is between commit and branch source - show horizontal line
                    if lane in active_lanes:
                        # Cross with active lane - use T junction
                        result.append(f"[{branch_color}]{self.BRANCH_DOWN}[/{branch_color}]")
                    else:
                        # Just horizontal line
                        result.append(f"[{branch_color}]{self.HORIZONTAL}[/{branch_color}]")
                else:
                    # Not involved in branch-out - keep original
                    result.append(col)
            
            return result
            
        except Exception:
            return columns
    
    def _is_between_branch_and_parent(self, lane: int, commit_lane: int, branch_from_lane: int) -> bool:
        """Check if a lane is between the branch commit and its parent lane.
        
        Args:
            lane: Lane to check
            commit_lane: The new branch's lane
            branch_from_lane: The parent's lane
            
        Returns:
            True if lane is strictly between commit and parent
        """
        min_lane = min(commit_lane, branch_from_lane)
        max_lane = max(commit_lane, branch_from_lane)
        return min_lane < lane < max_lane
    
    def _join_columns_for_branch(self, columns: list, commit_lane: int, branch_from_lane: int) -> str:
        """Join columns with horizontal line characters for branch-out visualization.
        
        Similar to _join_columns_for_merge but for branch-out points.
        
        Args:
            columns: List of column strings with Rich markup
            commit_lane: The lane where the new branch commit is
            branch_from_lane: The lane of the parent commit
            
        Returns:
            Joined string with horizontal lines in branch zone, spaces elsewhere
        """
        if not columns:
            return ""
        
        # Find the extent of the branch zone
        min_branch_lane = min(commit_lane, branch_from_lane)
        max_branch_lane = max(commit_lane, branch_from_lane)
        
        branch_color = self.get_color_for_lane(commit_lane)
        output_parts = []
        
        for i, col in enumerate(columns):
            output_parts.append(col)
            
            # Determine what separator to add after this column
            if i < len(columns) - 1:
                current_in_zone = min_branch_lane <= i <= max_branch_lane
                next_in_zone = min_branch_lane <= (i + 1) <= max_branch_lane
                
                # In branch zone: insert horizontal line character
                # Outside branch zone: insert space
                if current_in_zone and next_in_zone:
                    output_parts.append(f"[{branch_color}]{self.HORIZONTAL}[/{branch_color}]")
                else:
                    output_parts.append(" ")
        
        return "".join(output_parts)
    
    def _add_fork_point_rail(self, columns: list, commit_lane: int,
                             forked_lanes: list, active_lanes: set) -> list:
        """Add grouped horizontal rail at fork point (GitKraken style).
        
        Instead of drawing individual branch-out lines at each branch's first commit,
        this draws ONE shared horizontal rail at the fork point, with T-junctions
        where branches fork off.
        
        Visual effect:
        ├──┴──┴──┘  (rail from commit lane to max forked lane)
        
        IMPORTANT: This function preserves existing commit symbols (●, ◆, ➤) and
        merge corners (╮, ╯, ╭) when the commit is both a merge and a fork point.
        The horizontal rail connects to these symbols via the join function.
        
        Args:
            columns: List of column strings (already populated)
            commit_lane: The lane where the fork point commit is
            forked_lanes: Lanes that fork off from this commit
            active_lanes: Currently active lanes
            
        Returns:
            Updated columns list with fork rail
        """
        try:
            result = []
            max_forked_lane = max(forked_lanes) if forked_lanes else commit_lane
            min_forked_lane = min(forked_lanes) if forked_lanes else commit_lane
            
            # Determine rail extent (from commit lane to furthest forked lane)
            rail_min = min(commit_lane, min_forked_lane)
            rail_max = max(commit_lane, max_forked_lane)
            
            # Define symbols that should NOT be overwritten
            # These are commit dots and merge corners that take visual precedence
            commit_symbols = (self.COMMIT_DOT, self.MERGE_DOT, self.HEAD_INDICATOR)
            merge_corners = (self.MERGE_LEFT, self.MERGE_RIGHT, self.CURVE_TOP_LEFT, self.CURVE_TOP_RIGHT)
            
            for lane, col in enumerate(columns):
                color = self.get_color_for_lane(lane)
                
                if lane == commit_lane:
                    # Fork point commit - check if we should preserve existing symbol
                    # If column already has a commit symbol (●, ◆, ➤), keep it!
                    # The horizontal rail connection will be handled by join function
                    has_commit_symbol = any(sym in col for sym in commit_symbols)
                    if has_commit_symbol:
                        # Preserve the commit dot/merge dot/head indicator
                        result.append(col)
                    else:
                        # No commit symbol, show T-junction going toward forked lanes
                        # ├ if forking to the right, ┤ if forking to the left
                        if max_forked_lane > commit_lane:
                            result.append(f"[{color}]{self.T_RIGHT}[/{color}]")
                        else:
                            result.append(f"[{color}]{self.T_LEFT}[/{color}]")
                elif lane in forked_lanes:
                    # This lane forks off - check if we should preserve merge corners
                    # If column already has a merge corner (╮, ╯, ╭, ╮), keep it!
                    # The rail continues horizontally via the join function
                    has_merge_corner = any(corner in col for corner in merge_corners)
                    if has_merge_corner:
                        # Preserve the merge corner - rail connects via horizontal line
                        result.append(col)
                    else:
                        # No merge corner, show T-junction going up (┴)
                        # Use the forked lane's color
                        forked_color = self.get_color_for_lane(lane)
                        if lane == rail_max:
                            # Rightmost forked lane - use corner ┘ (opening upward)
                            result.append(f"[{forked_color}]{self.CORNER_BOTTOM_RIGHT}[/{forked_color}]")
                        else:
                            # Middle forked lane - use T-junction ┴ (opening upward to branches)
                            result.append(f"[{forked_color}]{self.T_UP}[/{forked_color}]")
                elif rail_min < lane < rail_max:
                    # Lane is in the rail zone but not a fork point
                    # Check for merge corners here too - they should be preserved
                    has_merge_corner = any(corner in col for corner in merge_corners)
                    if has_merge_corner:
                        # Preserve merge corner in the rail zone
                        result.append(col)
                    elif lane in active_lanes:
                        # Cross with active lane - use cross ┼
                        result.append(f"[{color}]{self.CROSS}[/{color}]")
                    else:
                        # Just horizontal line
                        result.append(f"[{color}]{self.HORIZONTAL}[/{color}]")
                else:
                    # Not involved in fork rail - keep original
                    result.append(col)
            
            return result
            
        except Exception:
            return columns
    
    def _join_columns_for_fork_rail(self, columns: list, commit_lane: int,
                                     forked_lanes: list) -> str:
        """Join columns with horizontal line characters for fork rail visualization.
        
        Creates continuous horizontal lines in the fork rail zone for
        GitKraken-style grouped branch-out.
        
        Args:
            columns: List of column strings with Rich markup
            commit_lane: The lane where the fork point commit is
            forked_lanes: Lanes that fork off from this commit
            
        Returns:
            Joined string with horizontal lines in rail zone, spaces elsewhere
        """
        if not columns:
            return ""
        
        max_forked_lane = max(forked_lanes) if forked_lanes else commit_lane
        min_forked_lane = min(forked_lanes) if forked_lanes else commit_lane
        
        # Rail extent
        rail_min = min(commit_lane, min_forked_lane)
        rail_max = max(commit_lane, max_forked_lane)
        
        # Use commit lane color for the rail
        rail_color = self.get_color_for_lane(commit_lane)
        output_parts = []
        
        for i, col in enumerate(columns):
            output_parts.append(col)
            
            # Determine what separator to add after this column
            if i < len(columns) - 1:
                current_in_rail = rail_min <= i <= rail_max
                next_in_rail = rail_min <= (i + 1) <= rail_max
                
                # In rail zone: insert horizontal line character
                # Outside rail zone: insert space
                if current_in_rail and next_in_rail:
                    output_parts.append(f"[{rail_color}]{self.HORIZONTAL}[/{rail_color}]")
                else:
                    output_parts.append(" ")
        
        return "".join(output_parts)
    
    def render_commit_line(self, commit: CommitNode, max_width: int = 80) -> str:
        """Render a clean single-line commit visualization with branch labels in left column.
        
        Format: [label_column] [graph] [sha] [message] [author]
        Example:
            main*          ● │ abc1234 Commit message - author
            origin/main    │ │ 
            feature/foo    │ ● def5678 Another commit - author
        
        Args:
            commit: The commit to render
            max_width: Maximum width for the line (default 80 for better containment)
            
        Returns:
            Formatted string with label column, graph, and commit info
            
        Note: Includes comprehensive error handling to prevent stylesheet errors
        """
        # Fixed width for label column (ASCII markers for consistent alignment)
        LABEL_COLUMN_WIDTH = 20
        
        try:
            # Validate commit data
            if not commit or not hasattr(commit, 'sha'):
                return " " * LABEL_COLUMN_WIDTH + "[error] Invalid commit data"
            
            # Calculate branch depth for this commit with error handling
            try:
                depth = self._calculate_commit_depth(commit)
            except Exception as depth_error:
                depth = 0  # Default to main line if depth calculation fails
            
            # Determine commit type and corresponding symbol
            # HEAD commits get special very visible indicator!
            is_head = self._is_head_commit(commit)
            if is_head:
                commit_symbol = self.HEAD_INDICATOR
            elif commit.is_merge():
                commit_symbol = self.MERGE_DOT
            else:
                commit_symbol = self.COMMIT_DOT
            
            # Get color based on depth and type with fallback
            # HEAD commits get BRIGHT GREEN for maximum visibility!
            try:
                if is_head:
                    commit_color = self.HEAD_COLOR
                elif commit.is_merge():
                    commit_color = self.merge_color
                else:
                    commit_color = self.depth_colors[min(max(depth, 0), len(self.depth_colors) - 1)]
            except (IndexError, TypeError):
                commit_color = self.depth_colors[0]  # Fallback to blue
            
            # Build label column (left side with branch/tag labels)
            try:
                label_column = self._format_label_column(commit, width=LABEL_COLUMN_WIDTH)
            except Exception as label_error:
                label_column = " " * LABEL_COLUMN_WIDTH
            
            # Build graph part with depth notation and validation
            try:
                # Use multi-lane graph columns if graph context is available
                if self.graph is not None:
                    graph_part = self._build_graph_columns(commit)
                else:
                    # Fallback to depth-based rendering if no graph context
                    graph_part = self._build_depth_graph_part(commit, depth, commit_symbol, commit_color)
            except Exception as graph_error:
                # Fallback to simple format if graph part fails
                graph_part = f"[#89b4fa]{commit_symbol} │[/#89b4fa]"
            
            # Calculate available width for commit info
            # Subtract label column width and graph width
            try:
                graph_part_display_len = len(self._strip_markup(graph_part))
                available_width = max(20, max_width - LABEL_COLUMN_WIDTH - graph_part_display_len - 1)  # -1 for space
            except Exception:
                available_width = 50  # Safe fallback
            
            # Format commit info with error handling (no inline refs - they're in label column)
            try:
                commit_info = self._format_commit_info(commit, available_width, depth, include_refs=False)
            except Exception as info_error:
                # Fallback to simple format if commit info fails
                safe_sha = getattr(commit, 'short_sha', commit.sha[:8])[:8]
                commit_info = f"[#89b4fa]{safe_sha}[/#89b4fa] [#cdd6f4]Error formatting[/#cdd6f4]"
            
            # Final result: label_column + graph + commit_info
            result = f"{label_column}{graph_part} {commit_info}"
            
            # Validate result doesn't contain problematic characters
            if not self._is_safe_markup(result):
                return f"{' ' * LABEL_COLUMN_WIDTH}[#89b4fa]{commit_symbol} │[/#89b4fa] [#89b4fa]{commit.short_sha[:8]}[/#89b4fa] [#cdd6f4]{commit.message[:20]}...[/#cdd6f4]"
            
            return result
            
        except Exception as e:
            # Ultimate fallback
            try:
                safe_sha = getattr(commit, 'short_sha', getattr(commit, 'sha', 'unknown')[:8])[:8]
                safe_msg = getattr(commit, 'message', 'Error rendering')[:20]
                return f"{' ' * LABEL_COLUMN_WIDTH}[#89b4fa]● │[/#89b4fa] [#89b4fa]{safe_sha}[/#89b4fa] [#cdd6f4]{safe_msg}...[/#cdd6f4]"
            except Exception:
                return f"{' ' * LABEL_COLUMN_WIDTH}[#89b4fa]● │[/#89b4fa] [#89b4fa]error[/#89b4fa] [#cdd6f4]render error[/#cdd6f4]"
    
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
    
    def _build_simple_timeline(self, commit: CommitNode) -> str:
        """Build a simple single-line timeline visualization.
        
        Args:
            commit: The commit being rendered
            
        Returns:
            String containing the simple timeline visualization
        """
        # Simple timeline: commit symbol + vertical line
        # HEAD commits get special visible indicator!
        if self._is_head_commit(commit):
            return f"[bold {self.HEAD_COLOR}]{self.HEAD_INDICATOR} {self.VERTICAL_LINE}[/bold {self.HEAD_COLOR}]"
        elif commit.is_merge():
            return f"{self.MERGE_DOT} {self.VERTICAL_LINE}"
        else:
            return f"{self.COMMIT_DOT} {self.VERTICAL_LINE}"
    

    
    def reset(self) -> None:
        """Reset the renderer state for error recovery."""
        # Simple renderer has minimal state to reset
        pass
    
    def _format_label_column(self, commit: CommitNode, width: int = 20) -> str:
        """Format branch labels for a dedicated left column.
        
        Creates a fixed-width left column with branch/tag labels styled
        like GitKraken's branch badges.
        
        Args:
            commit: Commit to format refs for
            width: Fixed width for the label column (default 20 chars)
            
        Returns:
            Fixed-width string with styled labels, padded/truncated to fit
            
        Styling (ASCII-only for consistent alignment):
            - Current branch: Green bold with asterisk → *main
            - Local branches: Cyan → feature/foo
            - Tags: Yellow with hash → #v1.0.0
            - Remote branches: Dim gray → origin/main
        """
        from octotui.graph_data import RefType
        
        if not hasattr(commit, 'refs') or not commit.refs:
            # Return empty column with proper width
            return " " * width
        
        try:
            labels = []
            labels_display = []  # Track display strings without markup for length calc
            
            # Sort refs: current first, then branches, then tags, then remotes
            def ref_sort_key(ref):
                if getattr(ref, 'is_current', False):
                    return (0, ref.short_name())
                elif ref.ref_type == RefType.BRANCH:
                    return (1, ref.short_name())
                elif ref.ref_type == RefType.TAG:
                    return (2, ref.short_name())
                elif ref.ref_type == RefType.REMOTE_BRANCH:
                    return (3, ref.short_name())
                else:
                    return (4, ref.short_name())
            
            sorted_refs = sorted(commit.refs, key=ref_sort_key)
            
            for ref in sorted_refs:
                ref_name = ref.short_name()
                is_current = getattr(ref, 'is_current', False)
                
                # Style based on ref type (no parentheses - clean badge style)
                # ASCII markers: * = current, # = tag (remotes/locals use name only)
                if is_current:
                    # Current branch: Green bold with asterisk prefix
                    display_name = f"*{ref_name}"
                    labels.append(f"[bold #a6e3a1]{display_name}[/bold #a6e3a1]")
                    labels_display.append(display_name)
                elif ref.ref_type == RefType.TAG:
                    # Tags: Yellow with hash prefix
                    display_name = f"#{ref_name}"
                    labels.append(f"[#f9e2af]{display_name}[/#f9e2af]")
                    labels_display.append(display_name)
                elif ref.ref_type == RefType.REMOTE_BRANCH:
                    # Remote branches: Dim gray (already has origin/ prefix)
                    display_name = ref_name
                    labels.append(f"[dim #6c7086]{display_name}[/dim #6c7086]")
                    labels_display.append(display_name)
                elif ref.ref_type == RefType.BRANCH:
                    # Local branches: Cyan (no prefix needed)
                    display_name = ref_name
                    labels.append(f"[#7dcfff]{display_name}[/#7dcfff]")
                    labels_display.append(display_name)
                else:
                    # HEAD or other: Purple
                    display_name = ref_name
                    labels.append(f"[#cba6f7]{display_name}[/#cba6f7]")
                    labels_display.append(display_name)
            
            if not labels:
                return " " * width
            
            # Build the column - try to fit labels with space separator
            result_parts = []
            result_display_parts = []
            current_len = 0
            
            for i, (label, display) in enumerate(zip(labels, labels_display)):
                separator_len = 1 if result_parts else 0  # Space between labels
                # Calculate display width (ASCII chars = 1 column each)
                label_len = len(display)
                
                if current_len + separator_len + label_len <= width - 1:  # -1 for trailing space
                    if result_parts:
                        result_parts.append(" ")
                        result_display_parts.append(" ")
                    result_parts.append(label)
                    result_display_parts.append(display)
                    current_len += separator_len + label_len
                elif not result_parts:
                    # First label is too long - truncate it
                    if label_len > width - 3:
                        truncated = display[:width - 3] + ".."
                        # Re-apply styling to truncated name
                        if "#a6e3a1" in label:
                            result_parts.append(f"[bold #a6e3a1]{truncated}[/bold #a6e3a1]")
                        elif "#f9e2af" in label:
                            result_parts.append(f"[#f9e2af]{truncated}[/#f9e2af]")
                        elif "#6c7086" in label:
                            result_parts.append(f"[dim #6c7086]{truncated}[/dim #6c7086]")
                        elif "#7dcfff" in label:
                            result_parts.append(f"[#7dcfff]{truncated}[/#7dcfff]")
                        else:
                            result_parts.append(f"[#cba6f7]{truncated}[/#cba6f7]")
                        result_display_parts.append(truncated)
                        current_len = len(truncated)
                    else:
                        result_parts.append(label)
                        result_display_parts.append(display)
                        current_len = label_len
                    break
                else:
                    # Can't fit more labels
                    break
            
            # Join and pad to fixed width
            result = "".join(result_parts)
            display_result = "".join(result_display_parts)
            # Calculate display width (ASCII = string length)
            display_len = len(display_result)
            
            # Pad with spaces to reach fixed width
            padding_needed = width - display_len
            if padding_needed > 0:
                result = result + " " * padding_needed
            
            return result
            
        except Exception:
            return " " * width
    
    def _format_ref_labels(self, commit: CommitNode, max_label_width: int = 40) -> tuple[str, int]:
        """Format ref labels (branches and tags) for a commit.
        
        NOTE: This method is kept for backwards compatibility but is no longer
        used in the main render path. Labels now appear in the left column via
        _format_label_column() instead of inline.
        
        Args:
            commit: Commit to format refs for
            max_label_width: Maximum width for all labels combined
            
        Returns:
            Tuple of (formatted_labels_with_markup, display_length)
            
        Styling:
            - Current branch: Green bold with * → (main*)
            - Local branches: Cyan → (feature/foo)
            - Tags: Yellow with # → (#v1.0.0)
            - Remote branches: Dim gray → (origin/main)
        """
        from octotui.graph_data import RefType
        
        if not hasattr(commit, 'refs') or not commit.refs:
            return "", 0
        
        try:
            labels = []
            
            # Sort refs: current first, then branches, then tags, then remotes
            def ref_sort_key(ref):
                if getattr(ref, 'is_current', False):
                    return (0, ref.short_name())
                elif ref.ref_type == RefType.BRANCH:
                    return (1, ref.short_name())
                elif ref.ref_type == RefType.TAG:
                    return (2, ref.short_name())
                elif ref.ref_type == RefType.REMOTE_BRANCH:
                    return (3, ref.short_name())
                else:
                    return (4, ref.short_name())
            
            sorted_refs = sorted(commit.refs, key=ref_sort_key)
            
            for ref in sorted_refs:
                ref_name = ref.short_name()
                is_current = getattr(ref, 'is_current', False)
                
                # Truncate long ref names
                if len(ref_name) > 20:
                    ref_name = ref_name[:17] + "..."
                
                # Style based on ref type
                if is_current:
                    # Current branch: Green bold with asterisk
                    labels.append(f"[bold #a6e3a1]({ref_name}*)[/bold #a6e3a1]")
                elif ref.ref_type == RefType.TAG:
                    # Tags: Yellow with hash prefix
                    labels.append(f"[#f9e2af](#{ref_name})[/#f9e2af]")
                elif ref.ref_type == RefType.REMOTE_BRANCH:
                    # Remote branches: Dim gray
                    labels.append(f"[dim #6c7086]({ref_name})[/dim #6c7086]")
                elif ref.ref_type == RefType.BRANCH:
                    # Local branches: Cyan
                    labels.append(f"[#89dceb]({ref_name})[/#89dceb]")
                else:
                    # HEAD or other: Purple
                    labels.append(f"[#cba6f7]({ref_name})[/#cba6f7]")
            
            if not labels:
                return "", 0
            
            # Join labels with space
            result = " ".join(labels)
            
            # Calculate display length (without markup)
            display_len = len(self._strip_markup(result))
            
            # Truncate if too long - keep first few labels
            if display_len > max_label_width:
                truncated_labels = []
                current_len = 0
                for label in labels:
                    label_len = len(self._strip_markup(label))
                    if current_len + label_len + 1 <= max_label_width - 3:  # -3 for "..."
                        truncated_labels.append(label)
                        current_len += label_len + 1
                    else:
                        break
                
                if truncated_labels:
                    result = " ".join(truncated_labels) + "[#6c7086]...[/#6c7086]"
                    display_len = len(self._strip_markup(result))
                else:
                    # Even first label is too long, show simplified placeholder
                    result = "[dim #6c7086](#...)[/dim #6c7086]"
                    display_len = len(self._strip_markup(result))
            
            return result, display_len
            
        except Exception:
            return "", 0
    
    def _format_commit_info(self, commit: CommitNode, max_width: int, depth: int = 0, include_refs: bool = False) -> str:
        """Format commit information with strict width containment.
        
        Args:
            commit: Commit to format
            max_width: Maximum width for commit info (actual display characters, not including markup)
            depth: Branch depth level (unused, kept for compatibility)
            include_refs: Whether to include ref labels inline (default False - refs are in label column)
            
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
        
        # Get ref labels only if requested (now refs are typically in left column)
        ref_labels = ""
        ref_labels_len = 0
        if include_refs:
            ref_labels, ref_labels_len = self._format_ref_labels(commit, max_label_width=35)
        
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
        # Format: SHA [ref_labels] message - author
        spaces_needed = 2 + (1 if ref_labels else 0)  # spaces: SHA_MSG, MSG_AUTHOR, optionally REF_MSG
        total_fixed_len = sha_len + ref_labels_len + author_len + spaces_needed
        available_message_len = max_width - total_fixed_len
        
        # Ensure reasonable bounds for message
        if available_message_len < 5:
            # Not enough space, reduce ref labels
            available_message_len = 15
            if include_refs:
                # Recalculate with shorter refs
                ref_labels, ref_labels_len = self._format_ref_labels(commit, max_label_width=15)
            spaces_needed = 2 + (1 if ref_labels else 0)
            total_fixed_len = sha_len + ref_labels_len + author_len + spaces_needed
            available_message_len = max(5, max_width - total_fixed_len)
        
        available_message_len = min(45, max(5, available_message_len))  # Between 5-45 chars (increased from 35)
        
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
        
        # Build raw components without markup first for length calculation
        raw_parts = [sha_part]
        if ref_labels_len > 0:
            raw_parts.append(self._strip_markup(ref_labels))
        raw_parts.append(message)
        raw_parts.append(author_part)
        
        raw_result = ' '.join(raw_parts)
        
        # Final safety check - ensure we don't exceed width
        if len(raw_result) > max_width:
            # Emergency truncation of message
            excess = len(raw_result) - max_width
            message = message[:max(1, len(message) - excess - 3)] + "..."
        
        # Build final result with markup
        # Format: SHA [ref_labels] message - author
        parts_with_markup = []
        parts_with_markup.append(f"[#89b4fa]{sha_part}[/#89b4fa]")
        if ref_labels:
            parts_with_markup.append(f" {ref_labels}")
        parts_with_markup.append(f" [#cdd6f4]{message}[/#cdd6f4]")
        parts_with_markup.append(f" [#6C7086]{author_part}[/#6C7086]")
        
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
    
    def _display_width(self, text: str) -> int:
        """Calculate the display width of text, accounting for wide characters.
        
        Emojis and other wide characters take 2 columns in terminal display,
        but Python's len() counts them as 1. This method properly accounts
        for wide characters to ensure correct column alignment.
        
        Args:
            text: Text to measure (should be plain text without markup)
            
        Returns:
            Display width in terminal columns
        """
        if not text:
            return 0
        
        width = 0
        for char in text:
            code_point = ord(char)
            # Emoji ranges that are typically 2 columns wide:
            # - Miscellaneous Symbols and Pictographs: U+1F300 - U+1F5FF
            # - Emoticons: U+1F600 - U+1F64F
            # - Transport and Map Symbols: U+1F680 - U+1F6FF
            # - Supplemental Symbols and Pictographs: U+1F900 - U+1F9FF
            # - Symbols and Pictographs Extended-A: U+1FA00 - U+1FAFF
            if code_point >= 0x1F300 and code_point <= 0x1FAFF:
                width += 2
            # Also check for other wide characters using East Asian Width
            elif code_point >= 0x1100:  # Start of potential wide chars
                import unicodedata
                ea_width = unicodedata.east_asian_width(char)
                if ea_width in ('F', 'W'):  # Fullwidth or Wide
                    width += 2
                else:
                    width += 1
            else:
                width += 1
        return width
    
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
    
    def _build_depth_graph_part(self, commit: CommitNode, depth: int, symbol: str, color: str) -> str:
        """Build the graph part with depth notation.
        
        Args:
            commit: Commit being rendered
            depth: Branch depth level (validated)
            symbol: Commit symbol (● or ◆)
            color: Color for this commit (validated)
            
        Returns:
            Formatted graph part with depth indication
        """
        try:
            # Validate inputs
            if not color or not color.startswith('#'):
                color = '#89b4fa'  # Fallback to blue
            
            if not symbol or symbol not in [self.COMMIT_DOT, self.MERGE_DOT, self.HEAD_INDICATOR]:
                symbol = self.COMMIT_DOT
            
            depth = max(0, depth)  # Ensure non-negative
            
            if depth == 0:
                # Main line - simple clean format
                return f"[{color}]{symbol} {self.VERTICAL_LINE}[/{color}]"
            
            elif depth == 1:
                # First level branch - show branch indicator
                if commit and commit.is_merge():
                    return f"[{color}]{symbol} {self.MERGE_CHAR}L1[/{color}]"
                else:
                    return f"[{color}]{symbol} {self.BRANCH_CHAR}L1[/{color}]"
            
            else:
                # Deeper levels - show with depth notation (limit to L9 for display)
                display_depth = min(depth, 9)
                depth_str = f"L{display_depth}"
                if commit and commit.is_merge():
                    return f"[{color}]{symbol} {self.MERGE_CHAR}{depth_str}[/{color}]"
                else:
                    return f"[{color}]{symbol} {self.BRANCH_CHAR}{depth_str}[/{color}]"
                    
        except Exception as e:
            # Fallback to simple format
            return f"[#89b4fa]{self.COMMIT_DOT} │[/#89b4fa]"
    



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
            
            # Initialize fresh renderer with graph context for multi-lane rendering
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
            
            # Create fresh renderer for each render with graph context
            self.renderer = GitGraphRenderer(graph=self.graph)
            
            # Set up depth calculations if we have graph data
            try:
                if hasattr(self.graph, 'commits') and self.graph.commits:
                    self.renderer.set_depth_from_graph_data(self.graph.commits)
            except Exception as depth_error:
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
                        self.renderer = GitGraphRenderer(graph=self.graph)
        
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
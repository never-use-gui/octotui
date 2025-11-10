import os
from pathlib import Path
from typing import Optional, Dict
from textual.app import App, ComposeResult
from textual.widgets import (
    Static,
    Header,
    Footer,
    Button,
    Tree,
    Label,
    Input,
    TabbedContent,
    TabPane,
    Select,
    TextArea,
)
from textual.containers import Horizontal, Vertical, Container, VerticalScroll
from textual.widgets.tree import TreeNode
from octotui.git_status_sidebar import GitStatusSidebar, Hunk
from octotui.octotui_logo import OctotuiLogo
from octotui.gac_integration import GACIntegration
from octotui.gac_config_modal import GACConfigModal
from octotui.diff_markdown import DiffMarkdown, DiffMarkdownConfig
from octotui.commit_graph import CommitGraphWidget
from textual.widget import Widget
from textual.screen import ModalScreen
from textual.widgets import OptionList
from textual.widgets.option_list import Option
import time


class CommitLine(Static):
    """A widget for displaying a commit line with SHA and message."""

    DEFAULT_CSS = """
    CommitLine {
        width: 100%;
        height: 1;
        overflow: hidden hidden;
    }
    """


class GitDiffHistoryTabs(Widget):
    """A widget that contains tabbed diff view, commit history, and commit message."""

    def compose(self) -> ComposeResult:
        """Create the tabbed content with diff view, commit history, and commit message tabs."""
        with TabbedContent():
            with TabPane("Diff View"):
                yield VerticalScroll(id="diff-content")
            with TabPane("Commit Graph", id="graph-tab"):
                # Commit graph will be mounted here dynamically when tab is shown
                yield Container(id="graph-container")
            with TabPane("Commit History"):
                yield VerticalScroll(id="history-content")
            with TabPane("Commit Message"):
                yield Vertical(
                    Label("Commit Message (Subject):", classes="commit-label"),
                    Horizontal(
                        Input(
                            placeholder="Enter commit message...",
                            id="commit-message",
                            classes="commit-input",
                        ),
                        Button("GAC", id="gac-button", classes="gac-button"),
                        classes="commit-message-row",
                    ),
                    Label("Commit Details (Body):", classes="commit-label"),
                    TextArea(
                        placeholder="Enter detailed description (optional)...",
                        id="commit-body",
                        classes="commit-body",
                    ),
                    Button("Commit", id="commit-button", classes="commit-button"),
                    id="commit-section",
                    classes="commit-section",
                )


class GitStatusTabs(Widget):
    """A widget that contains tabbed unstaged and staged changes."""

    def compose(self) -> ComposeResult:
        """Create the tabbed content with unstaged and staged changes tabs."""
        with TabbedContent(id="status-tabs"):
            with TabPane("Unstaged Changes", id="unstaged-tab"):
                yield VerticalScroll(
                    Static(
                        "Hint: Select a file and press 's' to stage the entire file",
                        classes="hint",
                    ),
                    Tree("Unstaged", id="unstaged-tree"),
                )
            with TabPane("Staged Changes", id="staged-tab"):
                yield VerticalScroll(
                    Tree("Staged", id="staged-tree"),
                )


class HelpModal(ModalScreen):
    """Modal screen for displaying help and keybindings."""

    DEFAULT_CSS = """
    HelpModal {
        align: center middle;
    }
    
    Container {
        border: solid #6c7086;
        background: #00122f;
        width: 80%;
        height: 90%;
        max-width: 120;
        max-height: 50;
        margin: 1;
        padding: 0;
    }
    
    VerticalScroll {
        height: 1fr;
        border: none;
        padding: 1 2;
        min-height: 30;
    }
    
    .help-title {
        text-align: center;
        text-style: bold;
        color: #bb9af7;
        margin: 0 0 1 0;
    }
    
    .help-section {
        margin: 1 0;
    }
    
    .help-section-title {
        text-style: bold;
        color: #9ece6a;
        margin: 0 0 1 0;
    }
    
    .help-key {
        color: #a9a1e1;
        text-style: bold;
    }
    
    .help-desc {
        color: #c0caf5;
    }
    """

    def compose(self) -> ComposeResult:
        """Create the help modal content."""
        with Container():
            yield Static("🐶 Tentacle - Keybindings", classes="help-title")
            with VerticalScroll():
                yield self._get_help_content()
            with Horizontal():
                yield Button("Close", classes="cancel-button")

    def _get_help_content(self) -> Static:
        """Generate the help content with all keybindings."""
        help_text = """
[help-section-title]📁 File Navigation[/help-section-title]
[help-key]↑/↓[/help-key]           Navigate through files and hunks
[help-key]Enter[/help-key]         Select file to view diff
[help-key]Tab[/help-key]           Navigate through UI elements (Shift+Tab to go backwards)

[help-section-title]📑 Tab Navigation[/help-section-title]
[help-key]1 or Ctrl+1[/help-key]  Switch to Unstaged Changes tab
[help-key]2 or Ctrl+2[/help-key]  Switch to Staged Changes tab

[help-section-title]🔄 Git Operations[/help-section-title]
[help-key]s[/help-key]             Stage selected file (works from any tab)
[help-key]u[/help-key]             Unstage selected file (works from any tab)
[help-key]a[/help-key]             Stage ALL unstaged changes
[help-key]x[/help-key]             Unstage ALL staged changes
[help-key]c[/help-key]             Commit staged changes

[help-section-title]🌿 Branch Management[/help-section-title]
[help-key]b[/help-key]             Show branch switcher
[help-key]r[/help-key]             Refresh branches

[help-section-title]📡 Remote Operations[/help-section-title]
[help-key]p[/help-key]                Push current branch
[help-key]o[/help-key]                Pull latest changes

[help-section-title]🤖 AI Integration (GAC)[/help-section-title]
[help-key]Ctrl+G[/help-key]        Configure GAC (21+ providers supported)
[help-key]g[/help-key]                Generate commit message with AI

GAC supports OpenAI, Anthropic, Gemini, Mistral, Cohere, DeepSeek,
Groq, Together, Cerebras, OpenRouter, xAI, Ollama, and more!

[help-section-title]⚙️ Application[/help-section-title]
[help-key]h[/help-key]             Show this help modal
[help-key]r[/help-key]             Refresh git status and file tree
[help-key]q[/help-key]             Quit application

[help-section-title]💡 UI Layout[/help-section-title]
The right panel uses a tabbed layout for Unstaged and Staged changes.
Use the shortcuts above to quickly switch between tabs, or click them.
Staging/unstaging operations work from either tab.
        """
        return Static(help_text)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        # Check if this is the close button (any button in this modal is close)
        self.dismiss()

    def key(self, event) -> bool:
        """Handle key events in the modal."""
        if event.name == "escape":
            self.dismiss()
            return True
        return super().key(event)


class BranchSwitchModal(ModalScreen):
    """Modal screen for switching branches."""

    DEFAULT_CSS = """
    BranchSwitchModal {
        align: center middle;
    }
    
    #Container {
        border: solid #6c7086;
        background: #00122f;
        width: 50%;
        height: 50%;
        margin: 1;
        padding: 1;
    }
    
    OptionList {
        height: 1fr;
        border: solid #6c7086;
    }
    """

    def __init__(self, git_sidebar: GitStatusSidebar):
        super().__init__()
        self.git_sidebar = git_sidebar

    def compose(self) -> ComposeResult:
        """Create the modal content."""
        with Container():
            yield Static("Switch Branch", classes="panel-header")
            yield OptionList()
            with Horizontal():
                yield Button(
                    "Cancel", id="cancel-branch-switch", classes="cancel-button"
                )
                yield Button("Refresh", id="refresh-branches", classes="refresh-button")

    def on_mount(self) -> None:
        """Populate the branch list when the modal is mounted."""
        self.populate_branch_list()

    def populate_branch_list(self) -> None:
        """Populate the option list with all available branches."""
        try:
            option_list = self.query_one(OptionList)
            option_list.clear_options()

            # Get all branches
            branches = self.git_sidebar.get_all_branches()
            current_branch = self.git_sidebar.get_current_branch()

            # Add branches to the option list
            for branch in branches:
                if branch == current_branch:
                    option_list.add_option(Option(branch, id=branch, disabled=True))
                else:
                    option_list.add_option(Option(branch, id=branch))

        except Exception as e:
            self.app.notify(f"Error populating branches: {e}", severity="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses in the modal."""
        if event.button.id == "cancel-branch-switch":
            self.app.pop_screen()
        elif event.button.id == "refresh-branches":
            self.populate_branch_list()
            self.app.notify("Branch list refreshed", severity="information")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle branch selection."""
        branch_name = event.option.id

        if branch_name:
            # Check if repo is dirty before switching
            if self.git_sidebar.is_dirty():
                self.app.notify(
                    "Cannot switch branches with uncommitted changes. Please commit or discard changes first.",
                    severity="error",
                )
            else:
                # Attempt to switch branch
                success = self.git_sidebar.switch_branch(branch_name)
                if success:
                    self.app.notify(
                        f"Switched to branch: {branch_name}", severity="information"
                    )
                    # Refresh the UI
                    self.app.populate_file_tree()
                    self.app.populate_commit_history()
                    # Close the modal
                    self.app.pop_screen()
                else:
                    self.app.notify(
                        f"Failed to switch to branch: {branch_name}", severity="error"
                    )


class GitDiffViewer(App):
    """A Textual app for viewing git diffs with hunk-based staging in a three-panel UI."""

    TITLE = "Tentacle"
    CSS_PATH = "style.tcss"
    THEME = "tokyo-night"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("c", "commit", "Commit Staged Changes"),
        ("g", "gac_generate", "GAC Generate Message"),
        ("Ctrl+g", "gac_config", "Configure GAC"),
        ("h", "show_help", "Show Help"),
        ("a", "stage_all", "Stage All Changes"),
        ("x", "unstage_all", "Unstage All Changes"),
        ("r", "refresh_branches", "Refresh"),
        ("b", "show_branch_switcher", "Switch Branch"),
        ("s", "stage_selected_file", "Stage Selected File"),
        ("u", "unstage_selected_file", "Unstage Selected File"),
        ("p", "push_changes", "Push"),
        ("o", "pull_changes", "Pull"),
        ("1", "switch_to_unstaged", "Switch to Unstaged Tab"),
        ("2", "switch_to_staged", "Switch to Staged Tab"),
        ("3", "switch_to_graph", "Switch to Commit Graph"),
        ("ctrl+1", "switch_to_unstaged", "Switch to Unstaged Tab"),
        ("ctrl+2", "switch_to_staged", "Switch to Staged Tab"),
        ("ctrl+3", "switch_to_graph", "Switch to Commit Graph"),
    ]

    def __init__(self, repo_path: str = None):
        super().__init__()
        self.dark = True
        self.gac_integration = None
        self.git_sidebar = GitStatusSidebar(repo_path)
        self.gac_integration = GACIntegration(self.git_sidebar)
        self.current_file = None
        self.current_commit = None
        self.file_tree = None
        self.current_is_staged = None
        self._current_displayed_file = None
        self._current_displayed_is_staged = None

    def compose(self) -> ComposeResult:
        """Create the UI layout with three-panel view: file tree, diff view, and commit history."""
        yield Header()

        yield Horizontal(
            # Left panel - File tree
            Vertical(
                OctotuiLogo(),
                Static("File Tree", id="sidebar-header", classes="panel-header"),
                Tree(os.path.basename(os.getcwd()), id="file-tree"),
                id="sidebar",
            ),
            # Center panel - Tabbed diff view and commit history
            Vertical(GitDiffHistoryTabs(), id="diff-panel"),
            # Right panel - Git status functionality
            Vertical(
                # Tabbed content for Unstaged/Staged changes
                GitStatusTabs(),
                id="status-panel",
            ),
            id="main-content",
        )
        yield Footer()

    def on_mount(self) -> None:
        """Initialize the UI when app mounts."""
        self.populate_file_tree()
        self.populate_unstaged_changes()
        self.populate_staged_changes()
        self.populate_commit_history()
        self.ensure_commit_graph_mounted()
        
        # If no files are selected, show a message in the diff panel
        try:
            diff_content = self.query_one("#diff-content", VerticalScroll)
            if not diff_content.children:
                diff_content.mount(
                    Static(
                        "Select a file from the tree to view its diff", classes="info"
                    )
                )
        except Exception:
            pass
        try:
            history_content = self.query_one("#history-content", VerticalScroll)
            if not history_content.children:
                history_content.mount(
                    Static("No commit history available", classes="info")
                )
        except Exception:
            pass

    def populate_branch_dropdown(self) -> None:
        """Populate the branch dropdown with all available branches."""
        try:
            # Get the select widget
            branch_select = self.query_one("#branch-select", Select)

            # Get all branches
            branches = self.git_sidebar.get_all_branches()
            current_branch = self.git_sidebar.get_current_branch()

            # Create options for the select widget
            options = [(branch, branch) for branch in branches]

            # Set the options and default value
            branch_select.set_options(options)
            branch_select.value = current_branch

        except Exception:
            # If we can't populate branches, that's okay - continue without it
            pass

    def populate_file_tree(self) -> None:
        """Populate the file tree sidebar with all files and their git status."""
        if not self.git_sidebar.repo:
            return
            
        try:
            # Get the tree widget
            tree = self.query_one("#file-tree", Tree)
            
            # Clear existing tree
            tree.clear()
            
            # Automatically expand the root node
            tree.root.expand()
            
            # Get all files in the repository with their statuses
            file_data = self.git_sidebar.collect_file_data()
            file_tree = self.git_sidebar.get_file_tree()
            
            # Sort file_tree so directories are processed first
            file_tree.sort(key=lambda x: (x[1] != "directory", x[0]))
            
            # Keep track of created directory nodes to avoid duplicates
            directory_nodes = {"": tree.root}  # Empty string maps to root node
            
            # Add all files and directories
            for file_path, file_type, git_status in file_tree:
                parts = file_path.split('/')
                
                for i in range(len(parts)):
                    # For directories, we need to process all parts
                    # For files, we need to process all parts except the last one (handled separately)
                    if file_type == "directory" or i < len(parts) - 1:
                        parent_path = "/".join(parts[:i])
                        current_path = "/".join(parts[:i+1])
                        
                        # Create node if it doesn't exist
                        if current_path not in directory_nodes:
                            parent_node = directory_nodes[parent_path]
                            new_node = parent_node.add(parts[i], expand=True)
                            new_node.label.stylize("bold #bb9af7")  # Color directories with accent color
                            directory_nodes[current_path] = new_node
                
                # For files, add as leaf node under the appropriate directory
                if file_type == "file":
                    # Get the parent directory node
                    parent_dir_path = "/".join(parts[:-1])
                    parent_node = directory_nodes[parent_dir_path] if parent_dir_path else tree.root
                    
                    leaf_node = parent_node.add_leaf(parts[-1], data={"path": file_path, "status": git_status})
                    # Apply specific text colors based on git status
                    if git_status == "staged":
                        leaf_node.label.stylize("bold #9ece6a")
                    elif git_status == "modified":
                        leaf_node.label.stylize("bold #a9a1e1")
                    elif git_status == "untracked":
                        leaf_node.label.stylize("bold purple")
                    else:  # unchanged
                        leaf_node.label.stylize("default")
                
        except Exception as e:
            # Show error in diff panel
            try:
                diff_content = self.query_one("#diff-content", VerticalScroll)
                diff_content.remove_children()
                diff_content.mount(Static(f"Error populating file tree: {e}", classes="error"))
            except Exception:
                # If we can't even show the error, that's okay - just continue without it
                pass

    def action_show_branch_switcher(self) -> None:
        """Show the branch switcher modal."""
        modal = BranchSwitchModal(self.git_sidebar)
        self.push_screen(modal)

    def action_refresh_branches(self) -> None:
        """Refresh all git status components including file trees and commit history."""
        # Get fresh data from git
        file_data = self.git_sidebar.collect_file_data()

        # Refresh all components
        self.populate_file_tree()
        self.populate_unstaged_changes(file_data)
        self.populate_staged_changes(file_data)
        self.populate_branch_dropdown()
        self.populate_commit_history()
        
        # Also refresh the diff view if a file is currently selected
        if self.current_file:
            self.display_file_diff(
                self.current_file, self.current_is_staged, force_refresh=True
            )

    def action_quit(self) -> None:
        """Quit the application with a message."""
        self.exit("Thanks for using GitDiffViewer!")

    def on_unstaged_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle unstaged tree node selection to display file diffs."""
        node_data = event.node.data

        if node_data and isinstance(node_data, dict) and "path" in node_data:
            file_path = node_data["path"]
            self.current_file = file_path
            self.display_file_diff(file_path, is_staged=False)

    def on_staged_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle staged tree node selection to display file diffs."""
        node_data = event.node.data

        if node_data and isinstance(node_data, dict) and "path" in node_data:
            file_path = node_data["path"]
            self.current_file = file_path
            self.display_file_diff(file_path, is_staged=True)

    def on_unstaged_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        """Handle unstaged tree node highlighting to display file diffs."""
        node_data = event.node.data

        if node_data and isinstance(node_data, dict) and "path" in node_data:
            file_path = node_data["path"]
            self.current_file = file_path
            self.display_file_diff(file_path, is_staged=False)

    def on_staged_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        """Handle staged tree node highlighting to display file diffs."""
        node_data = event.node.data

        if node_data and isinstance(node_data, dict) and "path" in node_data:
            file_path = node_data["path"]
            self.current_file = file_path
            self.display_file_diff(file_path, is_staged=True)

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle tree node selection to display file diffs."""
        node_data = event.node.data

        if node_data and isinstance(node_data, dict) and "path" in node_data:
            file_path = node_data["path"]
            status = node_data.get("status", "unchanged")
            is_staged = status == "staged"
            self.current_file = file_path
            self.display_file_diff(file_path, is_staged)

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        """Handle tree node highlighting to display file diffs."""
        node_data = event.node.data

        if node_data and isinstance(node_data, dict) and "path" in node_data:
            file_path = node_data["path"]
            status = node_data.get("status", "unchanged")
            is_staged = status == "staged"
            self.current_file = file_path
            self.display_file_diff(file_path, is_staged)

    def _reverse_sanitize_path(self, sanitized_path: str) -> str:
        """Reverse the sanitization of a file path.

        Args:
            sanitized_path: The sanitized path with encoded characters

        Returns:
            The original file path
        """
        return (
            sanitized_path.replace("__SLASH__", "/")
            .replace("__SPACE__", " ")
            .replace("__DOT__", ".")
        )

    @staticmethod
    def _hunk_has_changes(hunk: Hunk) -> bool:
        """Return True when a hunk contains any staged or unstaged edits."""
        return any(
            (line and line[:1] in {"+", "-"}) for line in getattr(hunk, "lines", [])
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events for hunk operations and commit."""
        button_id = event.button.id

        if button_id and button_id.startswith("stage-hunk-"):
            # Extract hunk index and file path (ignoring the timestamp at the end)
            parts = button_id.split("-")
            if len(parts) >= 4:
                hunk_index = int(parts[2])
                # Join parts 3 through second-to-last (excluding timestamp)
                sanitized_file_path = "-".join(parts[3:-1])
                file_path = self._reverse_sanitize_path(sanitized_file_path)
                self.stage_hunk(file_path, hunk_index)

        elif button_id and button_id.startswith("unstage-hunk-"):
            # Extract hunk index and file path (ignoring the timestamp at the end)
            parts = button_id.split("-")
            if len(parts) >= 4:
                hunk_index = int(parts[2])
                # Join parts 3 through second-to-last (excluding timestamp)
                sanitized_file_path = "-".join(parts[3:-1])
                file_path = self._reverse_sanitize_path(sanitized_file_path)
                self.unstage_hunk(file_path, hunk_index)

        elif button_id and button_id.startswith("discard-hunk-"):
            # Extract hunk index and file path (ignoring the timestamp at the end)
            parts = button_id.split("-")
            if len(parts) >= 4:
                hunk_index = int(parts[2])
                # Join parts 3 through second-to-last (excluding timestamp)
                sanitized_file_path = "-".join(parts[3:-1])
                file_path = self._reverse_sanitize_path(sanitized_file_path)
                self.discard_hunk(file_path, hunk_index)

        elif button_id == "commit-button":
            self.action_commit()

        elif button_id == "gac-button":
            self.action_gac_generate()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle branch selection changes."""
        if event.select.id == "branch-select":
            branch_name = event.value
            if branch_name:
                # Check if repo is dirty before switching
                if self.git_sidebar.is_dirty():
                    self.notify(
                        "Cannot switch branches with uncommitted changes. Please commit or discard changes first.",
                        severity="error",
                    )
                    # Reset to current branch
                    current_branch = self.git_sidebar.get_current_branch()
                    event.select.value = current_branch
                else:
                    # Attempt to switch branch
                    success = self.git_sidebar.switch_branch(branch_name)
                    if success:
                        self.notify(
                            f"Switched to branch: {branch_name}", severity="information"
                        )
                        # Refresh the UI
                        self.populate_branch_dropdown()
                        self.populate_file_tree()
                        self.populate_commit_history()
                    else:
                        self.notify(
                            f"Failed to switch to branch: {branch_name}",
                            severity="error",
                        )
                        # Reset to current branch
                        current_branch = self.git_sidebar.get_current_branch()
                        event.select.value = current_branch
            
    def action_refresh_branches(self) -> None:
        """Refresh all git status components including file trees and commit history."""
        # Get fresh data from git
        file_data = self.git_sidebar.collect_file_data()
        
        # Refresh all components
        self.populate_file_tree()
        self.populate_unstaged_changes(file_data)
        self.populate_staged_changes(file_data)
        self.populate_branch_dropdown()
        self.populate_commit_history()
        
        # Also refresh the diff view if a file is currently selected
        if self.current_file:
            self.display_file_diff(self.current_file, self.current_is_staged, force_refresh=True)
        
    def populate_file_tree(self) -> None:
        """Populate the file tree sidebar with all files and their git status."""
        if not self.git_sidebar.repo:
            return

        try:
            # Get the tree widget
            tree = self.query_one("#file-tree", Tree)

            # Clear existing tree
            tree.clear()

            # Automatically expand the root node
            tree.root.expand()

            # Get all files in the repository with their statuses
            file_tree = self.git_sidebar.get_file_tree()

            # Sort file_tree so directories are processed first
            file_tree.sort(key=lambda x: (x[1] != "directory", x[0]))

            # Keep track of created directory nodes to avoid duplicates
            directory_nodes = {"": tree.root}  # Empty string maps to root node

            # Add all files and directories
            for file_path, file_type, git_status in file_tree:
                parts = file_path.split("/")

                for i in range(len(parts)):
                    # For directories, we need to process all parts
                    # For files, we need to process all parts except the last one (handled separately)
                    if file_type == "directory" or i < len(parts) - 1:
                        parent_path = "/".join(parts[:i])
                        current_path = "/".join(parts[: i + 1])

                        # Create node if it doesn't exist
                        if current_path not in directory_nodes:
                            parent_node = directory_nodes[parent_path]
                            new_node = parent_node.add(parts[i], expand=True)
                            new_node.label.stylize(
                                "bold #bb9af7"
                            )  # Color directories with accent color
                            directory_nodes[current_path] = new_node

                # For files, add as leaf node under the appropriate directory
                if file_type == "file":
                    # Get the parent directory node
                    parent_dir_path = "/".join(parts[:-1])
                    parent_node = (
                        directory_nodes[parent_dir_path]
                        if parent_dir_path
                        else tree.root
                    )

                    leaf_node = parent_node.add_leaf(
                        parts[-1], data={"path": file_path, "status": git_status}
                    )
                    # Apply specific text colors based on git status
                    if git_status == "staged":
                        leaf_node.label.stylize("bold #9ece6a")
                    elif git_status == "modified":
                        leaf_node.label.stylize("bold #a9a1e1")
                    elif git_status == "untracked":
                        leaf_node.label.stylize("bold purple")
                    else:  # unchanged
                        leaf_node.label.stylize("default")

        except Exception as e:
            # Show error in diff panel
            try:
                diff_content = self.query_one("#diff-content", VerticalScroll)
                diff_content.remove_children()
                diff_content.mount(
                    Static(f"Error populating file tree: {e}", classes="error")
                )
            except Exception:
                # If we can't even show the error, that's okay - just continue without it
                pass

    def populate_unstaged_changes(self, file_data: Optional[Dict] = None) -> None:
        """Populate the unstaged changes tree in the right sidebar."""
        if not self.git_sidebar.repo:
            return

        file_data = file_data or self.git_sidebar.collect_file_data()
        try:
            # Get the unstaged tree widget
            tree = self.query_one("#unstaged-tree", Tree)

            # Clear existing tree
            tree.clear()

            # Automatically expand the root node
            tree.root.expand()

            # Use pre-fetched unstaged files
            unstaged_files = file_data["unstaged_files"]
            untracked_files = set(file_data["untracked_files"])

            # Sort unstaged_files so directories are processed first
            unstaged_files.sort()

            # Keep track of created directory nodes to avoid duplicates
            directory_nodes = {"": tree.root}  # Empty string maps to root node

            # Add unstaged files to tree with directory structure
            for file_path in unstaged_files:
                parts = file_path.split("/")
                file_name = parts[-1]

                # Determine file status from pre-fetched data
                status = "untracked" if file_path in untracked_files else "modified"

                # Build intermediate directory nodes as needed
                for i in range(len(parts) - 1):
                    parent_path = "/".join(parts[:i])
                    current_path = "/".join(parts[: i + 1])

                    # Create node if it doesn't exist
                    if current_path not in directory_nodes:
                        parent_node = directory_nodes[parent_path]
                        new_node = parent_node.add(parts[i], expand=True)
                        new_node.label.stylize(
                            "bold #bb9af7"
                        )  # Color directories with accent color
                        directory_nodes[current_path] = new_node

                # Add file as leaf node under the appropriate directory
                parent_dir_path = "/".join(parts[:-1])
                parent_node = (
                    directory_nodes[parent_dir_path] if parent_dir_path else tree.root
                )

                leaf_node = parent_node.add_leaf(
                    file_name, data={"path": file_path, "status": status}
                )

                # Apply styling based on status
                if status == "modified":
                    leaf_node.label.stylize("bold #a9a1e1")
                else:  # untracked
                    leaf_node.label.stylize("bold purple")

        except Exception as e:
            # Show error in diff panel
            try:
                diff_content = self.query_one("#diff-content", VerticalScroll)
                diff_content.remove_children()
                diff_content.mount(
                    Static(f"Error populating unstaged changes: {e}", classes="error")
                )
            except Exception:
                pass

    def populate_staged_changes(self, file_data: Optional[Dict] = None) -> None:
        """Populate the staged changes tree in the right sidebar."""
        if not self.git_sidebar.repo:
            return

        file_data = file_data or self.git_sidebar.collect_file_data()
        try:
            # Get the staged tree widget
            tree = self.query_one("#staged-tree", Tree)

            # Clear existing tree
            tree.clear()

            # Automatically expand the root node
            tree.root.expand()

            # Use pre-fetched staged files
            staged_files = file_data["staged_files"]

            # Sort staged_files so directories are processed first
            staged_files.sort()

            # Keep track of created directory nodes to avoid duplicates
            directory_nodes = {"": tree.root}  # Empty string maps to root node

            # Add staged files with directory structure
            for file_path in staged_files:
                parts = file_path.split("/")
                file_name = parts[-1]

                # Build intermediate directory nodes as needed
                for i in range(len(parts) - 1):
                    parent_path = "/".join(parts[:i])
                    current_path = "/".join(parts[: i + 1])

                    # Create node if it doesn't exist
                    if current_path not in directory_nodes:
                        parent_node = directory_nodes[parent_path]
                        new_node = parent_node.add(parts[i], expand=True)
                        new_node.label.stylize(
                            "bold #bb9af7"
                        )  # Color directories with accent color
                        directory_nodes[current_path] = new_node

                # Add file as leaf node under the appropriate directory
                parent_dir_path = "/".join(parts[:-1])
                parent_node = (
                    directory_nodes[parent_dir_path] if parent_dir_path else tree.root
                )

                leaf_node = parent_node.add_leaf(
                    file_name, data={"path": file_path, "status": "staged"}
                )
                leaf_node.label.stylize("bold #9ece6a")

        except Exception as e:
            # Show error in diff panel
            try:
                diff_content = self.query_one("#diff-content", VerticalScroll)
                diff_content.remove_children()
                diff_content.mount(
                    Static(f"Error populating staged changes: {e}", classes="error")
                )
            except Exception:
                pass

    def stage_hunk(self, file_path: str, hunk_index: int) -> None:
        """Stage a specific hunk of a file."""
        try:
            success = self.git_sidebar.stage_hunk(file_path, hunk_index)

            if success:
                # Clear any cached diff state
                if hasattr(self, "_current_displayed_file"):
                    delattr(self, "_current_displayed_file")
                if hasattr(self, "_current_displayed_is_staged"):
                    delattr(self, "_current_displayed_is_staged")

                # Refresh tree states with latest git data
                file_data = self.git_sidebar.collect_file_data()
                self.populate_unstaged_changes(file_data)
                self.populate_staged_changes(file_data)

                # Refresh only the diff view for the current file
                if self.current_file:
                    self.display_file_diff(
                        self.current_file, self.current_is_staged, force_refresh=True
                    )

                # Schedule a background refresh of file trees (non-blocking)
                self.call_later(self._refresh_trees_async)
            else:
                self.notify(f"Failed to stage {file_path}", severity="error")

        except Exception as e:
            self.notify(f"Error staging hunk: {e}", severity="error")

    def stage_file(self, file_path: str) -> None:
        """Stage all changes in a file."""
        try:
            success = self.git_sidebar.stage_file(file_path)
            if success:
                # Refresh trees
                # Refresh diff view for the staged file
                self.display_file_diff(file_path, is_staged=True, force_refresh=True)
            else:
                self.notify(
                    f"Failed to stage all changes in {file_path}", severity="error"
                )
        except Exception as e:
            self.notify(f"Error staging file: {e}", severity="error")

    def unstage_hunk(self, file_path: str, hunk_index: int) -> None:
        """Unstage a specific hunk of a file."""
        try:
            success = self.git_sidebar.unstage_hunk(file_path, hunk_index)

            if success:
                # Refresh tree states with latest git data
                file_data = self.git_sidebar.collect_file_data()
                self.populate_unstaged_changes(file_data)
                self.populate_staged_changes(file_data)

                # Refresh only the diff view for the current file
                if self.current_file:
                    self.display_file_diff(
                        self.current_file, self.current_is_staged, force_refresh=True
                    )

                # Schedule a background refresh of file trees (non-blocking)
                self.call_later(self._refresh_trees_async)
            else:
                self.notify(f"Failed to unstage {file_path}", severity="error")

        except Exception as e:
            self.notify(f"Error unstaging hunk: {e}", severity="error")

    def discard_hunk(self, file_path: str, hunk_index: int) -> None:
        """Discard changes in a specific hunk of a file."""
        try:
            success = self.git_sidebar.discard_hunk(file_path, hunk_index)

            if success:
                # Clear any cached diff state
                if hasattr(self, "_current_displayed_file"):
                    delattr(self, "_current_displayed_file")
                if hasattr(self, "_current_displayed_is_staged"):
                    delattr(self, "_current_displayed_is_staged")

                # Refresh tree states with latest git data
                file_data = self.git_sidebar.collect_file_data()
                self.populate_unstaged_changes(file_data)
                self.populate_staged_changes(file_data)

                # Refresh only the diff view
                if self.current_file:
                    self.display_file_diff(
                        self.current_file, self.current_is_staged, force_refresh=True
                    )

                # Schedule a background refresh of file trees (non-blocking)
                self.call_later(self._refresh_trees_async)
            else:
                self.notify(
                    f"Failed to discard changes in {file_path}", severity="error"
                )

        except Exception as e:
            self.notify(f"Error discarding hunk: {e}", severity="error")

    def _refresh_trees_async(self) -> None:
        """Background refresh of file trees to avoid blocking UI during hunk operations."""
        try:
            # Check if we have recently modified files to optimize the refresh
            if self.git_sidebar.has_recent_modifications():
                # For now, still do full refresh but in background
                # Future optimization: only update nodes for modified files
                self.populate_file_tree()
                self.populate_unstaged_changes()
                self.populate_staged_changes()
            else:
                # No recent changes, skip expensive operations
                pass
        except Exception:
            # Silently fail background operations to avoid disrupting user experience
            pass

    def populate_commit_history(self) -> None:
        """Populate the commit history tab."""
        try:
            history_content = self.query_one("#history-content", VerticalScroll)
            history_content.remove_children()

            branch_name = self.git_sidebar.get_current_branch()
            commits = self.git_sidebar.get_commit_history()

            for commit in commits:
                # Display branch, commit ID, author, and message with colors that match our theme
                commit_text = f"[#87CEEB]{branch_name}[/#87CEEB] [#E0FFFF]{commit.sha}[/#E0FFFF] [#00BFFF]{commit.author}[/#00BFFF]: {commit.message}"
                commit_line = CommitLine(commit_text, classes="info")
                history_content.mount(commit_line)

        except Exception:
            pass
            

            
    def display_file_diff(self, file_path: str, is_staged: bool = False, force_refresh: bool = False) -> None:
        """Display the diff for a selected file in the diff panel with appropriate buttons."""
        # Skip if this is the same file we're already displaying (unless force_refresh is True)
        if (
            not force_refresh
            and hasattr(self, "_current_displayed_file")
            and self._current_displayed_file == file_path
            and self._current_displayed_is_staged == is_staged
        ):
            return
        self.current_is_staged = is_staged

        try:
            diff_content = self.query_one("#diff-content", VerticalScroll)
            # Ensure we're starting with a clean slate
            diff_content.remove_children()

            # Track which file we're currently displaying
            self._current_displayed_file = file_path
            self._current_displayed_is_staged = is_staged

            # Get file status to determine which buttons to show
            hunks = self.git_sidebar.get_diff_hunks(file_path, staged=is_staged)

            if not hunks:
                diff_content.mount(Static("No changes to display", classes="info"))
                return

            # Generate a unique timestamp for this refresh to avoid ID collisions
            refresh_id = str(int(time.time() * 1000000))  # microsecond timestamp

            repo_root = getattr(self.git_sidebar, "repo_path", Path.cwd())
            markdown_config = DiffMarkdownConfig(
                repo_root=repo_root,
                prefer_diff_language=False,
                show_headers=False,
            )

            # Display each hunk
            for i, hunk in enumerate(hunks):
                hunk_header = Static(hunk.header, classes="hunk-header")

                markdown_widget = DiffMarkdown(
                    file_path=file_path,
                    hunks=[hunk],
                    config=markdown_config,
                )
                markdown_widget.add_class("diff-markdown")

                sanitized_file_path = (
                    file_path.replace("/", "__SLASH__")
                    .replace(" ", "__SPACE__")
                    .replace(".", "__DOT__")
                )
                hunk_children = [hunk_header, markdown_widget]

                if self._hunk_has_changes(hunk):
                    if is_staged:
                        hunk_children.append(
                            Horizontal(
                                Button(
                                    "Unstage",
                                    id=f"unstage-hunk-{i}-{sanitized_file_path}-{refresh_id}",
                                    classes="unstage-button",
                                ),
                                classes="hunk-buttons",
                            )
                        )
                    else:
                        hunk_children.append(
                            Horizontal(
                                Button(
                                    "Stage",
                                    id=f"stage-hunk-{i}-{sanitized_file_path}-{refresh_id}",
                                    classes="stage-button",
                                ),
                                Button(
                                    "Discard",
                                    id=f"discard-hunk-{i}-{sanitized_file_path}-{refresh_id}",
                                    classes="discard-button",
                                ),
                                classes="hunk-buttons",
                            )
                        )

                hunk_container = Container(
                    *hunk_children,
                    id=f"{'staged' if is_staged else 'unstaged'}-hunk-{i}-{sanitized_file_path}-{refresh_id}",
                    classes="hunk-container",
                )

                diff_content.mount(hunk_container)

        except Exception as e:
            self.notify(f"Error displaying diff: {e}", severity="error")

    def action_commit(self) -> None:
        """Commit staged changes with a commit message from the UI."""
        try:
            # Get the commit message input widgets
            commit_input = self.query_one("#commit-message", Input)
            commit_body = self.query_one("#commit-body", TextArea)

            subject = commit_input.value.strip()
            body = commit_body.text.strip()

            # Combine subject and body for full commit message
            message = subject
            if body:
                message = f"{subject}\n\n{body}"

            # Check if there's a commit message
            if not subject:
                self.notify("Please enter a commit message", severity="warning")
                return

            # Check if there are staged changes
            staged_files = self.git_sidebar.get_staged_files()
            if not staged_files:
                self.notify("No staged changes to commit", severity="warning")
                return

            # Attempt to commit staged changes
            success = self.git_sidebar.commit_staged_changes(message)

            if success:
                self.notify(
                    f"Successfully committed changes with message: {message}",
                    severity="information",
                )
                # Clear the commit message inputs
                commit_input.value = ""
                commit_body.text = ""

                # Rebuild tree states with latest git data
                file_data = self.git_sidebar.collect_file_data()
                self.populate_file_tree()
                self.populate_unstaged_changes(file_data)
                self.populate_staged_changes(file_data)

                # Refresh the diff and commit history views
                if self.current_file:
                    self.display_file_diff(
                        self.current_file, self.current_is_staged, force_refresh=True
                    )
                self.populate_commit_history()
            else:
                self.notify("Failed to commit changes", severity="error")

        except Exception as e:
            self.notify(f"Error committing changes: {e}", severity="error")

    def action_push_changes(self) -> None:
        """Push the current branch to its remote."""
        try:
            success, message = self.git_sidebar.push_current_branch()
            if success:
                self.notify(f"🚀 {message}", severity="information")
            else:
                self.notify(message, severity="error")
        except Exception as e:
            self.notify(f"Push blew up: {e}", severity="error")

    def action_pull_changes(self) -> None:
        """Pull the latest changes for the current branch."""
        try:
            success, message = self.git_sidebar.pull_current_branch()
            if success:
                self.notify(f"📥 {message}", severity="information")
                # Refresh trees and history to reflect new changes
                file_data = self.git_sidebar.collect_file_data()
                self.populate_file_tree()
                self.populate_unstaged_changes(file_data)
                self.populate_staged_changes(file_data)
                self.populate_commit_history()
                if self.current_file:
                    self.display_file_diff(
                        self.current_file, self.current_is_staged, force_refresh=True
                    )
            else:
                self.notify(message, severity="error")
        except Exception as e:
            self.notify(f"Pull imploded: {e}", severity="error")

    def action_gac_config(self) -> None:
        """Show GAC configuration modal."""

        def handle_config_result(result):
            # Refresh GAC integration after config changes
            self.gac_integration = GACIntegration(self.git_sidebar)

        self.push_screen(GACConfigModal(), handle_config_result)

    def action_stage_selected_file(self) -> None:
        """Stage the entire currently selected file from any file tree if it is unstaged/untracked."""
        try:
            if not self.current_file:
                self.notify("No file selected", severity="warning")
                return
            status = self.git_sidebar.get_file_status(self.current_file)
            # Allow staging even if file is partially staged; block only if unchanged
            if "unchanged" in status:
                self.notify("Selected file has no changes", severity="information")
                return

            # Perform the staging operation
            success = self.git_sidebar.stage_file(self.current_file)
            if success:
                # Use the comprehensive refresh function
                self.action_refresh_branches()
                # Also refresh diff view for the staged file
                self.display_file_diff(
                    self.current_file, is_staged=True, force_refresh=True
                )
            else:
                self.notify(
                    f"Failed to stage all changes in {self.current_file}",
                    severity="error",
                )
        except Exception as e:
            self.notify(f"Error staging selected file: {e}", severity="error")

    def action_unstage_selected_file(self) -> None:
        """Unstage all changes for the selected file (if staged)."""
        try:
            if not self.current_file:
                self.notify("No file selected", severity="warning")
                return
            status = self.git_sidebar.get_file_status(self.current_file)
            if "staged" not in status:
                self.notify("Selected file is not staged", severity="information")
                return

            # Perform the unstaging operation
            if hasattr(self.git_sidebar, "unstage_file_all") and callable(
                self.git_sidebar.unstage_file_all
            ):
                success = self.git_sidebar.unstage_file_all(self.current_file)
            else:
                # Fallback: remove entire file from index
                success = self.git_sidebar.unstage_file(self.current_file)

            if success:
                # Use the comprehensive refresh function
                self.action_refresh_branches()
                # Also refresh diff view to show unstaged changes
                if self.current_file:
                    self.display_file_diff(
                        self.current_file, is_staged=False, force_refresh=True
                    )
            else:
                self.notify(f"Failed to unstage {self.current_file}", severity="error")
        except Exception as e:
            self.notify(f"Error unstaging selected file: {e}", severity="error")

    def action_show_help(self) -> None:
        """Show the help modal with keybindings."""
        try:
            help_modal = HelpModal()
            self.push_screen(help_modal)
        except Exception as e:
            self.notify(f"Error showing help: {e}", severity="error")

    def action_stage_all(self) -> None:
        """Stage all unstaged changes."""
        try:
            success, message = self.git_sidebar.stage_all_changes()
            if success:
                # Refresh UI
                self.populate_file_tree()
                if self.current_file:
                    self.display_file_diff(
                        self.current_file, is_staged=True, force_refresh=True
                    )
            else:
                self.notify(message, severity="error")
        except Exception as e:
            self.notify(f"Error staging all changes: {e}", severity="error")

    def action_unstage_all(self) -> None:
        """Unstage all staged changes."""
        try:
            success, message = self.git_sidebar.unstage_all_changes()
            if success:
                # Refresh UI
                self.populate_file_tree()
                if self.current_file:
                    self.display_file_diff(
                        self.current_file, is_staged=False, force_refresh=True
                    )
            else:
                self.notify(message, severity="error")
        except Exception as e:
            self.notify(f"Error unstaging all changes: {e}", severity="error")

    def action_switch_to_unstaged(self) -> None:
        """Switch to the Unstaged Changes tab."""
        try:
            status_tabs = self.query_one("#status-tabs", TabbedContent)
            status_tabs.active = "unstaged-tab"
        except Exception as e:
            self.notify(f"Error switching to unstaged tab: {e}", severity="error")

    def action_switch_to_staged(self) -> None:
        """Switch to the Staged Changes tab."""
        try:
            status_tabs = self.query_one("#status-tabs", TabbedContent)
            status_tabs.active = "staged-tab"
        except Exception as e:
            self.notify(f"Error switching to staged tab: {e}", severity="error")
    
    def ensure_commit_graph_mounted(self) -> None:
        """Ensure the CommitGraphWidget is mounted into the graph container once.

        This is idempotent and safe to call multiple times. It gracefully
        handles missing/invalid repos (e.g. during merge conflicts or in
        non-git directories) by showing a friendly message instead of dying.
        """
        try:
            container = self.query_one("#graph-container", Container)
        except Exception:
            return

        # If graph already mounted, do nothing
        if any(isinstance(child, CommitGraphWidget) for child in container.children):
            return

        # If repo is unavailable, show a message
        if not self.git_sidebar or not self.git_sidebar.repo:
            if not container.children:
                container.mount(Static("No git repository detected", classes="info"))
            return

        try:
            graph = CommitGraphWidget(self.git_sidebar.repo)
            container.mount(graph)
        except Exception as e:
            # Fail gracefully; don't break the rest of the UI
            container.mount(
                Static(f"Error loading commit graph: {e}", classes="error")
            )

    def action_switch_to_graph(self) -> None:
        """Switch to the Commit Graph tab and ensure graph is mounted."""
        try:
            self.ensure_commit_graph_mounted()
            tabbed_content = self.query(TabbedContent)
            for tabs in tabbed_content:
                try:
                    if tabs.query_one("#graph-tab", TabPane):
                        tabs.active = "graph-tab"
                        break
                except Exception:
                    continue
        except Exception as e:
            self.notify(f"Error switching to graph tab: {e}", severity="error")

    def action_gac_generate(self) -> None:
        """Generate commit message using GAC and populate the commit message fields (no auto-commit)."""
        try:
            if not self.gac_integration.is_configured():
                self.notify(
                    "🤖 GAC is not configured. Press Ctrl+G to configure it first.",
                    severity="warning",
                )
                return

            # Check if there are staged changes
            staged_files = self.git_sidebar.get_staged_files()
            if not staged_files:
                self.notify(
                    "No staged changes to generate commit message for",
                    severity="warning",
                )
                return

            # Show generating message
            self.notify(
                "🤖 Generating commit message with GAC...", severity="information"
            )

            # Generate commit message
            try:
                commit_message = self.gac_integration.generate_commit_message(
                    staged_only=True, one_liner=False
                )

                if commit_message:
                    # Parse the commit message into subject and body
                    lines = commit_message.strip().split("\n", 1)
                    subject = lines[0].strip()
                    body = lines[1].strip() if len(lines) > 1 else ""

                    # Populate the commit message inputs
                    try:
                        commit_input = self.query_one("#commit-message", Input)
                        commit_body = self.query_one("#commit-body", TextArea)

                        commit_input.value = subject
                        commit_body.text = body

                        self.notify(
                            f"✅ GAC generated commit message: {subject[:50]}...",
                            severity="information",
                        )

                    except Exception as e:
                        self.notify(
                            f"Generated message but failed to populate fields: {e}",
                            severity="warning",
                        )
                else:
                    self.notify(
                        "❌ GAC failed to generate a commit message", severity="error"
                    )

            except Exception as e:
                self.notify(
                    f"❌ Failed to generate commit message: {e}", severity="error"
                )

        except Exception as e:
            self.notify(f"❌ Error with GAC integration: {e}", severity="error")

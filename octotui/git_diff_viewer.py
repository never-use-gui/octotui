from pathlib import Path
from textual.app import App, ComposeResult
from textual.widgets import (
    Static,
    Button,
    Label,
    Input,
    TabbedContent,
    TabPane,
    Select,
    TextArea,
)
from textual.containers import Horizontal, Vertical, Container, VerticalScroll
from octotui.git_status_sidebar import GitStatusSidebar, Hunk
from octotui.gac_integration import GACIntegration
from octotui.gac_config_modal import GACConfigModal
from octotui.diff_markdown import DiffMarkdown, DiffMarkdownConfig
from octotui.commit_graph import CommitGraphWidget
from octotui.octotui_logo import OctotuiLogo
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
        with TabbedContent(id="main-tabs"):
            with TabPane("Diff View", id="diff-tab"):
                yield VerticalScroll(id="diff-content")
            with TabPane("Commit Graph", id="graph-tab"):
                # Commit graph will be mounted here dynamically when tab is shown
                yield Container(id="graph-container")
            with TabPane("Commit History", id="history-tab"):
                yield VerticalScroll(id="history-content")
            with TabPane("Commit Message", id="commit-tab"):
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
[help-key]←/→[/help-key]          Navigate through files (previous/next)
[help-key]Tab[/help-key]           Cycle through hunk buttons (Stage/Discard/Unstage)
[help-key]Enter[/help-key]         Press the currently focused button

[help-section-title]📑 View Switching[/help-section-title]
[help-key]1 or Ctrl+1[/help-key]  View Unstaged files
[help-key]2 or Ctrl+2[/help-key]  View Staged files
[help-key]3 or Ctrl+3[/help-key]  View Commit Graph

[help-section-title]🔄 Git Operations[/help-section-title]
[help-key]s[/help-key]             Stage current file
[help-key]u[/help-key]             Unstage current file
[help-key]a[/help-key]             Stage ALL unstaged changes
[help-key]x[/help-key]             Unstage ALL staged changes
[help-key]c[/help-key]             Commit staged changes

[help-section-title]🌿 Branch Management[/help-section-title]
[help-key]b[/help-key]             Show branch switcher
[help-key]r[/help-key]             Refresh

[help-section-title]📡 Remote Operations[/help-section-title]
[help-key]p[/help-key]             Push current branch
[help-key]o[/help-key]             Pull latest changes

[help-section-title]🤖 AI Integration (GAC)[/help-section-title]
[help-key]Ctrl+G[/help-key]        Configure GAC (21+ providers supported)
[help-key]g[/help-key]             Generate commit message with AI

GAC supports OpenAI, Anthropic, Gemini, Mistral, Cohere, DeepSeek,
Groq, Together, Cerebras, OpenRouter, xAI, Ollama, and more!

[help-section-title]⚙️ Application[/help-section-title]
[help-key]h[/help-key]             Show this help modal
[help-key]q[/help-key]             Quit application

[help-section-title]💡 Status Bar[/help-section-title]
The bottom status bar shows:
• Current view mode (STAGED/UNSTAGED)
• Current file name
• File position (e.g., 3/10)
• Counts of staged and unstaged files
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
                    # Refresh the UI with new navigation
                    self.app.build_file_list()
                    self.app.populate_commit_history()
                    if self.app.file_list:
                        self.app._navigate_to_current_file()
                    else:
                        self.app.update_status_bar()
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
        ("c", "show_commit_tab", "Commit"),
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
        ("1", "switch_to_unstaged", "View Unstaged"),
        ("2", "switch_to_staged", "View Staged"),
        ("3", "switch_to_graph", "Switch to Commit Graph"),
        ("ctrl+1", "switch_to_unstaged", "View Unstaged"),
        ("ctrl+2", "switch_to_staged", "View Staged"),
        ("ctrl+3", "switch_to_graph", "Switch to Commit Graph"),
        ("left", "prev_file", "← Prev"),
        ("right", "next_file", "→ Next"),
        ("enter", "fire_focused_button", "Select"),
        ("tab", "cycle_buttons", "Cycle Buttons"),
    ]

    def __init__(self, repo_path: str | None = None):
        super().__init__()
        self.dark = True
        self.git_sidebar = GitStatusSidebar(repo_path)
        self.gac_integration = GACIntegration(self.git_sidebar)
        self.current_file: str | None = None
        self.current_commit: str | None = None
        self.current_is_staged: bool | None = None
        self._current_displayed_file: str | None = None
        self._current_displayed_is_staged: bool | None = None
        # Navigation state
        self.file_list: list[tuple[str, bool]] = []  # (file_path, is_staged)
        self.current_file_index: int = 0
        self.viewing_staged: bool = False  # False = viewing unstaged files
        self.focused_button_index: int = 0  # For Tab cycling through buttons

    def compose(self) -> ComposeResult:
        """Create the UI layout with full-width diff panel and status bar."""
        yield OctotuiLogo()
        yield GitDiffHistoryTabs()
        yield Static("", id="status-bar", markup=True)

    def on_mount(self) -> None:
        """Initialize the UI when app mounts."""
        self.populate_commit_history()
        self.ensure_commit_graph_mounted()
        
        # Build file list and navigate to first file
        self.build_file_list()
        if self.file_list:
            self._navigate_to_current_file()
        else:
            self.update_status_bar()
            # Show message in diff panel if no files
            try:
                diff_content = self.query_one("#diff-content", VerticalScroll)
                if not diff_content.children:
                    diff_content.mount(
                        Static(
                            "No changes to display. Use ←/→ to navigate files, 1/2 to switch views.",
                            classes="info",
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

    def build_file_list(self) -> None:
        """Build the list of files to navigate through based on current view mode."""
        self.file_list = []
        if not self.git_sidebar.repo:
            return
        
        try:
            file_data = self.git_sidebar.collect_file_data()
            
            if self.viewing_staged:
                # Get staged files
                staged_files = file_data.get("staged_files", [])
                for file_path in sorted(staged_files):
                    self.file_list.append((file_path, True))
            else:
                # Get unstaged files (modified + untracked)
                unstaged_files = file_data.get("unstaged_files", [])
                for file_path in sorted(unstaged_files):
                    self.file_list.append((file_path, False))
        except Exception:
            self.file_list = []

    def update_status_bar(self) -> None:
        """Update the status bar with current navigation state."""
        try:
            status_bar = self.query_one("#status-bar", Static)
            
            # Get file counts
            file_data = self.git_sidebar.collect_file_data()
            staged_count = len(file_data.get("staged_files", []))
            unstaged_count = len(file_data.get("unstaged_files", []))
            
            # Build status bar content
            view_mode = "STAGED" if self.viewing_staged else "UNSTAGED"
            view_icon = "◀" if self.viewing_staged else "▶"
            
            if self.file_list:
                file_path, _ = self.file_list[self.current_file_index]
                file_name = file_path.split("/")[-1] if "/" in file_path else file_path
                file_index = f"{self.current_file_index + 1}/{len(self.file_list)}"
                
                status_text = (
                    f"{view_icon} [bold #bb9af7]{view_mode}[/] {view_icon} │ "
                    f"[#c0caf5]{file_name}[/] │ {file_index} │ "
                    f"[#9ece6a]■ {staged_count} staged[/]  [#a9a1e1]○ {unstaged_count} unstaged[/]"
                )
            else:
                status_text = (
                    f"{view_icon} [bold #bb9af7]{view_mode}[/] {view_icon} │ "
                    f"[dim]No files[/] │ "
                    f"[#9ece6a]■ {staged_count} staged[/]  [#a9a1e1]○ {unstaged_count} unstaged[/]"
                )
            
            status_bar.update(status_text)
        except Exception:
            pass

    def get_current_buttons(self) -> list[Button]:
        """Get all action buttons in the current diff view."""
        try:
            diff_content = self.query_one("#diff-content", VerticalScroll)
            buttons = list(diff_content.query(Button))
            # Filter to only stage/unstage/discard buttons
            action_buttons = [
                btn for btn in buttons 
                if btn.id and (
                    btn.id.startswith("stage-hunk-") or 
                    btn.id.startswith("unstage-hunk-") or 
                    btn.id.startswith("discard-hunk-")
                )
            ]
            return action_buttons
        except Exception:
            return []

    def _navigate_to_current_file(self) -> None:
        """Display the current file and update status bar."""
        if self.file_list:
            file_path, is_staged = self.file_list[self.current_file_index]
            self.current_file = file_path
            self.current_is_staged = is_staged
            self.display_file_diff(file_path, is_staged, force_refresh=True)
            # Reset focused button index when navigating to new file
            self.focused_button_index = 0
            self._update_button_focus()
        self.update_status_bar()

    def _update_button_focus(self) -> None:
        """Update visual focus on buttons."""
        buttons = self.get_current_buttons()
        if buttons:
            self.focused_button_index = min(self.focused_button_index, len(buttons) - 1)
        for i, btn in enumerate(buttons):
            if i == self.focused_button_index:
                btn.add_class("button-focused")
            else:
                btn.remove_class("button-focused")

    def action_prev_file(self) -> None:
        """Navigate to previous file."""
        if not self.file_list:
            return
        self.current_file_index = (self.current_file_index - 1) % len(self.file_list)
        self._navigate_to_current_file()

    def action_next_file(self) -> None:
        """Navigate to next file."""
        if not self.file_list:
            return
        self.current_file_index = (self.current_file_index + 1) % len(self.file_list)
        self._navigate_to_current_file()

    def action_cycle_buttons(self) -> None:
        """Cycle through Stage/Discard/Unstage buttons on current hunk."""
        buttons = self.get_current_buttons()
        if not buttons:
            return
        self.focused_button_index = (self.focused_button_index + 1) % len(buttons)
        self._update_button_focus()

    def action_fire_focused_button(self) -> None:
        """Fire the currently focused button (Stage/Discard/Unstage)."""
        buttons = self.get_current_buttons()
        if not buttons:
            return  # Silently return - no buttons to press
        if 0 <= self.focused_button_index < len(buttons):
            buttons[self.focused_button_index].press()

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

    def action_show_branch_switcher(self) -> None:
        """Show the branch switcher modal."""
        modal = BranchSwitchModal(self.git_sidebar)
        self.push_screen(modal)

    def action_refresh_branches(self) -> None:
        """Refresh all git status components and commit history."""
        # Rebuild file list
        self.build_file_list()
        self.populate_branch_dropdown()
        self.populate_commit_history()
        
        # Refresh the view
        if self.file_list:
            self._navigate_to_current_file()
        else:
            self.update_status_bar()
        
        self.notify("Refreshed", severity="information")

    def action_quit(self) -> None:
        """Quit the application with a message."""
        self.exit("Thanks for using GitDiffViewer!")

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
                        self.build_file_list()
                        self.current_file_index = 0
                        if self.file_list:
                            self._navigate_to_current_file()
                        else:
                            self.update_status_bar()
                        self.populate_commit_history()
                    else:
                        self.notify(
                            f"Failed to switch to branch: {branch_name}",
                            severity="error",
                        )
                        # Reset to current branch
                        current_branch = self.git_sidebar.get_current_branch()
                        event.select.value = current_branch

    def stage_hunk(self, file_path: str, hunk_index: int) -> None:
        """Stage a specific hunk of a file."""
        try:
            success = self.git_sidebar.stage_hunk(file_path, hunk_index)

            # Clear any cached diff state regardless of success
            self._current_displayed_file = None
            self._current_displayed_is_staged = None

            # Invalidate git cache to get fresh state
            self.git_sidebar._invalidate_cache()

            if success:
                self.notify(f"Staged hunk in {file_path}", severity="information")
            else:
                # Staging failed - might be already staged or hunk changed
                self.notify("Could not stage hunk (may already be staged)", severity="warning")

            # Regardless of success/failure, rebuild file list and check if we should advance
            old_file = self.current_file
            self.build_file_list()
            self._stay_on_file_or_advance(old_file)

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

            # Clear any cached diff state regardless of success
            self._current_displayed_file = None
            self._current_displayed_is_staged = None

            # Invalidate git cache to get fresh state
            self.git_sidebar._invalidate_cache()

            if success:
                self.notify(f"Unstaged hunk in {file_path}", severity="information")
            else:
                self.notify("Could not unstage hunk (may already be unstaged)", severity="warning")

            # Regardless of success/failure, rebuild file list and check if we should advance
            old_file = self.current_file
            self.build_file_list()
            self._stay_on_file_or_advance(old_file)

        except Exception as e:
            self.notify(f"Error unstaging hunk: {e}", severity="error")

    def discard_hunk(self, file_path: str, hunk_index: int) -> None:
        """Discard changes in a specific hunk of a file."""
        try:
            success = self.git_sidebar.discard_hunk(file_path, hunk_index)

            # Clear any cached diff state regardless of success
            self._current_displayed_file = None
            self._current_displayed_is_staged = None

            # Invalidate git cache to get fresh state
            self.git_sidebar._invalidate_cache()

            if success:
                self.notify(f"Discarded hunk in {file_path}", severity="information")
            else:
                self.notify("Could not discard hunk (may already be gone)", severity="warning")

            # Regardless of success/failure, rebuild file list and check if we should advance
            old_file = self.current_file
            self.build_file_list()
            self._stay_on_file_or_advance(old_file)

        except Exception as e:
            self.notify(f"Error discarding hunk: {e}", severity="error")

    def _stay_on_file_or_advance(self, old_file: str) -> None:
        """Try to stay on the same file after a hunk operation, or advance to next."""
        if not self.file_list:
            # No files left in current view
            self.current_file = None
            self.current_file_index = 0
            self.update_status_bar()
            
            # If we were viewing unstaged files and there are none left,
            # but there ARE staged files, auto-switch to staged view
            if not self.viewing_staged:
                self.git_sidebar._invalidate_cache()
                staged_files = self.git_sidebar.get_staged_files()
                
                if staged_files:
                    self.notify(
                        f"All changes staged! Press 'c' to commit ({len(staged_files)} files)",
                        severity="information",
                    )
                    # Auto-switch to staged view
                    self.viewing_staged = True
                    self.build_file_list()
                    self.current_file_index = 0
                    if self.file_list:
                        self._navigate_to_current_file()
                    else:
                        self.update_status_bar()
                    return
            
            # Show "no changes" message
            try:
                diff_content = self.query_one("#diff-content", VerticalScroll)
                diff_content.remove_children()
                view_type = "staged" if self.viewing_staged else "unstaged"
                diff_content.mount(
                    Static(f"No {view_type} changes to display", classes="info")
                )
            except Exception:
                pass
            return
        
        # Try to find the same file in the list
        for i, (file_path, _) in enumerate(self.file_list):
            if file_path == old_file:
                # File still exists - check if it still has hunks
                hunks = self.git_sidebar.get_diff_hunks(file_path, staged=self.viewing_staged)
                if hunks:
                    self.current_file_index = i
                    self._navigate_to_current_file()
                    return
                # File has no more hunks in current view, fall through to advance
                break
        
        # File no longer in list or has no hunks, advance to next file
        if self.file_list:
            # Move to next file (wrap around if needed)
            self.current_file_index = min(self.current_file_index, len(self.file_list) - 1)
            self._navigate_to_current_file()

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

                # Rebuild file list and refresh view
                self.build_file_list()
                self.populate_commit_history()
                
                if self.file_list:
                    self._navigate_to_current_file()
                else:
                    self.update_status_bar()
                    try:
                        diff_content = self.query_one("#diff-content", VerticalScroll)
                        diff_content.remove_children()
                        diff_content.mount(
                            Static("Commit successful! No more changes to display.", classes="info")
                        )
                    except Exception:
                        pass
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
                # Rebuild file list and refresh
                self.build_file_list()
                self.populate_commit_history()
                if self.file_list:
                    self._navigate_to_current_file()
                else:
                    self.update_status_bar()
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
        """Stage the entire currently selected file."""
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
                old_file = self.current_file
                self.build_file_list()
                self._stay_on_file_or_advance(old_file)
                self.notify(f"Staged {old_file}", severity="information")
            else:
                self.notify(
                    f"Failed to stage {self.current_file}",
                    severity="error",
                )
        except Exception as e:
            self.notify(f"Error staging selected file: {e}", severity="error")

    def action_unstage_selected_file(self) -> None:
        """Unstage all changes for the selected file."""
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
                old_file = self.current_file
                self.build_file_list()
                self._stay_on_file_or_advance(old_file)
                self.notify(f"Unstaged {old_file}", severity="information")
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
                # Rebuild file list and refresh
                self.build_file_list()
                if self.file_list:
                    self.current_file_index = 0
                    self._navigate_to_current_file()
                else:
                    self.update_status_bar()
                    try:
                        diff_content = self.query_one("#diff-content", VerticalScroll)
                        diff_content.remove_children()
                        diff_content.mount(
                            Static("All changes staged! Switch to staged view (2) to see them.", classes="info")
                        )
                    except Exception:
                        pass
                self.notify("All changes staged", severity="information")
            else:
                self.notify(message, severity="error")
        except Exception as e:
            self.notify(f"Error staging all changes: {e}", severity="error")

    def action_unstage_all(self) -> None:
        """Unstage all staged changes."""
        try:
            success, message = self.git_sidebar.unstage_all_changes()
            if success:
                # Rebuild file list and refresh
                self.build_file_list()
                if self.file_list:
                    self.current_file_index = 0
                    self._navigate_to_current_file()
                else:
                    self.update_status_bar()
                    try:
                        diff_content = self.query_one("#diff-content", VerticalScroll)
                        diff_content.remove_children()
                        diff_content.mount(
                            Static("All changes unstaged! Switch to unstaged view (1) to see them.", classes="info")
                        )
                    except Exception:
                        pass
                self.notify("All changes unstaged", severity="information")
            else:
                self.notify(message, severity="error")
        except Exception as e:
            self.notify(f"Error unstaging all changes: {e}", severity="error")

    def action_switch_to_unstaged(self) -> None:
        """Switch to viewing unstaged files."""
        self.viewing_staged = False
        self.build_file_list()
        self.current_file_index = 0
        if self.file_list:
            self._navigate_to_current_file()
        else:
            self.update_status_bar()
            # Clear diff panel and show message
            try:
                diff_content = self.query_one("#diff-content", VerticalScroll)
                diff_content.remove_children()
                diff_content.mount(
                    Static("No unstaged changes to display", classes="info")
                )
            except Exception:
                pass
        self.notify("Viewing unstaged files", severity="information")

    def action_switch_to_staged(self) -> None:
        """Switch to viewing staged files."""
        self.viewing_staged = True
        self.build_file_list()
        self.current_file_index = 0
        if self.file_list:
            self._navigate_to_current_file()
        else:
            self.update_status_bar()
            # Clear diff panel and show message
            try:
                diff_content = self.query_one("#diff-content", VerticalScroll)
                diff_content.remove_children()
                diff_content.mount(
                    Static("No staged changes to display", classes="info")
                )
            except Exception:
                pass
        self.notify("Viewing staged files", severity="information")

    def action_show_commit_tab(self) -> None:
        """Switch to the Commit Message tab."""
        try:
            tabbed_content = self.query_one("#main-tabs", TabbedContent)
            tabbed_content.active = "commit-tab"
        except Exception as e:
            self.notify(f"Could not switch to commit tab: {e}", severity="error")

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

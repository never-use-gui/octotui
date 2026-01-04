<div align="center">

<img src="cute-octo.png" alt="OctoTUI Logo" width="300">

# OctoTUI

[![PyPI version](https://img.shields.io/pypi/v/octotui.svg)](https://pypi.org/project/octotui/)
[![Python](https://img.shields.io/pypi/pyversions/octotui.svg)](https://pypi.org/project/octotui/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

**A terminal UI for Git, inspired by GitKraken**

[Installation](#installation) • [Screenshots](#screenshots) • [Keybindings](#keybindings)

</div>

---

![OctoTUI Demo](octotui.gif)

OctoTUI brings a GitKraken-like experience to your terminal. Visual diffs, hunk-level staging, branch management, commit history—all without leaving the command line.

### Features

- Visual diffs with syntax highlighting
- Hunk-level staging/unstaging
- Branch visualization and management
- Commit history browsing
- AI-powered commit messages (via [GAC](https://github.com/cellwebb/gac))
- 100% free and open source

---

## Screenshots

### Status Tab
Repository status at a glance: branch, remote tracking, sync status (ahead/behind), working tree operations.

![Status Tab](screenshots/octotui_status.png)

### Files Tab
Browse your repository with a tree view. Press `e` to open files in your editor.

![Files Tab](screenshots/octotui_files.png)

### Unstaged Changes
Review unstaged changes with syntax-highlighted diffs. Stage or discard individual hunks.

![Unstaged Tab](screenshots/octotui_unstaged.png)

### Staged Changes
See what's going into your next commit. Unstage hunks if needed.

![Staged Tab](screenshots/octotui_staged.png)

### Commit Tab
Write commit messages with subject and body, or generate them with AI.

![Commit Tab](screenshots/octotui_commit.png)

### Settings Tab
Configure your editor, theme, and AI provider. Supports 30+ providers including OpenAI, Anthropic, and Ollama.

![Settings Tab](screenshots/octotui_settings1.png)
![Settings Tab - GAC Config](screenshots/octotui_settings2.png)

---

## Installation

### Quick Start

```bash
uvx octotui
```

### From Source

```bash
git clone https://github.com/never-use-gui/octotui.git
cd octotui
uv run octotui
```

### Requirements

- Python 3.11+
- Git
- Terminal with 256+ colors

---

## AI Commit Messages (Optional)

```bash
uv pip install 'gac>=0.18.0'
```

Then press `Ctrl+G` in OctoTUI to configure your AI provider.

---

## Keybindings

### Navigation
| Key | Action |
|-----|--------|
| `↑/↓` | Navigate files/hunks |
| `←/→` | Navigate between files |
| `Enter` | Select file |
| `Tab` | Cycle through buttons |
| `e` | Edit file in external editor |

### View Switching
| Key | Tab |
|-----|-----|
| `1` | Status |
| `2` | Files |
| `3` | Unstaged |
| `4` | Staged |
| `5` | Commit |
| `6` | Graph |
| `7` | History |
| `8` | Settings |

### Git Operations
| Key | Action |
|-----|--------|
| `s` | Stage selected file |
| `u` | Unstage selected file |
| `a` | Stage all changes |
| `x` | Unstage all changes |
| `c` | Commit |
| `p` | Push |
| `o` | Pull |
| `r` | Refresh |
| `b` | Switch branch |

### AI & App
| Key | Action |
|-----|--------|
| `g` | Generate AI commit message |
| `Ctrl+G` | Configure GAC |
| `h` | Help |
| `q` | Quit |

---

## Git Status Colors

| Color | Meaning |
|-------|----------|
| Green | Staged |
| Yellow | Modified (unstaged) |
| Blue | Directory |
| Purple | Untracked |
| Red | Deleted |

---

## Tech Stack

- [Textual](https://textual.textualize.io/) - TUI framework
- [GitPython](https://gitpython.readthedocs.io/) - Git operations
- [GAC](https://github.com/cellwebb/gac) - AI commit generation

## License

MIT - see [LICENSE](LICENSE)

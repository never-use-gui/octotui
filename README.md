<div align="center">

<img src="cute-octo.png" alt="OctoTUI Logo" width="300">

# 🐙 OctoTUI


[![PyPI version](https://img.shields.io/pypi/v/octotui.svg)](https://pypi.org/project/octotui/)
[![Python](https://img.shields.io/pypi/pyversions/octotui.svg)](https://pypi.org/project/octotui/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](http://makeapullrequest.com)

**A Textual TUI For GitKraken Lovers** 
 
[Installation](#-installation) • [AI Commits](#-ai-powered-commits) • [Keybindings](#️-keybindings)

</div>

---

## 🚀 OctoTUI
![octotui.png](octotui.png)
> **We love GitKraken so much, we wanted to bring that beautiful experience to the terminal!**

GitKraken is amazing - it's gorgeous, intuitive, and makes Git feel approachable. But as terminal enthusiasts, we found ourselves constantly context-switching between our editor and GitKraken. We wanted that same delightful experience without ever leaving the command line.

**OctoTUI is our love letter to both GitKraken and the terminal.**

### 💙 What We Kept from GitKraken
- ✅ Beautiful, intuitive visual diffs
- ✅ Hunk-level staging control
- ✅ Branch visualization and management
- ✅ Commit history browsing

### 🎯 What We Added for Terminal Lovers
- 🤖 AI-powered commit messages (via GAC)
- 🆓 100% free and open source
- 🏠 Never leave your terminal flow

## 📦 Installation

### Quick Start (Recommended)

```bash
# Using uvx (isolated, recommended)
uvx octotui
```

### From Source (For Contributors)

```bash
git clone https://github.com/never-use-gui/octotui.git
cd octotui
uv run octotui
```

### System Requirements

- 🐍 Python 3.11+
- 🔧 Git
- 💻 Any terminal with 256+ colors


### First-Time Workflow

1. **Review Changes**: See your diffs in beautiful color
2. **Stage Hunks**: Click or use `s` to stage individual changes
3. **Generate Commit**: Press `g` for AI-powered message (optional)
4. **Commit**: Press `c` to commit with your message
5. **Push**: Press `p` to push to remote

**Pro tip**: Press `h` anytime to see all available keybindings! 🚀

## 🤖 AI-Powered Commits

### Setup (Optional but Awesome)

```bash
# Install GAC (Git Auto Commit)
uv pip install 'gac>=0.18.0'
```

### Configuration

1. Press `Ctrl+G` in OctoTUI
2. Choose your provider (we recommend **Cerebras** for free tier)
3. Select your model
4. Paste your API key
5. Save & enjoy AI commit messages!

## ⌨️ Keybindings

### 📁 Navigation
| Key | Action |
|-----|--------|
| `↑/↓` | Navigate files/hunks |
| `Enter` | Select file |
| `Tab` / `Shift+Tab` | Cycle through UI elements |
| `1` / `Ctrl+1` | Switch to Unstaged tab |
| `2` / `Ctrl+2` | Switch to Staged tab |

### 🔄 Git Operations
| Key | Action |
|-----|--------|
| `s` | Stage selected file |
| `u` | Unstage selected file |
| `a` | Stage ALL unstaged changes |
| `x` | Unstage ALL staged changes |
| `c` | Commit staged changes |

### 🌿 Branch & Remote
| Key | Action |
|-----|--------|
| `b` | Switch branch |
| `r` | Refresh status |
| `p` | Push to remote |
| `o` | Pull from remote |

### 🤖 AI Features
| Key | Action |
|-----|--------|
| `g` | Generate AI commit message |
| `Ctrl+G` | Configure GAC settings |

### ⚙️ Application
| Key | Action |
|-----|--------|
| `h` | Show help modal |
| `q` | Quit application |
| `Ctrl+D` | Toggle dark mode |

## 🎨 Git Status Colors

| Color | Meaning |
|-------|----------|
| 🟢 **Green** | Staged files (ready to commit) |
| 🟡 **Yellow** | Modified files (unstaged) |
| 🔵 **Blue** | Directories |
| 🟣 **Purple** | Untracked files |
| 🔴 **Red** | Deleted files |

### Code Quality Standards

- ✅ Follow the Zen of Python
- ✅ DRY (Don't Repeat Yourself)
- ✅ YAGNI (You Aren't Gonna Need It)
- ✅ SOLID principles
- ✅ Keep files under 600 lines
- ✅ Write tests for new features
- ✅ Pass `ruff check` with zero errors

## 📚 Tech Stack

- **[Textual](https://textual.textualize.io/)**: Modern TUI framework
- **[GitPython](https://gitpython.readthedocs.io/)**: Git operations
- **[GAC](https://github.com/cellwebb/gac)**: AI commit generation
- **[Ruff](https://github.com/astral-sh/ruff)**: Lightning-fast Python linter

## 📜 License

MIT License - see [LICENSE](LICENSE) for details

## 🙏 Acknowledgments

- Built with ❤️ using [Textual](https://textual.textualize.io/)
- AI commits powered by [GAC](https://github.com/cellwebb/gac)

## 💬 Community

- 🐛 **Issues**: [GitHub Issues](https://github.com/never-use-gui/octotui/issues)
---

<div align="center">

### 🌟 If you like OctoTUI, give us a star! 🌟

[⬆ Back to Top](#-octotui)

</div>

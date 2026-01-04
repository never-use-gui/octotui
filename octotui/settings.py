"""Settings management for octotui."""

import json
from pathlib import Path
from typing import Any


DEFAULT_SETTINGS = {
    "editor": "",
    "theme": "tokyo-night",
}

CONFIG_DIR = Path.home() / ".config" / "octotui"
SETTINGS_FILE = CONFIG_DIR / "settings.json"


def ensure_config_dir() -> None:
    """Ensure the config directory exists."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_settings() -> dict[str, Any]:
    """Load settings from the config file."""
    ensure_config_dir()
    
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r") as f:
                settings = json.load(f)
                # Merge with defaults to handle new settings
                return {**DEFAULT_SETTINGS, **settings}
        except (json.JSONDecodeError, IOError):
            return DEFAULT_SETTINGS.copy()
    
    return DEFAULT_SETTINGS.copy()


def save_settings(settings: dict[str, Any]) -> bool:
    """Save settings to the config file."""
    ensure_config_dir()
    
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=2)
        return True
    except IOError:
        return False


def get_setting(key: str, default: Any = None) -> Any:
    """Get a specific setting value."""
    settings = load_settings()
    return settings.get(key, default)


def set_setting(key: str, value: Any) -> bool:
    """Set a specific setting value and save."""
    settings = load_settings()
    settings[key] = value
    return save_settings(settings)

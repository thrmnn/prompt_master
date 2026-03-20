"""User configuration file support (~/.prompt_master/config.toml)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

CONFIG_PATH = Path.home() / ".prompt_master" / "config.toml"

# Default values
DEFAULTS = {
    "target": "general",
    "model": "haiku",
    "max_tokens": 4096,
    "format": "markdown",
}


def load_config() -> Dict[str, Any]:
    """Load config from disk, falling back to defaults for missing keys."""
    config = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "rb") as f:
                user_config = tomllib.load(f)
            config.update(user_config)
        except Exception:
            pass  # Silently use defaults on parse failure
    return config


def get(key: str, default: Any = None) -> Any:
    """Get a single config value."""
    config = load_config()
    return config.get(key, default)

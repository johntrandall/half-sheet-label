"""Config loading. TOML at $XDG_CONFIG_HOME/half-sheet-label/config.toml.

Everything is optional; the tool runs with sensible defaults and no config file.
Example config lives in docs/config.example.toml.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path


def default_config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")
    return Path(base) / "half-sheet-label" / "config.toml"


def load_config(path: Path | None = None) -> dict:
    p = Path(path) if path else default_config_path()
    try:
        return tomllib.loads(p.read_text())
    except FileNotFoundError:
        return {}
    except tomllib.TOMLDecodeError as e:
        raise SystemExit(f"half-sheet-label: bad config at {p}: {e}")

from __future__ import annotations

import sys
from pathlib import Path


def app_root() -> Path:
    """Return the source root or PyInstaller extraction root."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)

    return Path(__file__).resolve().parent


def resource_path(relative_path: str) -> Path:
    return app_root() / relative_path

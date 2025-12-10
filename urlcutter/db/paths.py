"""Centralized user-data and migrations paths for UrlCutter."""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

APP_NAME = "UrlCutter"

__all__ = ["APP_NAME", "user_data_dir", "db_path", "alembic_dir"]


def _is_frozen() -> bool:
    """Detect PyInstaller runtime."""
    return bool(getattr(sys, "frozen", False)) and hasattr(sys, "_MEIPASS")


def user_data_dir() -> Path:
    """
    Return the per-OS user data directory for the app and ensure it exists.

    Windows: %APPDATA%/UrlCutter
    macOS:   ~/Library/Application Support/UrlCutter
    Linux:   ~/.local/share/UrlCutter

    Override (for dev/tests): set env URLCUTTER_DATA_DIR to an absolute path.
    """
    override = os.getenv("URLCUTTER_DATA_DIR")
    if override:
        p = Path(override).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    system = platform.system()
    if system == "Windows":
        base = os.getenv("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        p = Path(base) / APP_NAME
    elif system == "Darwin":
        p = Path.home() / "Library" / "Application Support" / APP_NAME
    else:
        p = Path.home() / ".local" / "share" / APP_NAME

    p.mkdir(parents=True, exist_ok=True)
    return p


def db_path() -> Path:
    """
    Path to the SQLite history database file inside the user data dir.

    Always: <user_data_dir>/history.db
    """
    return user_data_dir() / "history.db"


def alembic_dir() -> Path:
    """
    Locate the Alembic migrations folder.

    Resolution order:
      1) Env override URLCUTTER_ALEMBIC_DIR (absolute path).
      2) Frozen app: <_MEIPASS>/alembic_migrations (bundled with PyInstaller).
      3) Dev: <project_root>/alembic_migrations
      4) Fallback: <user_data_dir>/alembic_migrations (will be created if missing).
    """
    override = os.getenv("URLCUTTER_ALEMBIC_DIR")
    if override:
        p = Path(override).expanduser().resolve()
        if p.exists():
            return p

    if _is_frozen():
        p = Path(sys._MEIPASS) / "alembic_migrations"  # type: ignore[attr-defined]
        if p.exists():
            return p

    # This file is urlcutter/db/paths.py → project root is parents[2]
    project_root = Path(__file__).resolve().parents[2]
    p = project_root / "alembic_migrations"
    if p.exists():
        return p

    # Last-resort fallback
    p = user_data_dir() / "alembic_migrations"
    p.mkdir(parents=True, exist_ok=True)
    return p

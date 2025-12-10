"""Programmatic Alembic upgrade for app startup (works with/without alembic.ini)."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from .paths import alembic_dir, db_path


def upgrade_to_head() -> None:
    """
    Ensure the local DB schema is at the latest Alembic head.
    Safe to call on every app start.

    - В dev читаем корневой alembic.ini (если есть) только ради логгинга.
    - В иных случаях конфиг собираем программно.
    """
    # Попробуем найти корневой ini (обычный dev-случай: <project_root>/alembic.ini)
    project_root = Path(__file__).resolve().parents[2]
    root_ini = project_root / "alembic_migrations" / "alembic.ini"

    cfg = Config(str(root_ini)) if root_ini.exists() else Config()

    # Куда смотреть миграции и где наша БД
    cfg.set_main_option("script_location", str(alembic_dir()))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path().as_posix()}")

    # Запускаем апгрейд
    command.upgrade(cfg, "head")

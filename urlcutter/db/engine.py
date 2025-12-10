"""SQLAlchemy engine and session helpers for UrlCutter."""

from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .paths import db_path

# SQLite URL to the user data dir DB
_SQLITE_URL = f"sqlite:///{db_path().as_posix()}"

# Single engine for the app; check_same_thread=False for GUI callbacks
engine = create_engine(
    _SQLITE_URL,
    connect_args={"check_same_thread": False},
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@contextmanager
def get_session():
    """
    Context-managed DB session.

    Usage:
        with get_session() as s:
            ...
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

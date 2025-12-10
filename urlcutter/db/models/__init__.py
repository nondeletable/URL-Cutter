"""ORM models for UrlCutter."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


# export models
from .link import Link  # noqa: E402,F401

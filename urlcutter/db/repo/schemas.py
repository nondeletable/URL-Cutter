"""Data contracts (DTO) for the History feature. No business logic here."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

# Defaults for UI paging
DEFAULT_PAGE_SIZE: int = 50
PAGE_SIZE_CHOICES = (10, 25, 50, 100)

SortField = Literal["created_at", "service", "long_url", "short_url", "copy_count"]
SortDirection = Literal["asc", "desc"]
LocaleCode = Literal["ru", "en"]


@dataclass(slots=True)
class LinkRecord:
    """
    Single link history entry.

    Note: on 'add' call, 'id' and 'created_at_utc' may be None (assigned by storage).
    """

    id: int | None
    long_url: str
    short_url: str
    service: str
    created_at_utc: datetime | None
    copy_count: int = 0


@dataclass(slots=True)
class HistoryFilters:
    """Filters applied to the listing/export operations."""

    query: str | None = None  # case-insensitive substring in long_url OR short_url
    date_from_local: date | None = None  # inclusive, user's local date
    date_to_local: date | None = None  # inclusive, user's local date
    service: str | None = None  # None or "ALL" => no filter


@dataclass(slots=True)
class SortSpec:
    field: SortField = "created_at"
    direction: SortDirection = "desc"


@dataclass(slots=True)
class PageSpec:
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE  # should be one of PAGE_SIZE_CHOICES


@dataclass(slots=True)
class HistoryPage:
    items: list[LinkRecord]
    total: int
    page: int
    page_size: int
    has_prev: bool
    has_next: bool


@dataclass(slots=True)
class ExportSpec:
    filters: HistoryFilters
    sort: SortSpec
    locale: LocaleCode
    filename_suggestion: str  # e.g., "urlcutter_history_YYYY-MM-DD.csv"

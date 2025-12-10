"""Abstract interface for the History service (no implementation here)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .schemas import (
    ExportSpec,
    HistoryFilters,
    HistoryPage,
    LinkRecord,
    PageSpec,
    SortSpec,
)


class HistoryService(ABC):
    """
    Contract for link history operations.

    Implementations must:
      - treat date filters as inclusive (local dates translated to UTC internally),
      - perform case-insensitive substring search across long_url OR short_url,
      - sort and paginate deterministically,
      - protect CSV output from CSV injection by prefixing values that start with =,+,-,@.
    """

    @abstractmethod
    def list(self, filters: HistoryFilters, sort: SortSpec, page: PageSpec) -> HistoryPage:
        """Return a paginated result according to filters and sort order."""
        raise NotImplementedError

    @abstractmethod
    def add(self, record: LinkRecord) -> LinkRecord:
        """
        Persist a new record and return the stored version with id and created_at_utc set.
        May raise ValidationError or StorageError.
        """
        raise NotImplementedError

    @abstractmethod
    def increment_copy_count(self, id: int) -> None:
        """Increase copy_count for the given record id by 1."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, id: int) -> None:
        """Delete the record by id. May raise NotFoundError or StorageError."""
        raise NotImplementedError

    @abstractmethod
    def export_csv(self, spec: ExportSpec) -> bytes:
        """Produce CSV bytes for the current selection (filters + sort)."""
        raise NotImplementedError

    @abstractmethod
    def distinct_services(self) -> list[str]:
        """Return unique service identifiers available in storage."""
        raise NotImplementedError

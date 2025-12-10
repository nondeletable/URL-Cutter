"""Typed exceptions for the History service (no logic)."""


class ValidationError(Exception):
    """Client error: bad input parameters (e.g., page < 1, wrong id, invalid dates)."""


class NotFoundError(Exception):
    """Requested record was not found."""


class StorageError(Exception):
    """Persistent storage failure (DB/file I/O)."""


class ExportError(Exception):
    """CSV export failed."""

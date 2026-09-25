"""
Helpers for partial updates (PATCH) shared by the finance services.

Used by:
- accounts_service.py, categories_service.py, investment_assets_service.py
"""

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any


def reject_nulls(changes: dict[str, Any], fields: Iterable[str]) -> None:
    """Raise ValueError when a required field is explicitly sent as null."""

    for field in fields:
        if field in changes and changes[field] is None:
            raise ValueError(f"'{field}' cannot be null")


def apply_archive_flag(
    changes: dict[str, Any], current_archived_at: datetime | None
) -> None:
    """
    Replace the `archived` flag with the `archived_at` column value.

    Archiving an already archived row keeps its original timestamp;
    restoring clears it.
    """

    if "archived" not in changes:
        return

    archived = changes.pop("archived")

    if archived:
        changes["archived_at"] = current_archived_at or datetime.now(UTC)
    else:
        changes["archived_at"] = None

"""
HTTP contracts for note operations.

Used by:
- api/notes.py
"""

from uuid import UUID

from pydantic import BaseModel, Field


class NoteCreateRequest(BaseModel):
    """Note submitted by the authenticated user."""

    title: str = Field(
        min_length=1,
        max_length=200,
    )

    # Keep synchronous ingestion intentionally bounded.
    content: str = Field(
        min_length=1,
        max_length=1_000_000,
    )


class NoteCreateResponse(BaseModel):
    """Result returned after successful note ingestion."""

    note_id: UUID

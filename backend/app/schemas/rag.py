"""
Contracts used by the RAG subsystem.

These schemas decouple vector retrieval from agents and HTTP APIs.
Retrieval returns structured metadata instead of plain strings so callers
can reason about note provenance, relevance and citations.

Used by:
- repositories/note_repository.py
- services/rag/retrieval_service.py
- agent knowledge tools
"""

from uuid import UUID

from pydantic import BaseModel


class RetrievalResult(BaseModel):
    """A chunk retrieved from the user's notes."""

    note_id: UUID
    title: str
    chunk_index: int
    content: str
    distance: float

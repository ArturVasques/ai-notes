"""
Contracts used by the RAG subsystem.

These schemas decouple vector retrieval from agents and HTTP APIs.
Retrieval returns structured metadata instead of plain strings so callers
can reason about document provenance, relevance and citations.

Used by:
- repositories/document_repository.py
- services/rag/retrieval_service.py
- agent knowledge tools
"""

from uuid import UUID

from pydantic import BaseModel


class RetrievalResult(BaseModel):
    """A chunk retrieved from the tenant's knowledge base."""

    document_id: UUID
    filename: str
    chunk_index: int
    content: str
    distance: float

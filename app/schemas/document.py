"""
HTTP contracts for document operations.

Used by:
- api/documents.py
"""

from uuid import UUID

from pydantic import BaseModel


class DocumentUploadResponse(BaseModel):
    """Result returned after successful document ingestion."""

    document_id: UUID
    status: str

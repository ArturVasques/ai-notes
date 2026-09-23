"""
Document ingestion orchestration.

Coordinates:
1. text chunking,
2. batch embedding generation,
3. atomic persistence.

Used by:
- document upload API.
- future background ingestion workers.

The service coordinates application behaviour but contains no SQL.
"""

from uuid import UUID, uuid4

from app.repositories.document_repository import create_document_with_chunks
from app.services.ai.embedding_service import create_embeddings
from app.services.rag.chunking import chunk_text


async def ingest_document(
    *,
    tenant_id: UUID,
    uploaded_by: UUID,
    filename: str,
    content_type: str | None,
    content: str,
) -> UUID:
    """Ingest a text document into the tenant knowledge base."""

    chunks = chunk_text(content)

    if not chunks:
        raise ValueError("Document contains no usable text")

    embeddings = await create_embeddings(chunks)

    document_id = uuid4()

    await create_document_with_chunks(
        document_id=document_id,
        tenant_id=tenant_id,
        uploaded_by=uploaded_by,
        filename=filename,
        content_type=content_type,
        chunks=chunks,
        embeddings=embeddings,
    )

    return document_id

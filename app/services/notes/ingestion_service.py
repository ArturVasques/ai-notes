"""
Note ingestion orchestration.

Coordinates:
1. text chunking,
2. batch embedding generation,
3. atomic persistence.

Used by:
- notes API.
- future background ingestion workers.

The service coordinates application behaviour but contains no SQL.
"""

from uuid import UUID, uuid4

from app.repositories.note_repository import create_note_with_chunks
from app.services.ai.embedding_service import create_embeddings
from app.services.rag.chunking import chunk_text


async def ingest_note(
    *,
    created_by: UUID,
    title: str,
    content: str,
) -> UUID:
    """Ingest a note into the knowledge base of the user who created it."""

    chunks = chunk_text(content)

    if not chunks:
        raise ValueError("Note contains no usable text")

    embeddings = await create_embeddings(chunks)

    note_id = uuid4()

    await create_note_with_chunks(
        note_id=note_id,
        created_by=created_by,
        title=title,
        content=content,
        chunks=chunks,
        embeddings=embeddings,
    )

    return note_id

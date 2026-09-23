"""
Semantic retrieval orchestration.

Transforms a natural-language query into an embedding and retrieves relevant
chunks from the user's notes in PostgreSQL/pgvector.

Used by:
- agent knowledge tools.
- evaluation suites.
- future search endpoints.
"""

from uuid import UUID

from app.core.config import get_settings
from app.repositories.note_repository import search_similar_chunks
from app.schemas.rag import RetrievalResult
from app.services.ai.embedding_service import create_embedding

settings = get_settings()


async def retrieve_knowledge(
    *,
    user_id: UUID,
    query: str,
) -> list[RetrievalResult]:
    """Retrieve relevant chunks from the notes owned by the user."""

    embedding = await create_embedding(query)

    return await search_similar_chunks(
        user_id=user_id,
        embedding=embedding,
        limit=settings.rag_top_k,
        max_distance=settings.rag_max_distance,
    )

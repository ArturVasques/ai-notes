"""
OpenAI embedding infrastructure.

Provides single-query and batch note embedding operations.

Used by:
- note ingestion to embed chunks in batches.
- retrieval service to embed search queries.

Note ingestion uses batching to avoid one API request per chunk.
"""

from openai import AsyncOpenAI

from app.core.config import get_ai_settings

settings = get_ai_settings()

client = AsyncOpenAI(api_key=settings.openai_api_key)


async def create_embedding(text: str) -> list[float]:
    """Create an embedding for a single search query."""

    response = await client.embeddings.create(
        model=settings.openai_embedding_model,
        input=text,
    )

    return response.data[0].embedding


async def create_embeddings(texts: list[str]) -> list[list[float]]:
    """Create embeddings for multiple note chunks in one API request."""

    if not texts:
        return []

    response = await client.embeddings.create(
        model=settings.openai_embedding_model,
        input=texts,
    )

    return [item.embedding for item in response.data]

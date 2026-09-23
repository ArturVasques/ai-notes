"""
Persistence and vector retrieval for notes.

Responsibilities:
- persist notes and their chunks.
- perform owner-scoped vector similarity searches.

Used by:
- note ingestion service.
- RAG retrieval service.

Security boundary:
Every retrieval query requires the owner's user_id and filters it directly
in SQL. Note ownership must never depend on an LLM instruction.
"""

from uuid import UUID, uuid4

from psycopg import AsyncConnection

from app.database.connection import pool
from app.schemas.rag import RetrievalResult


async def create_note_with_chunks(
    *,
    note_id: UUID,
    created_by: UUID,
    title: str,
    content: str,
    chunks: list[str],
    embeddings: list[list[float]],
) -> None:
    """
    Persist a note and all generated chunks atomically.

    A single transaction prevents partially-ingested notes. If any chunk
    fails, neither the note nor its chunks are committed.
    """

    if len(chunks) != len(embeddings):
        raise ValueError("Every chunk must have exactly one embedding")

    async with pool.connection() as connection, connection.transaction():
        await _insert_note(
            connection=connection,
            note_id=note_id,
            created_by=created_by,
            title=title,
            content=content,
        )

        await _insert_chunks(
            connection=connection,
            note_id=note_id,
            chunks=chunks,
            embeddings=embeddings,
        )


async def _insert_note(
    *,
    connection: AsyncConnection,
    note_id: UUID,
    created_by: UUID,
    title: str,
    content: str,
) -> None:
    """Insert the note within the caller's transaction."""

    await connection.execute(
        """
        INSERT INTO notes (
            id,
            created_by,
            title,
            content
        )
        VALUES (%s, %s, %s, %s)
        """,
        (
            note_id,
            created_by,
            title,
            content,
        ),
    )


async def _insert_chunks(
    *,
    connection: AsyncConnection,
    note_id: UUID,
    chunks: list[str],
    embeddings: list[list[float]],
) -> None:
    """Insert all chunks within the same note transaction."""

    async with connection.cursor() as cursor:
        await cursor.executemany(
            """
            INSERT INTO note_chunks (
                id,
                note_id,
                chunk_index,
                content,
                embedding
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            [
                (
                    uuid4(),
                    note_id,
                    index,
                    chunk,
                    embedding,
                )
                for index, (chunk, embedding) in enumerate(
                    zip(chunks, embeddings, strict=True)
                )
            ],
        )


async def search_similar_chunks(
    *,
    user_id: UUID,
    embedding: list[float],
    limit: int,
    max_distance: float,
) -> list[RetrievalResult]:
    """
    Retrieve semantically similar chunks belonging only to the user's notes.

    Filtering occurs inside PostgreSQL before results are exposed to the AI
    layer. The LLM therefore cannot retrieve another user's notes.
    """

    async with pool.connection() as connection, connection.cursor() as cursor:
        await cursor.execute(
            """
                SELECT
                    nc.note_id,
                    n.title,
                    nc.chunk_index,
                    nc.content,
                    nc.embedding <=> %s::vector AS distance
                FROM note_chunks nc
                JOIN notes n
                  ON n.id = nc.note_id
                WHERE n.created_by = %s
                  AND nc.embedding <=> %s::vector < %s
                ORDER BY nc.embedding <=> %s::vector
                LIMIT %s
                """,
            (
                embedding,
                user_id,
                embedding,
                max_distance,
                embedding,
                limit,
            ),
        )

        rows = await cursor.fetchall()

    return [
        RetrievalResult(
            note_id=row[0],
            title=row[1],
            chunk_index=row[2],
            content=row[3],
            distance=float(row[4]),
        )
        for row in rows
    ]

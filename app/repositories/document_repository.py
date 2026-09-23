"""
Persistence and vector retrieval for knowledge-base documents.

Responsibilities:
- persist documents and their chunks.
- perform tenant-scoped vector similarity searches.

Used by:
- document ingestion service.
- RAG retrieval service.

Security boundary:
Every retrieval query requires tenant_id and filters it directly in SQL.
Tenant isolation must never depend on an LLM instruction.
"""

from uuid import UUID, uuid4

from psycopg import AsyncConnection

from app.database.connection import pool
from app.schemas.rag import RetrievalResult


async def create_document_with_chunks(
    *,
    document_id: UUID,
    tenant_id: UUID,
    uploaded_by: UUID,
    filename: str,
    content_type: str | None,
    chunks: list[str],
    embeddings: list[list[float]],
) -> None:
    """
    Persist a document and all generated chunks atomically.

    A single transaction prevents partially-ingested documents. If any chunk
    fails, neither the document nor its chunks are committed.
    """

    if len(chunks) != len(embeddings):
        raise ValueError("Every chunk must have exactly one embedding")

    async with pool.connection() as connection, connection.transaction():
        await _insert_document(
            connection=connection,
            document_id=document_id,
            tenant_id=tenant_id,
            uploaded_by=uploaded_by,
            filename=filename,
            content_type=content_type,
        )

        await _insert_chunks(
            connection=connection,
            document_id=document_id,
            tenant_id=tenant_id,
            chunks=chunks,
            embeddings=embeddings,
        )

        await _mark_document_ready(
            connection=connection,
            document_id=document_id,
            tenant_id=tenant_id,
        )


async def _insert_document(
    *,
    connection: AsyncConnection,
    document_id: UUID,
    tenant_id: UUID,
    uploaded_by: UUID,
    filename: str,
    content_type: str | None,
) -> None:
    """Insert document metadata within the caller's transaction."""

    await connection.execute(
        """
        INSERT INTO documents (
            id,
            tenant_id,
            uploaded_by,
            filename,
            content_type,
            status
        )
        VALUES (%s, %s, %s, %s, %s, 'processing')
        """,
        (
            document_id,
            tenant_id,
            uploaded_by,
            filename,
            content_type,
        ),
    )


async def _insert_chunks(
    *,
    connection: AsyncConnection,
    document_id: UUID,
    tenant_id: UUID,
    chunks: list[str],
    embeddings: list[list[float]],
) -> None:
    """Insert all chunks within the same document transaction."""

    async with connection.cursor() as cursor:
        await cursor.executemany(
            """
            INSERT INTO document_chunks (
                id,
                tenant_id,
                document_id,
                chunk_index,
                content,
                embedding
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            [
                (
                    uuid4(),
                    tenant_id,
                    document_id,
                    index,
                    chunk,
                    embedding,
                )
                for index, (chunk, embedding) in enumerate(
                    zip(chunks, embeddings, strict=True)
                )
            ],
        )


async def _mark_document_ready(
    *,
    connection: AsyncConnection,
    document_id: UUID,
    tenant_id: UUID,
) -> None:
    """Mark a successfully ingested document as available for retrieval."""

    await connection.execute(
        """
        UPDATE documents
        SET status = 'ready'
        WHERE id = %s
          AND tenant_id = %s
        """,
        (document_id, tenant_id),
    )


async def search_similar_chunks(
    *,
    tenant_id: UUID,
    embedding: list[float],
    limit: int,
    max_distance: float,
) -> list[RetrievalResult]:
    """
    Retrieve semantically similar chunks belonging only to the tenant.

    Filtering occurs inside PostgreSQL before results are exposed to the AI
    layer. The LLM therefore cannot retrieve another tenant's documents.
    """

    async with pool.connection() as connection, connection.cursor() as cursor:
        await cursor.execute(
            """
                SELECT
                    dc.document_id,
                    d.filename,
                    dc.chunk_index,
                    dc.content,
                    dc.embedding <=> %s::vector AS distance
                FROM document_chunks dc
                JOIN documents d
                  ON d.id = dc.document_id
                 AND d.tenant_id = dc.tenant_id
                WHERE dc.tenant_id = %s
                  AND d.status = 'ready'
                  AND dc.embedding <=> %s::vector < %s
                ORDER BY dc.embedding <=> %s::vector
                LIMIT %s
                """,
            (
                embedding,
                tenant_id,
                embedding,
                max_distance,
                embedding,
                limit,
            ),
        )

        rows = await cursor.fetchall()

    return [
        RetrievalResult(
            document_id=row[0],
            filename=row[1],
            chunk_index=row[2],
            content=row[3],
            distance=float(row[4]),
        )
        for row in rows
    ]

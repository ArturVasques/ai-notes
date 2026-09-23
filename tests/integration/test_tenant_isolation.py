"""
Integration test proving that vector retrieval cannot cross tenant boundaries.

Uses the real PostgreSQL/pgvector database, but no OpenAI API.
"""

from uuid import uuid4

import pytest

from app.database.connection import pool
from app.repositories.document_repository import search_similar_chunks


@pytest.mark.asyncio
async def test_vector_search_does_not_cross_tenant_boundary() -> None:
    tenant_a = uuid4()
    tenant_b = uuid4()

    user_a = uuid4()
    user_b = uuid4()

    document_a = uuid4()
    document_b = uuid4()

    # Both tenants deliberately receive the same vector.
    # Without tenant filtering, both chunks would be equally good matches.
    vector = [0.1] * 1536

    try:
        async with pool.connection() as connection, connection.transaction():
            await connection.execute(
                """
                    INSERT INTO tenants (id, name)
                    VALUES (%s, 'Tenant A'), (%s, 'Tenant B')
                    """,
                (tenant_a, tenant_b),
            )

            await connection.execute(
                """
                    INSERT INTO users (
                        id,
                        tenant_id,
                        external_identity_id,
                        name,
                        email
                    )
                    VALUES
                        (%s, %s, 'user-a', 'User A', 'a@test.local'),
                        (%s, %s, 'user-b', 'User B', 'b@test.local')
                    """,
                (user_a, tenant_a, user_b, tenant_b),
            )

            await connection.execute(
                """
                    INSERT INTO documents (
                        id,
                        tenant_id,
                        uploaded_by,
                        filename,
                        status
                    )
                    VALUES
                        (%s, %s, %s, 'tenant-a.txt', 'ready'),
                        (%s, %s, %s, 'tenant-b.txt', 'ready')
                    """,
                (
                    document_a,
                    tenant_a,
                    user_a,
                    document_b,
                    tenant_b,
                    user_b,
                ),
            )

            await connection.execute(
                """
                    INSERT INTO document_chunks (
                        id,
                        tenant_id,
                        document_id,
                        chunk_index,
                        content,
                        embedding
                    )
                    VALUES
                        (%s, %s, %s, 0, 'SECRET A', %s),
                        (%s, %s, %s, 0, 'SECRET B', %s)
                    """,
                (
                    uuid4(),
                    tenant_a,
                    document_a,
                    vector,
                    uuid4(),
                    tenant_b,
                    document_b,
                    vector,
                ),
            )

        results = await search_similar_chunks(
            tenant_id=tenant_a,
            embedding=vector,
            limit=10,
            max_distance=0.8,
        )

        assert any(result.content == "SECRET A" for result in results)

        assert all(result.content != "SECRET B" for result in results)

    finally:
        async with pool.connection() as connection, connection.transaction():
            await connection.execute(
                "DELETE FROM tenants WHERE id IN (%s, %s)",
                (tenant_a, tenant_b),
            )


@pytest.mark.asyncio
async def test_document_cannot_reference_user_from_another_tenant() -> None:
    """The database must reject cross-tenant document ownership."""

    tenant_a = uuid4()
    tenant_b = uuid4()
    user_a = uuid4()

    try:
        async with pool.connection() as connection:
            await connection.execute(
                """
                INSERT INTO tenants (id, name)
                VALUES (%s, 'Tenant A'), (%s, 'Tenant B')
                """,
                (tenant_a, tenant_b),
            )

            await connection.execute(
                """
                INSERT INTO users (
                    id,
                    tenant_id,
                    external_identity_id,
                    name,
                    email
                )
                VALUES (%s, %s, 'user-a', 'User A', 'a@test.local')
                """,
                (user_a, tenant_a),
            )

            with pytest.raises(Exception):
                async with connection.transaction():
                    await connection.execute(
                        """
                        INSERT INTO documents (
                            id,
                            tenant_id,
                            uploaded_by,
                            filename
                        )
                        VALUES (%s, %s, %s, 'invalid.txt')
                        """,
                        (
                            uuid4(),
                            tenant_b,
                            user_a,
                        ),
                    )

    finally:
        async with pool.connection() as connection:
            await connection.execute(
                "DELETE FROM tenants WHERE id IN (%s, %s)",
                (tenant_a, tenant_b),
            )


@pytest.mark.asyncio
async def test_chunk_cannot_reference_document_from_another_tenant() -> None:
    """The database must reject cross-tenant document chunks."""

    tenant_a = uuid4()
    tenant_b = uuid4()

    user_a = uuid4()
    document_a = uuid4()

    vector = [0.1] * 1536

    try:
        async with pool.connection() as connection:
            await connection.execute(
                """
                INSERT INTO tenants (id, name)
                VALUES (%s, 'Tenant A'), (%s, 'Tenant B')
                """,
                (tenant_a, tenant_b),
            )

            await connection.execute(
                """
                INSERT INTO users (
                    id,
                    tenant_id,
                    external_identity_id,
                    name,
                    email
                )
                VALUES (%s, %s, 'user-a', 'User A', 'a@test.local')
                """,
                (user_a, tenant_a),
            )

            await connection.execute(
                """
                INSERT INTO documents (
                    id,
                    tenant_id,
                    uploaded_by,
                    filename
                )
                VALUES (%s, %s, %s, 'tenant-a.txt')
                """,
                (
                    document_a,
                    tenant_a,
                    user_a,
                ),
            )

            with pytest.raises(Exception):
                async with connection.transaction():
                    await connection.execute(
                        """
                        INSERT INTO document_chunks (
                            id,
                            tenant_id,
                            document_id,
                            chunk_index,
                            content,
                            embedding
                        )
                        VALUES (%s, %s, %s, 0, 'INVALID', %s)
                        """,
                        (
                            uuid4(),
                            tenant_b,
                            document_a,
                            vector,
                        ),
                    )

    finally:
        async with pool.connection() as connection:
            await connection.execute(
                "DELETE FROM tenants WHERE id IN (%s, %s)",
                (tenant_a, tenant_b),
            )

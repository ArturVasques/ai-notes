"""
Integration tests proving that notes are owned and retrieved per user.

Uses the real PostgreSQL/pgvector database, but no OpenAI API.
"""

from uuid import uuid4

import pytest

from app.database.connection import pool
from app.repositories.note_repository import (
    create_note_with_chunks,
    search_similar_chunks,
)


async def _insert_users(*user_ids: object) -> None:
    async with pool.connection() as connection, connection.transaction():
        for user_id in user_ids:
            await connection.execute(
                """
                INSERT INTO users (id, external_identity_id, name, email)
                VALUES (%s, %s, 'Test User', %s)
                """,
                (user_id, f"test-{user_id}", f"{user_id}@test.local"),
            )


async def _delete_users(*user_ids: object) -> None:
    async with pool.connection() as connection, connection.transaction():
        for user_id in user_ids:
            await connection.execute("DELETE FROM users WHERE id = %s", (user_id,))


@pytest.mark.asyncio
async def test_vector_search_returns_only_the_callers_notes() -> None:
    user_a = uuid4()
    user_b = uuid4()

    # Both users deliberately receive the same vector.
    # Without owner filtering, both chunks would be equally good matches.
    vector = [0.1] * 1536

    try:
        await _insert_users(user_a, user_b)

        for owner, secret in ((user_a, "SECRET A"), (user_b, "SECRET B")):
            await create_note_with_chunks(
                note_id=uuid4(),
                created_by=owner,
                title=f"Note {secret}",
                content=secret,
                chunks=[secret],
                embeddings=[vector],
            )

        results = await search_similar_chunks(
            user_id=user_a,
            embedding=vector,
            limit=10,
            max_distance=0.8,
        )

        assert any(result.content == "SECRET A" for result in results)
        assert all(result.content != "SECRET B" for result in results)
        assert all(result.title == "Note SECRET A" for result in results)

    finally:
        await _delete_users(user_a, user_b)


@pytest.mark.asyncio
async def test_note_cannot_reference_an_unknown_user() -> None:
    """The database must reject a note without an existing owner."""

    with pytest.raises(Exception):
        await create_note_with_chunks(
            note_id=uuid4(),
            created_by=uuid4(),
            title="Orphan",
            content="INVALID",
            chunks=["INVALID"],
            embeddings=[[0.1] * 1536],
        )


@pytest.mark.asyncio
async def test_chunk_cannot_reference_an_unknown_note() -> None:
    """The database must reject a chunk without an existing note."""

    with pytest.raises(Exception):
        async with pool.connection() as connection, connection.transaction():
            await connection.execute(
                """
                INSERT INTO note_chunks (
                    id,
                    note_id,
                    chunk_index,
                    content,
                    embedding
                )
                VALUES (%s, %s, 0, 'INVALID', %s)
                """,
                (uuid4(), uuid4(), [0.1] * 1536),
            )

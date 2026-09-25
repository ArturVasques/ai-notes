"""
Persistence operations for application users.

Functions receive the connection from the calling service so provisioning
a user and its default categories can share one database transaction.

Used by:
- services/users_service.py

This repository contains PostgreSQL concerns only and knows nothing about
tokens or HTTP.
"""

from uuid import UUID

from psycopg import AsyncConnection
from psycopg.rows import class_row

from app.schemas.user import UserProfile


async def get_user_by_id(
    connection: AsyncConnection, *, user_id: UUID
) -> UserProfile | None:
    """Return the user with the supplied id, if it exists."""

    async with connection.cursor(row_factory=class_row(UserProfile)) as cursor:
        await cursor.execute(
            "SELECT id, name, email FROM users WHERE id = %s",
            (user_id,),
        )

        return await cursor.fetchone()


async def get_user_by_external_identity(
    connection: AsyncConnection, *, external_identity_id: str
) -> UserProfile | None:
    """Return the user mapped to an identity-provider id, if it exists."""

    async with connection.cursor(row_factory=class_row(UserProfile)) as cursor:
        await cursor.execute(
            "SELECT id, name, email FROM users WHERE external_identity_id = %s",
            (external_identity_id,),
        )

        return await cursor.fetchone()


async def insert_user_if_absent(
    connection: AsyncConnection,
    *,
    user_id: UUID,
    external_identity_id: str,
    name: str,
    email: str | None,
) -> bool:
    """
    Create the user unless one already exists for the external identity.

    Returns True when the row was inserted. Two concurrent first logins of
    the same person race safely: one inserts, the other gets False and
    re-reads the existing user.
    """

    async with connection.cursor() as cursor:
        await cursor.execute(
            """
            INSERT INTO users (id, external_identity_id, name, email)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (external_identity_id) DO NOTHING
            """,
            (user_id, external_identity_id, name, email),
        )

        return cursor.rowcount == 1


async def update_user_profile(
    connection: AsyncConnection,
    *,
    user_id: UUID,
    name: str,
    email: str | None,
) -> None:
    """Refresh the display name and email from the identity provider."""

    await connection.execute(
        "UPDATE users SET name = %s, email = %s WHERE id = %s",
        (name, email, user_id),
    )

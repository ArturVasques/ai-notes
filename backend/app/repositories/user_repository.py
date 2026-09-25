"""
Persistence operations for application users.

Used by:
- future authentication/user provisioning services.

This repository contains PostgreSQL concerns only and knows nothing about
HTTP authentication.
"""

from uuid import UUID

from app.database.connection import pool
from app.schemas.user import UserProfile


async def get_user_by_id(
    *,
    user_id: UUID,
) -> UserProfile | None:
    """Return the user with the supplied id, if it exists."""

    async with pool.connection() as connection, connection.cursor() as cursor:
        await cursor.execute(
            """
                SELECT id, name, email
                FROM users
                WHERE id = %s
                """,
            (user_id,),
        )

        row = await cursor.fetchone()

    if row is None:
        return None

    return UserProfile(
        id=row[0],
        name=row[1],
        email=row[2],
    )

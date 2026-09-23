"""
Persistence operations for application users.

Every user lookup is tenant-scoped.

Used by:
- user tools.
- future authentication/user services.

This repository contains PostgreSQL concerns only and knows nothing about
agents or HTTP authentication.
"""

from uuid import UUID

from app.database.connection import pool
from app.schemas.user import UserProfile


async def get_user_by_id(
    *,
    user_id: UUID,
    tenant_id: UUID,
) -> UserProfile | None:
    """Return a user only when they belong to the supplied tenant."""

    async with pool.connection() as connection, connection.cursor() as cursor:
        await cursor.execute(
            """
                SELECT id, name, email
                FROM users
                WHERE id = %s
                  AND tenant_id = %s
                """,
            (user_id, tenant_id),
        )

        row = await cursor.fetchone()

    if row is None:
        return None

    return UserProfile(
        id=row[0],
        name=row[1],
        email=row[2],
    )

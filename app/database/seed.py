"""
Development-only database seed.

Creates deterministic local identities required to exercise authenticated
application flows without an external identity provider.

Never run development seed data in production.
"""

import asyncio
from uuid import UUID

from app.core.config import AppEnv, get_settings
from app.core.event_loop import loop_factory
from app.database.connection import close_database_pool, open_database_pool, pool

USER_ID = UUID("22222222-2222-2222-2222-222222222222")


async def seed() -> None:
    """Insert the local development user."""

    settings = get_settings()

    if settings.app_env != AppEnv.DEVELOPMENT:
        raise RuntimeError("Development seed cannot run outside development")

    await open_database_pool()

    try:
        async with pool.connection() as connection, connection.transaction():
            await connection.execute(
                """
                    INSERT INTO users (
                        id,
                        external_identity_id,
                        name,
                        email
                    )
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                (
                    USER_ID,
                    "local-developer",
                    "Local Developer",
                    "developer@example.com",
                ),
            )

    finally:
        await close_database_pool()


if __name__ == "__main__":
    asyncio.run(
        seed(),
        loop_factory=loop_factory,
    )

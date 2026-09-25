"""
Pytest configuration for the integration test suite only.

The database pool follows the same lifecycle as the production application:
it is opened once for the test session and closed when the session finishes.
This fixture lives here (not in tests/conftest.py) so that `pytest tests/unit`
never needs a reachable PostgreSQL instance.

Every test creates its own users with random ids and deletes them at the
end; deleting a user cascades to all of its finance rows, so tests never
see each other's data.
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from uuid import UUID, uuid4

import pytest_asyncio

from app.auth.context import AppContext
from app.auth.permissions import FINANCE_READ, FINANCE_WRITE, PROFILE_READ
from app.core.event_loop import configure_windows_event_loop_policy
from app.database.connection import (
    close_database_pool,
    open_database_pool,
    pool,
)

configure_windows_event_loop_policy()

UserFactory = Callable[[], Awaitable[AppContext]]


@pytest_asyncio.fixture(scope="session", autouse=True)
async def database_pool() -> AsyncIterator[None]:
    """Keep the shared database pool alive for the complete test session."""

    await open_database_pool()

    yield

    await close_database_pool()


@pytest_asyncio.fixture
async def make_user() -> AsyncIterator[UserFactory]:
    """Create users on demand and delete them (and their data) afterwards."""

    created: list[UUID] = []

    async def factory() -> AppContext:
        user_id = uuid4()

        async with pool.connection() as connection, connection.transaction():
            await connection.execute(
                """
                INSERT INTO users (id, external_identity_id, name, email)
                VALUES (%s, %s, 'Test User', %s)
                """,
                (user_id, f"test-{user_id}", f"{user_id}@test.local"),
            )

        created.append(user_id)

        return AppContext(
            user_id=user_id,
            permissions=frozenset({FINANCE_READ, FINANCE_WRITE, PROFILE_READ}),
        )

    yield factory

    async with pool.connection() as connection, connection.transaction():
        await connection.execute("DELETE FROM users WHERE id = ANY(%s)", (created,))


@pytest_asyncio.fixture
async def user(make_user: UserFactory) -> AppContext:
    """Trusted context of the user under test."""

    return await make_user()


@pytest_asyncio.fixture
async def other_user(make_user: UserFactory) -> AppContext:
    """Trusted context of a second, unrelated user."""

    return await make_user()

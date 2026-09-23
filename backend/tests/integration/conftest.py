"""
Pytest configuration for the integration test suite only.

The database pool follows the same lifecycle as the production application:
it is opened once for the test session and closed when the session finishes.
This fixture lives here (not in tests/conftest.py) so that `pytest tests/unit`
never needs a reachable PostgreSQL instance.
"""

from collections.abc import AsyncIterator

import pytest_asyncio

from app.core.event_loop import configure_windows_event_loop_policy
from app.database.connection import (
    close_database_pool,
    open_database_pool,
)

configure_windows_event_loop_policy()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def database_pool() -> AsyncIterator[None]:
    """Keep the shared database pool alive for the complete test session."""

    await open_database_pool()

    yield

    await close_database_pool()

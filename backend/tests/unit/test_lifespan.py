"""
Regression tests for application startup and shutdown.

- If the database pool cannot be opened, startup must fail (uvicorn then
  exits non-zero) instead of serving requests without a database.
- Shutdown must always close the pool, and open/close must pair up exactly.

The real pool is never opened here: the lifespan hooks are replaced, so this
file runs with no PostgreSQL reachable like the rest of the unit suite (CI
enforces that by pointing POSTGRES_PORT at a closed port).
"""

import pytest
from fastapi.testclient import TestClient

import main


def test_startup_fails_when_database_pool_cannot_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unreachable() -> None:
        raise ConnectionError("could not connect to server")

    monkeypatch.setattr(main, "open_database_pool", unreachable)

    with pytest.raises(ConnectionError), TestClient(main.app):
        pass


def test_shutdown_closes_the_pool_after_successful_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    async def fake_open() -> None:
        events.append("open")

    async def fake_close() -> None:
        events.append("close")

    monkeypatch.setattr(main, "open_database_pool", fake_open)
    monkeypatch.setattr(main, "close_database_pool", fake_close)

    with TestClient(main.app) as client:
        assert client.get("/health/live").status_code == 200
        assert events == ["open"]

    assert events == ["open", "close"]

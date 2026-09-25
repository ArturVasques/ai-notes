"""
HTTP-level regression tests for the error contract and request correlation.

Bugs covered:
- a domain ValueError raised by a service used to surface as an unhandled
  500 with a traceback; it must be a 400 VALIDATION_ERROR.
- unexpected exceptions must be masked as 500 INTERNAL_ERROR without leaking
  the message, and still carry X-Request-ID (Starlette's ServerErrorMiddleware
  bypasses the request-id middleware on that path).
- NotFoundError, ConflictError and PermissionDeniedError map to 404, 409
  and 403 with the same body shape.
- CORS is closed unless origins are explicitly configured.

Failure paths use a small application wired exactly like main.py (error
handlers, then the request-id middleware) with routes that raise, because
the finance endpoints do not exist yet. Nothing opens a database pool.
"""

import re
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.cors import CORSMiddleware

import app.core.middleware as middleware
from app.api.errors import register_error_handlers
from app.core.config import AppSettings
from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError
from app.core.middleware import request_id_middleware
from main import app

UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def _app_with_failing_routes() -> FastAPI:
    failing = FastAPI()

    register_error_handlers(failing)
    failing.middleware("http")(request_id_middleware)

    @failing.get("/domain-error")
    async def domain_error() -> None:
        raise ValueError("Amount must be positive")

    @failing.get("/unexpected-error")
    async def unexpected_error() -> None:
        raise RuntimeError("database credentials are hunter2")

    @failing.get("/type-error")
    async def type_error() -> None:
        raise TypeError("unexpected keyword argument")

    @failing.get("/not-found")
    async def not_found() -> None:
        raise NotFoundError("Account not found")

    @failing.get("/conflict")
    async def conflict() -> None:
        raise ConflictError("An active account with this name already exists")

    @failing.get("/forbidden")
    async def forbidden() -> None:
        raise PermissionDeniedError("Insufficient permissions")

    return failing


@pytest.fixture
def client() -> Iterator[TestClient]:
    yield TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def failing_client() -> Iterator[TestClient]:
    yield TestClient(_app_with_failing_routes(), raise_server_exceptions=False)


def test_domain_value_error_returns_validation_error(
    failing_client: TestClient,
) -> None:
    response = failing_client.get("/domain-error")

    assert response.status_code == 400
    assert response.json() == {
        "code": "VALIDATION_ERROR",
        "message": "Amount must be positive",
    }
    assert UUID_PATTERN.match(response.headers["x-request-id"])


def test_unexpected_exception_is_masked_and_correlated(
    failing_client: TestClient,
) -> None:
    response = failing_client.get(
        "/unexpected-error", headers={"X-Request-ID": "corr-123"}
    )

    assert response.status_code == 500
    assert response.json() == {
        "code": "INTERNAL_ERROR",
        "message": "An unexpected error occurred",
    }
    assert "hunter2" not in response.text
    assert response.headers["x-request-id"] == "corr-123"


def test_type_error_is_masked_as_internal_error(failing_client: TestClient) -> None:
    response = failing_client.get("/type-error")

    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL_ERROR"


@pytest.mark.parametrize(
    ("path", "status_code", "code", "message"),
    [
        ("/not-found", 404, "NOT_FOUND", "Account not found"),
        (
            "/conflict",
            409,
            "CONFLICT",
            "An active account with this name already exists",
        ),
        ("/forbidden", 403, "FORBIDDEN", "Insufficient permissions"),
    ],
)
def test_application_errors_map_to_http_status(
    failing_client: TestClient, path: str, status_code: int, code: str, message: str
) -> None:
    response = failing_client.get(path)

    assert response.status_code == status_code
    assert response.json() == {"code": code, "message": message}
    assert UUID_PATTERN.match(response.headers["x-request-id"])


def test_request_id_is_generated_and_echoed(client: TestClient) -> None:
    generated = client.get("/health/live")
    echoed = client.get("/health/live", headers={"X-Request-ID": "trace-abc"})

    assert generated.status_code == 200
    assert UUID_PATTERN.match(generated.headers["x-request-id"])
    assert echoed.headers["x-request-id"] == "trace-abc"


def test_cors_is_closed_by_default(client: TestClient) -> None:
    response = client.get(
        "/health/live", headers={"Origin": "https://attacker.example"}
    )

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_api_metadata_uses_the_personal_finance_name(client: TestClient) -> None:
    assert app.title == "Personal Finance API"


def _settings_with_cors(origins: str, monkeypatch: pytest.MonkeyPatch) -> AppSettings:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("POSTGRES_PASSWORD", "unit-test-password")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", origins)

    return AppSettings(_env_file=None)


def test_configure_cors_adds_middleware_only_when_origins_are_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed = FastAPI()
    monkeypatch.setattr(
        middleware, "get_settings", lambda: _settings_with_cors("", monkeypatch)
    )
    middleware.configure_cors(closed)

    opened = FastAPI()
    monkeypatch.setattr(
        middleware,
        "get_settings",
        lambda: _settings_with_cors("http://localhost:4200", monkeypatch),
    )
    middleware.configure_cors(opened)

    assert all(m.cls is not CORSMiddleware for m in closed.user_middleware)
    assert any(m.cls is CORSMiddleware for m in opened.user_middleware)

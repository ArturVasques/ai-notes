"""
HTTP-level regression tests for the error contract and request correlation.

Bugs covered:
- an empty document used to surface as an unhandled 500 with a traceback;
  it must be a 400 VALIDATION_ERROR.
- unexpected exceptions must be masked as 500 INTERNAL_ERROR without leaking
  the message, and still carry X-Request-ID (Starlette's ServerErrorMiddleware
  bypasses the request-id middleware on that path).
- only AssistantContractError maps to 502 UPSTREAM_ERROR.
- CORS is closed unless origins are explicitly configured.

The app is used without its lifespan (no `with TestClient(...)`), so no
database pool is opened and nothing reaches OpenAI.
"""

import re
from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.cors import CORSMiddleware

import app.api.chat as chat_api
import app.api.documents as documents_api
import app.core.middleware as middleware
from app.auth.context import AppContext
from app.auth.dependencies import get_app_context
from app.auth.permissions import DOCUMENTS_CREATE, KNOWLEDGE_READ, PROFILE_READ
from app.core.config import AppSettings
from app.services.ai.agent_service import AssistantContractError
from main import app

UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def _trusted_context() -> AppContext:
    return AppContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        permissions=frozenset({KNOWLEDGE_READ, DOCUMENTS_CREATE, PROFILE_READ}),
    )


@pytest.fixture
def client() -> Iterator[TestClient]:
    app.dependency_overrides[get_app_context] = _trusted_context

    yield TestClient(app, raise_server_exceptions=False)

    app.dependency_overrides.clear()


def test_empty_document_returns_validation_error(client: TestClient) -> None:
    response = client.post(
        "/documents",
        files={"file": ("blank.txt", b"   \n\n  ", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json() == {
        "code": "VALIDATION_ERROR",
        "message": "Document contains no usable text",
    }
    assert UUID_PATTERN.match(response.headers["x-request-id"])


def test_text_plain_with_charset_parameter_is_accepted(client: TestClient) -> None:
    response = client.post(
        "/documents",
        files={"file": ("blank.txt", b"   ", "text/plain; charset=utf-8")},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_unexpected_exception_is_masked_and_correlated(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def explode(**kwargs: object) -> None:
        raise RuntimeError("database credentials are hunter2")

    monkeypatch.setattr(documents_api, "ingest_document", explode)

    response = client.post(
        "/documents",
        files={"file": ("doc.txt", b"some real content", "text/plain")},
        headers={"X-Request-ID": "corr-123"},
    )

    assert response.status_code == 500
    assert response.json() == {
        "code": "INTERNAL_ERROR",
        "message": "An unexpected error occurred",
    }
    assert "hunter2" not in response.text
    assert response.headers["x-request-id"] == "corr-123"


def test_unrelated_type_error_is_not_reported_as_upstream_failure(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def wrong_arity(**kwargs: object) -> None:
        raise TypeError("unexpected keyword argument")

    monkeypatch.setattr(documents_api, "ingest_document", wrong_arity)

    response = client.post(
        "/documents",
        files={"file": ("doc.txt", b"content", "text/plain")},
    )

    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL_ERROR"


def test_assistant_contract_violation_returns_upstream_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def broken_assistant(**kwargs: object) -> None:
        raise AssistantContractError("Assistant returned an unexpected output type")

    monkeypatch.setattr(chat_api, "run_assistant", broken_assistant)

    response = client.post("/chat", json={"message": "hello"})

    assert response.status_code == 502
    assert response.json() == {
        "code": "UPSTREAM_ERROR",
        "message": "The assistant returned an unexpected response",
    }
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

"""
Unit tests for the authentication boundary (Bearer → AppContext).

The token validator and the user provisioning are replaced, so nothing here
needs Entra or a database. HTTP-level cases use the real application: a
missing or malformed Bearer header must answer 401 without ever reaching
the network.
"""

from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

import app.auth.dependencies as dependencies
from app.auth.context import AppContext
from app.auth.jwt_validator import (
    AuthenticationError,
    IdentityProviderUnavailableError,
    TokenIdentity,
)
from app.auth.permissions import (
    AUTHENTICATED_USER_PERMISSIONS,
    FINANCE_READ,
    FINANCE_WRITE,
)
from app.core.errors import PermissionDeniedError
from app.schemas.user import UserProfile
from main import app

IDENTITY = TokenIdentity(
    external_identity_id="oid-1",
    tenant_id="tenant-1",
    name="Artur",
    preferred_username="artur@example.com",
    email=None,
    scopes=frozenset({"access_as_user"}),
)


def _bearer(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


async def test_missing_credentials_are_rejected_with_bearer_challenge() -> None:
    with pytest.raises(HTTPException) as error:
        await dependencies.get_app_context(credentials=None)

    assert error.value.status_code == 401
    assert error.value.headers == {"WWW-Authenticate": "Bearer"}


async def test_non_bearer_scheme_is_rejected() -> None:
    basic = HTTPAuthorizationCredentials(scheme="Basic", credentials="dXNlcjpwdw==")

    with pytest.raises(HTTPException) as error:
        await dependencies.get_app_context(credentials=basic)

    assert error.value.status_code == 401


async def test_invalid_token_is_rejected_without_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def reject(token: str) -> TokenIdentity:
        raise AuthenticationError("InvalidAudienceError")

    monkeypatch.setattr(dependencies, "validate_access_token", reject)

    with pytest.raises(HTTPException) as error:
        await dependencies.get_app_context(credentials=_bearer("token"))

    assert error.value.status_code == 401
    assert error.value.detail == "Authentication required"


async def test_unavailable_identity_provider_answers_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unavailable(token: str) -> TokenIdentity:
        raise IdentityProviderUnavailableError("JWKS unavailable")

    monkeypatch.setattr(dependencies, "validate_access_token", unavailable)

    with pytest.raises(HTTPException) as error:
        await dependencies.get_app_context(credentials=_bearer("token"))

    assert error.value.status_code == 503


async def test_valid_token_builds_context_from_the_internal_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    internal_id = uuid4()
    seen: list[TokenIdentity] = []

    async def accept(token: str) -> TokenIdentity:
        assert token == "valid-token"
        return IDENTITY

    async def provision(identity: TokenIdentity) -> UserProfile:
        seen.append(identity)
        return UserProfile(id=internal_id, name="Artur", email=None)

    monkeypatch.setattr(dependencies, "validate_access_token", accept)
    monkeypatch.setattr(dependencies, "get_or_provision_user", provision)

    context = await dependencies.get_app_context(credentials=_bearer("valid-token"))

    assert context.user_id == internal_id
    assert context.permissions == AUTHENTICATED_USER_PERMISSIONS
    assert seen == [IDENTITY]


def test_require_permission_raises_when_missing() -> None:
    context = AppContext(user_id=uuid4(), permissions=frozenset({FINANCE_READ}))

    context.require_permission(FINANCE_READ)

    with pytest.raises(PermissionDeniedError):
        context.require_permission(FINANCE_WRITE)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("path", ["/me", "/accounts", "/transactions"])
def test_endpoints_without_authorization_answer_401(
    client: TestClient, path: str
) -> None:
    response = client.get(path)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "authorization",
    ["Bearer not-a-jwt", "Basic dXNlcjpwdw==", "Bearer", "Token abc"],
)
def test_malformed_authorization_headers_answer_401(
    client: TestClient, authorization: str
) -> None:
    response = client.get("/me", headers={"Authorization": authorization})

    assert response.status_code == 401

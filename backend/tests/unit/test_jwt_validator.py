"""
Unit tests for Entra access token validation. No network, no database.

Tokens are signed with a throwaway RSA key generated per test session; the
JWKS lookup is replaced so the validator sees that key as the tenant's
published signing key. Every rejection path is exercised: the validator
must fail closed and never trust a claim before the signature is verified.
"""

import base64
import hashlib
import hmac
import json
import time
from collections.abc import Callable
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError

import app.auth.jwt_validator as jwt_validator
from app.auth.jwt_validator import (
    AuthenticationError,
    IdentityProviderUnavailableError,
    validate_access_token,
)
from app.core.config import AppEnv, AppSettings

TENANT_ID = "11111111-1111-1111-1111-111111111111"
API_CLIENT_ID = "22222222-2222-2222-2222-222222222222"
OTHER_ID = "33333333-3333-3333-3333-333333333333"
OID = "44444444-4444-4444-4444-444444444444"
ISSUER = f"https://login.microsoftonline.com/{TENANT_ID}/v2.0"

TokenFactory = Callable[..., str]


class _SigningKey:
    def __init__(self, public_pem: bytes) -> None:
        self.key = public_pem


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


@pytest.fixture(scope="module")
def rsa_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="module")
def private_pem(rsa_key: rsa.RSAPrivateKey) -> bytes:
    return rsa_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )


@pytest.fixture(scope="module")
def public_pem(rsa_key: rsa.RSAPrivateKey) -> bytes:
    return rsa_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )


@pytest.fixture(autouse=True)
def entra_settings(monkeypatch: pytest.MonkeyPatch, public_pem: bytes) -> None:
    settings = AppSettings(
        _env_file=None,
        app_env=AppEnv.TEST,
        postgres_password="unused",
        entra_tenant_id=TENANT_ID,
        entra_api_client_id=API_CLIENT_ID,
    )
    monkeypatch.setattr(jwt_validator, "get_settings", lambda: settings)

    async def published_key(token: str) -> _SigningKey:
        return _SigningKey(public_pem)

    monkeypatch.setattr(jwt_validator, "fetch_signing_key", published_key)


@pytest.fixture
def make_token(private_pem: bytes) -> TokenFactory:
    def factory(
        *, algorithm: str = "RS256", key: bytes | None = None, **overrides: Any
    ) -> str:
        now = int(time.time())
        claims: dict[str, Any] = {
            "aud": API_CLIENT_ID,
            "iss": ISSUER,
            "iat": now - 10,
            "nbf": now - 10,
            "exp": now + 600,
            "oid": OID,
            "tid": TENANT_ID,
            "ver": "2.0",
            "scp": "access_as_user",
            "name": "Artur",
            "preferred_username": "artur@example.com",
            "sub": "subject",
        }

        for name, value in overrides.items():
            if value is None:
                claims.pop(name, None)
            else:
                claims[name] = value

        return jwt.encode(
            claims, key or private_pem, algorithm=algorithm, headers={"kid": "test"}
        )

    return factory


async def test_valid_token_yields_the_identity(make_token: TokenFactory) -> None:
    identity = await validate_access_token(make_token())

    assert identity.external_identity_id == OID
    assert identity.tenant_id == TENANT_ID
    assert identity.name == "Artur"
    assert identity.preferred_username == "artur@example.com"
    assert identity.email is None
    assert identity.scopes == {"access_as_user"}


async def test_extra_scopes_and_email_are_carried(make_token: TokenFactory) -> None:
    identity = await validate_access_token(
        make_token(scp="access_as_user other.scope", email=" a@b.c ")
    )

    assert identity.scopes == {"access_as_user", "other.scope"}
    assert identity.email == "a@b.c"


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"aud": OTHER_ID}, "InvalidAudienceError"),
        (
            {"iss": f"https://login.microsoftonline.com/{OTHER_ID}/v2.0"},
            "InvalidIssuerError",
        ),
        ({"iss": f"https://sts.windows.net/{TENANT_ID}/"}, "InvalidIssuerError"),
        ({"exp": int(time.time()) - 120}, "ExpiredSignatureError"),
        ({"nbf": int(time.time()) + 600}, "ImmatureSignatureError"),
        ({"oid": None}, "MissingRequiredClaimError"),
        ({"scp": None}, "MissingRequiredClaimError"),
        ({"ver": None}, "MissingRequiredClaimError"),
        ({"tid": OTHER_ID}, "another tenant"),
        ({"ver": "1.0"}, "Unsupported token version"),
        ({"scp": "other.scope"}, "Required scope missing"),
        ({"scp": ""}, "Required scope missing"),
        ({"oid": "   "}, "Missing object id"),
    ],
)
async def test_invalid_claims_are_rejected(
    make_token: TokenFactory, overrides: dict[str, Any], reason: str
) -> None:
    with pytest.raises(AuthenticationError, match=reason):
        await validate_access_token(make_token(**overrides))


async def test_token_signed_by_another_key_is_rejected(
    make_token: TokenFactory,
) -> None:
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_pem = other.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )

    with pytest.raises(AuthenticationError, match="InvalidSignatureError"):
        await validate_access_token(make_token(key=other_pem))


async def test_symmetric_algorithm_confusion_is_rejected(
    make_token: TokenFactory, public_pem: bytes
) -> None:
    """A token HMAC-signed with the public key must not verify as RS256."""

    # PyJWT refuses to *create* such a token, so it is assembled by hand:
    # the classic attack where the server's public key is used as the HMAC
    # secret of an HS256 token.
    now = int(time.time())
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT", "kid": "test"}).encode())
    payload = _b64url(
        json.dumps(
            {
                "aud": API_CLIENT_ID,
                "iss": ISSUER,
                "iat": now,
                "nbf": now,
                "exp": now + 600,
                "oid": OID,
                "tid": TENANT_ID,
                "ver": "2.0",
                "scp": "access_as_user",
            }
        ).encode()
    )
    signing_input = f"{header}.{payload}".encode()
    signature = _b64url(hmac.new(public_pem, signing_input, hashlib.sha256).digest())

    with pytest.raises(AuthenticationError, match="InvalidAlgorithmError"):
        await validate_access_token(f"{header}.{payload}.{signature}")


async def test_none_algorithm_is_rejected(make_token: TokenFactory) -> None:
    now = int(time.time())
    unsigned = jwt.encode(
        {
            "aud": API_CLIENT_ID,
            "iss": ISSUER,
            "iat": now,
            "nbf": now,
            "exp": now + 600,
            "oid": OID,
            "tid": TENANT_ID,
            "ver": "2.0",
            "scp": "access_as_user",
        },
        key="",
        algorithm="none",
    )

    with pytest.raises(AuthenticationError, match="InvalidAlgorithmError"):
        await validate_access_token(unsigned)


async def test_garbage_token_is_rejected_before_any_key_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Real key resolution: a malformed token fails at header parsing,
    # before any HTTP request could be made.
    async def real_lookup(token: str) -> Any:
        return await jwt_validator.run_in_threadpool(
            jwt_validator.get_jwks_client().get_signing_key_from_jwt, token
        )

    monkeypatch.setattr(jwt_validator, "fetch_signing_key", real_lookup)

    with pytest.raises(AuthenticationError, match="DecodeError"):
        await validate_access_token("not-a-jwt")


async def test_unknown_signing_key_is_rejected(
    monkeypatch: pytest.MonkeyPatch, make_token: TokenFactory
) -> None:
    async def unknown_kid(token: str) -> Any:
        raise PyJWKClientError("Unable to find a signing key that matches")

    monkeypatch.setattr(jwt_validator, "fetch_signing_key", unknown_kid)

    with pytest.raises(AuthenticationError, match="PyJWKClientError"):
        await validate_access_token(make_token())


async def test_unreachable_jwks_is_reported_as_provider_unavailable(
    monkeypatch: pytest.MonkeyPatch, make_token: TokenFactory
) -> None:
    async def unreachable(token: str) -> Any:
        raise PyJWKClientConnectionError("connection refused")

    monkeypatch.setattr(jwt_validator, "fetch_signing_key", unreachable)

    with pytest.raises(IdentityProviderUnavailableError):
        await validate_access_token(make_token())


def test_jwks_client_targets_the_tenant_discovery_endpoint() -> None:
    jwt_validator.get_jwks_client.cache_clear()

    client = jwt_validator.get_jwks_client()

    assert (
        client.uri
        == f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys"
    )

    jwt_validator.get_jwks_client.cache_clear()

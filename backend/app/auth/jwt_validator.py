"""
Validation of Microsoft Entra ID access tokens (v2).

A request is trusted only after every check below passes:

1. the token is a well-formed JWT whose `kid` matches a key currently
   published by the tenant (JWKS, fetched over HTTPS and cached);
2. the RS256 signature verifies against that key;
3. `exp`, `nbf` and `iat` are valid (with a small clock leeway);
4. `iss` is this tenant's v2 issuer and `aud` is this API's client id;
5. `ver` is "2.0" and `tid` is this tenant (single-tenant application);
6. `scp` contains the configured delegated scope.

Decoding a JWT is not validating it: nothing in this module trusts a claim
before the signature has been verified. The token itself is never logged.

Multi-tenant note: this application is single-tenant, so `oid` alone
identifies a user. Accepting several tenants would require the pair
(`tid`, `oid`) as the external identity.

Used by:
- app/auth/dependencies.py to build AppContext from a Bearer token.
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import jwt
from jwt import PyJWKClient
from jwt.exceptions import (
    InvalidTokenError,
    PyJWKClientConnectionError,
    PyJWKClientError,
)
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings

ALLOWED_ALGORITHMS = ["RS256"]
CLOCK_LEEWAY_SECONDS = 30
JWKS_CACHE_SECONDS = 3600

REQUIRED_CLAIMS = ["aud", "iss", "exp", "iat", "nbf", "oid", "tid", "ver", "scp"]


class AuthenticationError(Exception):
    """The token is missing, malformed or fails validation (HTTP 401)."""


class IdentityProviderUnavailableError(Exception):
    """The tenant's signing keys could not be fetched (HTTP 503)."""


@dataclass(frozen=True)
class TokenIdentity:
    """The validated identity carried by an access token."""

    external_identity_id: str
    """Entra object id (`oid`): stable per user in this tenant."""

    tenant_id: str
    name: str | None
    preferred_username: str | None
    email: str | None
    scopes: frozenset[str]


@lru_cache
def get_jwks_client() -> PyJWKClient:
    """Shared JWKS client; keys are cached so most requests never hit HTTP."""

    return PyJWKClient(
        get_settings().entra_jwks_url,
        cache_keys=True,
        lifespan=JWKS_CACHE_SECONDS,
    )


async def fetch_signing_key(token: str) -> Any:
    """
    Resolve the public key that signed the token from the tenant's JWKS.

    PyJWKClient uses blocking HTTP, so it runs in the thread pool.
    """

    return await run_in_threadpool(get_jwks_client().get_signing_key_from_jwt, token)


async def validate_access_token(token: str) -> TokenIdentity:
    """Validate a Bearer token and return the identity it proves."""

    settings = get_settings()

    try:
        signing_key = await fetch_signing_key(token)
    except PyJWKClientConnectionError as exc:
        raise IdentityProviderUnavailableError("JWKS unavailable") from exc
    except (PyJWKClientError, InvalidTokenError) as exc:
        raise AuthenticationError(
            f"Signing key not resolved: {type(exc).__name__}"
        ) from exc

    try:
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=ALLOWED_ALGORITHMS,
            audience=settings.entra_api_client_id,
            issuer=settings.entra_issuer,
            leeway=CLOCK_LEEWAY_SECONDS,
            options={"require": REQUIRED_CLAIMS},
        )
    except InvalidTokenError as exc:
        raise AuthenticationError(type(exc).__name__) from exc

    if claims["ver"] != "2.0":
        raise AuthenticationError("Unsupported token version")

    if claims["tid"] != settings.entra_tenant_id:
        raise AuthenticationError("Token issued for another tenant")

    scopes = frozenset(str(claims["scp"]).split())

    if settings.entra_required_scope not in scopes:
        raise AuthenticationError("Required scope missing")

    oid = str(claims["oid"]).strip()

    if not oid:
        raise AuthenticationError("Missing object id")

    return TokenIdentity(
        external_identity_id=oid,
        tenant_id=str(claims["tid"]),
        name=_optional_string(claims.get("name")),
        preferred_username=_optional_string(claims.get("preferred_username")),
        email=_optional_string(claims.get("email")),
        scopes=scopes,
    )


def _optional_string(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()

    return None

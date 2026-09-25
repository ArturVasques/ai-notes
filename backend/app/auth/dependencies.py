"""
FastAPI authentication boundary.

Converts the `Authorization: Bearer <token>` header into a trusted
AppContext:

    Bearer JWT → validation (jwt_validator) → Entra `oid`
    → internal User (provisioned on first login) → AppContext

Identity never comes from any other header or from the request body.
Failures answer 401 with a generic message: the exact reason is logged
server-side, without the token, so nothing about the token contract leaks
to a caller probing the API.

Used by:
- every finance and profile endpoint through `Depends(get_app_context)`.
- tests, which replace this dependency with `app.dependency_overrides` to
  run without an identity provider.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.context import AppContext
from app.auth.jwt_validator import (
    AuthenticationError,
    IdentityProviderUnavailableError,
    validate_access_token,
)
from app.auth.permissions import AUTHENTICATED_USER_PERMISSIONS
from app.core.logging import get_logger
from app.services.users_service import get_or_provision_user

logger = get_logger()

# auto_error=False so a missing header is answered by this module (401 with
# WWW-Authenticate) instead of FastAPI's default 403.
bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_app_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AppContext:
    """Authenticate the request and return the caller's trusted context."""

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()

    try:
        identity = await validate_access_token(credentials.credentials)
    except AuthenticationError as exc:
        logger.warning("access_token_rejected", reason=str(exc))
        raise _unauthorized() from exc
    except IdentityProviderUnavailableError as exc:
        logger.error("identity_provider_unavailable", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Identity provider unavailable",
        ) from exc

    user = await get_or_provision_user(identity)

    return AppContext(
        user_id=user.id,
        permissions=AUTHENTICATED_USER_PERMISSIONS,
    )

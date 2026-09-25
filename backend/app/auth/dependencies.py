"""
FastAPI authentication boundary.

This module converts authenticated HTTP identity into trusted AppContext.

Development currently uses explicit headers so the complete architecture can
run locally without requiring an external identity provider.

Production:
Replace the development implementation with Entra ID JWT validation while
keeping AppContext and all downstream services unchanged.

Security:
Development header authentication must never be enabled in production.
"""

from uuid import UUID

from fastapi import Header, HTTPException, status

from app.auth.context import AppContext
from app.auth.permissions import FINANCE_READ, FINANCE_WRITE, PROFILE_READ
from app.core.config import AppEnv, get_settings

settings = get_settings()


async def get_app_context(
    x_user_id: UUID | None = Header(default=None),
) -> AppContext:
    """
    Build trusted application context for a local development request.

    Production implementations must derive identity from a validated token,
    never from caller-controlled identity headers.

    Development header authentication is possible only when APP_ENV is
    exactly `development`. There is no default APP_ENV: an unset or
    misconfigured value fails settings loading at startup instead of
    silently falling back to a permissive mode.
    """

    if settings.app_env != AppEnv.DEVELOPMENT:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Production identity provider is not configured",
        )

    if x_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Development identity header is required",
        )

    return AppContext(
        user_id=x_user_id,
        permissions=frozenset(
            {
                FINANCE_READ,
                FINANCE_WRITE,
                PROFILE_READ,
            }
        ),
    )

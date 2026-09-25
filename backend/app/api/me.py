"""
HTTP API for the authenticated user's own profile.

Also the simplest authenticated call, useful to verify the complete
Angular → MSAL → Bearer → FastAPI → AppContext flow.
"""

from fastapi import APIRouter, Depends

from app.auth.context import AppContext
from app.auth.dependencies import get_app_context
from app.schemas.user import UserProfile
from app.services import users_service

router = APIRouter(
    prefix="/me",
    tags=["Profile"],
)


@router.get("", response_model=UserProfile)
async def get_me(context: AppContext = Depends(get_app_context)) -> UserProfile:
    """Return the caller's profile as provisioned from the identity provider."""

    return await users_service.get_profile(context)

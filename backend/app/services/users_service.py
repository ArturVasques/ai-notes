"""
Application service for users: just-in-time provisioning on first login.

The identity provider authenticates; this service maps the proven identity
(`oid`) to an internal user. The internal UUID is what every finance row
references, so a change of identity provider would only touch this mapping.

Used by:
- app/auth/dependencies.py on every authenticated request.
- api/me.py
"""

from uuid import uuid4

from app.auth.context import AppContext
from app.auth.jwt_validator import TokenIdentity
from app.auth.permissions import PROFILE_READ
from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.database.connection import pool
from app.repositories import user_repository
from app.schemas.user import UserProfile
from app.services.finance.categories_service import provision_default_categories

logger = get_logger()

FALLBACK_DISPLAY_NAME = "User"


def display_name(identity: TokenIdentity) -> str:
    """Name shown in the application, with a safe fallback."""

    return identity.name or identity.preferred_username or FALLBACK_DISPLAY_NAME


async def get_or_provision_user(identity: TokenIdentity) -> UserProfile:
    """
    Return the internal user for a validated identity, creating it on the
    first login together with its default categories.

    The profile (name, email) is refreshed from the token when it changed,
    so renaming in Entra is reflected here. Email is informational only and
    never used as an identity key.
    """

    name = display_name(identity)

    async with pool.connection() as connection, connection.transaction():
        user = await user_repository.get_user_by_external_identity(
            connection, external_identity_id=identity.external_identity_id
        )

        if user is None:
            user_id = uuid4()

            created = await user_repository.insert_user_if_absent(
                connection,
                user_id=user_id,
                external_identity_id=identity.external_identity_id,
                name=name,
                email=identity.email,
            )

            if created:
                await provision_default_categories(connection, user_id=user_id)
                logger.info("user_provisioned", user_id=str(user_id))

            user = await user_repository.get_user_by_external_identity(
                connection, external_identity_id=identity.external_identity_id
            )

            assert user is not None
            return user

        if user.name != name or user.email != identity.email:
            await user_repository.update_user_profile(
                connection, user_id=user.id, name=name, email=identity.email
            )
            user = UserProfile(id=user.id, name=name, email=identity.email)

    return user


async def get_profile(context: AppContext) -> UserProfile:
    """Return the authenticated user's own profile."""

    context.require_permission(PROFILE_READ)

    async with pool.connection() as connection:
        user = await user_repository.get_user_by_id(connection, user_id=context.user_id)

    if user is None:
        raise NotFoundError("User not found")

    return user

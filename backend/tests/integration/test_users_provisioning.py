"""
Integration tests for just-in-time user provisioning.

A validated identity (Entra `oid`) is mapped to an internal user on first
login, together with the default categories. Later logins reuse the same
internal id, refresh the profile, and never duplicate categories.
"""

import asyncio
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest_asyncio

from app.auth.context import AppContext
from app.auth.jwt_validator import TokenIdentity
from app.auth.permissions import AUTHENTICATED_USER_PERMISSIONS
from app.database.connection import pool
from app.services import users_service
from app.services.finance import categories_service
from app.services.finance.categories_service import DEFAULT_CATEGORIES


def _identity(
    oid: str,
    *,
    name: str | None = "Artur",
    preferred_username: str | None = "artur@example.com",
    email: str | None = None,
) -> TokenIdentity:
    return TokenIdentity(
        external_identity_id=oid,
        tenant_id="tenant-1",
        name=name,
        preferred_username=preferred_username,
        email=email,
        scopes=frozenset({"access_as_user"}),
    )


@pytest_asyncio.fixture
async def oid() -> AsyncIterator[str]:
    """A fresh external identity, deleted (with its data) after the test."""

    external_identity_id = f"oid-{uuid4()}"

    yield external_identity_id

    async with pool.connection() as connection, connection.transaction():
        await connection.execute(
            "DELETE FROM users WHERE external_identity_id = %s",
            (external_identity_id,),
        )


async def test_first_login_creates_the_user_and_default_categories(
    oid: str,
) -> None:
    user = await users_service.get_or_provision_user(_identity(oid))
    context = AppContext(user_id=user.id, permissions=AUTHENTICATED_USER_PERMISSIONS)

    categories = await categories_service.list_categories(context)
    profile = await users_service.get_profile(context)

    assert user.name == "Artur"
    assert user.email is None
    assert len(categories) == len(DEFAULT_CATEGORIES)
    assert profile == user


async def test_later_logins_reuse_the_same_internal_user(oid: str) -> None:
    first = await users_service.get_or_provision_user(_identity(oid))
    second = await users_service.get_or_provision_user(_identity(oid))
    context = AppContext(user_id=first.id, permissions=AUTHENTICATED_USER_PERMISSIONS)

    categories = await categories_service.list_categories(context)

    assert second.id == first.id
    assert len(categories) == len(DEFAULT_CATEGORIES)


async def test_concurrent_first_logins_create_one_user(oid: str) -> None:
    users = await asyncio.gather(
        *(users_service.get_or_provision_user(_identity(oid)) for _ in range(4))
    )
    context = AppContext(
        user_id=users[0].id, permissions=AUTHENTICATED_USER_PERMISSIONS
    )

    categories = await categories_service.list_categories(context)

    assert len({user.id for user in users}) == 1
    assert len(categories) == len(DEFAULT_CATEGORIES)


async def test_profile_is_refreshed_from_the_token(oid: str) -> None:
    created = await users_service.get_or_provision_user(_identity(oid))

    renamed = await users_service.get_or_provision_user(
        _identity(oid, name="Artur V.", email="artur@example.com")
    )

    assert renamed.id == created.id
    assert renamed.name == "Artur V."
    assert renamed.email == "artur@example.com"


async def test_display_name_falls_back_safely(oid: str) -> None:
    without_name = await users_service.get_or_provision_user(
        _identity(oid, name=None, preferred_username="artur@example.com")
    )
    anonymous = await users_service.get_or_provision_user(
        _identity(oid, name=None, preferred_username=None)
    )

    assert without_name.name == "artur@example.com"
    assert anonymous.name == users_service.FALLBACK_DISPLAY_NAME


async def test_two_identities_may_share_an_email(oid: str) -> None:
    """Email is informational: it must never block provisioning."""

    other_oid = f"oid-{uuid4()}"

    try:
        first = await users_service.get_or_provision_user(
            _identity(oid, email="shared@example.com")
        )
        second = await users_service.get_or_provision_user(
            _identity(other_oid, email="shared@example.com")
        )

        assert first.id != second.id
    finally:
        async with pool.connection() as connection, connection.transaction():
            await connection.execute(
                "DELETE FROM users WHERE external_identity_id = %s", (other_oid,)
            )

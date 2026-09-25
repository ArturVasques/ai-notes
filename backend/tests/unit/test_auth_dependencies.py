"""
Regression tests for the development authentication boundary.

Bug covered: header identity (X-User-Id) must be possible only
when APP_ENV is exactly `development`. Any other environment fails closed
with 501 until a real identity provider is wired in.
"""

from uuid import uuid4

import pytest
from fastapi import HTTPException

import app.auth.dependencies as dependencies
from app.auth.context import AppContext
from app.auth.permissions import FINANCE_READ, FINANCE_WRITE, PROFILE_READ
from app.core.config import AppEnv, AppSettings
from app.core.errors import PermissionDeniedError


def _settings_for(app_env: AppEnv, monkeypatch: pytest.MonkeyPatch) -> AppSettings:
    monkeypatch.setenv("APP_ENV", app_env.value)
    monkeypatch.setenv("POSTGRES_PASSWORD", "unit-test-password")

    return AppSettings(_env_file=None)


@pytest.mark.parametrize("app_env", [AppEnv.PRODUCTION, AppEnv.TEST])
async def test_header_identity_is_rejected_outside_development(
    monkeypatch: pytest.MonkeyPatch, app_env: AppEnv
) -> None:
    monkeypatch.setattr(dependencies, "settings", _settings_for(app_env, monkeypatch))

    with pytest.raises(HTTPException) as error:
        await dependencies.get_app_context(x_user_id=uuid4())

    assert error.value.status_code == 501


async def test_development_requires_the_identity_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        dependencies, "settings", _settings_for(AppEnv.DEVELOPMENT, monkeypatch)
    )

    with pytest.raises(HTTPException) as error:
        await dependencies.get_app_context(x_user_id=None)

    assert error.value.status_code == 401


async def test_development_builds_trusted_context_from_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        dependencies, "settings", _settings_for(AppEnv.DEVELOPMENT, monkeypatch)
    )
    user_id = uuid4()

    context = await dependencies.get_app_context(x_user_id=user_id)

    assert context.user_id == user_id
    assert context.permissions == {FINANCE_READ, FINANCE_WRITE, PROFILE_READ}


def test_require_permission_raises_when_missing() -> None:
    context = AppContext(user_id=uuid4(), permissions=frozenset({FINANCE_READ}))

    context.require_permission(FINANCE_READ)

    with pytest.raises(PermissionDeniedError):
        context.require_permission(FINANCE_WRITE)

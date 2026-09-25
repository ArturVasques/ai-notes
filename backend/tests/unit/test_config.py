"""
Regression tests for configuration fail-safes.

Bugs covered:
- APP_ENV used to default to "development", which silently enabled header
  authentication in any deployment that forgot to set it.

All settings objects are built with `_env_file=None` so the developer's local
`.env` never leaks into these assertions.
"""

import pytest
from pydantic import ValidationError

from app.core.config import AppEnv, AppSettings

APP_ENV_VARIABLES = (
    "APP_ENV",
    "POSTGRES_DB",
    "POSTGRES_PASSWORD",
)


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in APP_ENV_VARIABLES:
        monkeypatch.delenv(variable, raising=False)

    monkeypatch.setenv("POSTGRES_PASSWORD", "unit-test-password")


def test_missing_app_env_fails_settings_loading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValidationError) as error:
        AppSettings(_env_file=None)

    failing_fields = {str(item["loc"][0]) for item in error.value.errors()}

    assert failing_fields == {"app_env"}


def test_unknown_app_env_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "staging")

    with pytest.raises(ValidationError):
        AppSettings(_env_file=None)


@pytest.mark.parametrize("value", ["development", "test", "production"])
def test_supported_app_env_values_parse_to_the_enum(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("APP_ENV", value)

    settings = AppSettings(_env_file=None)

    assert settings.app_env is AppEnv(value)


def test_cors_is_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")

    settings = AppSettings(_env_file=None)

    assert settings.cors_allowed_origins == ""


def test_default_database_is_personal_finance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")

    settings = AppSettings(_env_file=None)

    assert settings.postgres_db == "personal_finance"

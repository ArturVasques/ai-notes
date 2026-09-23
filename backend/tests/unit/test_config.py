"""
Regression tests for configuration fail-safes.

Bugs covered:
- APP_ENV used to default to "development", which silently enabled header
  authentication in any deployment that forgot to set it.
- OPENAI_EMBEDDING_MODEL was a free-form value, so a model with a different
  dimensionality than the VECTOR(1536) column only failed at the first insert.

All settings objects are built with `_env_file=None` so the developer's local
`.env` never leaks into these assertions.
"""

import pytest
from pydantic import ValidationError

from app.core.config import (
    EMBEDDING_MODEL_DIMENSIONS,
    NOTE_CHUNKS_EMBEDDING_DIMENSION,
    AISettings,
    AppEnv,
    AppSettings,
)

APP_ENV_VARIABLES = (
    "APP_ENV",
    "POSTGRES_PASSWORD",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "OPENAI_EMBEDDING_MODEL",
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


def test_embedding_model_with_incompatible_dimension_fails_early(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-key")
    monkeypatch.setenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")

    assert EMBEDDING_MODEL_DIMENSIONS["text-embedding-3-large"] != (
        NOTE_CHUNKS_EMBEDDING_DIMENSION
    )

    with pytest.raises(ValidationError, match="VECTOR\\(1536\\)"):
        AISettings(_env_file=None)


def test_unknown_embedding_model_fails_early(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-key")
    monkeypatch.setenv("OPENAI_EMBEDDING_MODEL", "some-future-model")

    with pytest.raises(ValidationError, match="Unsupported OPENAI_EMBEDDING_MODEL"):
        AISettings(_env_file=None)


def test_compatible_embedding_model_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-key")
    monkeypatch.setenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

    settings = AISettings(_env_file=None)

    assert EMBEDDING_MODEL_DIMENSIONS[settings.openai_embedding_model] == (
        NOTE_CHUNKS_EMBEDDING_DIMENSION
    )


def test_empty_openai_api_key_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")

    with pytest.raises(ValidationError):
        AISettings(_env_file=None)

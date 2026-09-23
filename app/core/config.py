"""
Central application configuration.

All configuration is loaded from environment variables or the local `.env`
file through Pydantic Settings.

Configuration is split by concern so that infrastructure code never has to
satisfy AI-only requirements:

- `AppSettings` covers application/runtime, PostgreSQL and RAG configuration.
  It has no dependency on OpenAI credentials, so Alembic migrations and the
  database connection pool can be configured without an OpenAI API key.
- `AISettings` covers OpenAI model configuration.

Used by:
- database/connection.py and migrations/env.py for PostgreSQL configuration
  (AppSettings only).
- app/auth/dependencies.py for the APP_ENV fail-safe check (AppSettings).
- AI services (embedding_service, openai bootstrap, assistant agent) for
  model configuration (AISettings).
- RAG services for retrieval configuration (AppSettings).
- application startup for environment and logging settings (AppSettings).

Production environments should inject these values through the deployment
platform rather than shipping a `.env` file.
"""

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Contract between the configured embedding model and the fixed
# `VECTOR(1536)` column defined in
# migrations/versions/aa7cc31ac6dd_create_initial_schema.py.
#
# The embedding model is not a free-form value: changing it to a model that
# produces a different dimensionality requires a schema migration and
# re-embedding every existing note chunk.
EMBEDDING_MODEL_DIMENSIONS: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}

NOTE_CHUNKS_EMBEDDING_DIMENSION = 1536


class AppEnv(StrEnum):
    """Deployment environment. Controls fail-safe behaviour such as dev auth."""

    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class AppSettings(BaseSettings):
    """Application, infrastructure and RAG configuration."""

    # Application
    app_env: AppEnv
    log_level: str = "INFO"
    cors_allowed_origins: str = ""

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "ai_notes"
    postgres_user: str = "postgres"
    postgres_password: str

    # RAG
    rag_top_k: int = 5
    rag_max_distance: float = 0.8

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class AISettings(BaseSettings):
    """OpenAI model configuration.

    Kept separate from AppSettings so that infrastructure code (Alembic,
    the database pool) never requires an OpenAI API key.
    """

    openai_api_key: str = Field(min_length=1)
    openai_model: str = "gpt-5.6-luna"
    openai_embedding_model: str = "text-embedding-3-small"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def _validate_embedding_dimension(self) -> "AISettings":
        """Fail fast when the embedding model does not match the schema."""

        dimension = EMBEDDING_MODEL_DIMENSIONS.get(self.openai_embedding_model)

        if dimension is None:
            raise ValueError(
                f"Unsupported OPENAI_EMBEDDING_MODEL "
                f"'{self.openai_embedding_model}'. Supported models: "
                f"{sorted(EMBEDDING_MODEL_DIMENSIONS)}."
            )

        if dimension != NOTE_CHUNKS_EMBEDDING_DIMENSION:
            raise ValueError(
                f"OPENAI_EMBEDDING_MODEL '{self.openai_embedding_model}' "
                f"produces {dimension}-dimension embeddings, but the "
                f"note_chunks schema is fixed at "
                f"VECTOR({NOTE_CHUNKS_EMBEDDING_DIMENSION}). Changing the "
                "embedding model requires a schema migration and "
                "re-embedding every existing note chunk."
            )

        return self


@lru_cache
def get_settings() -> AppSettings:
    """
    Return the application settings singleton.

    Caching avoids repeatedly parsing environment configuration throughout
    the application.
    """
    return AppSettings()


@lru_cache
def get_ai_settings() -> AISettings:
    """Return the OpenAI settings singleton."""
    return AISettings()

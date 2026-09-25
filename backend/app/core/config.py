"""
Central application configuration.

All configuration is loaded from environment variables or the local `.env`
file through Pydantic Settings.

Used by:
- database/connection.py and alembic/env.py for PostgreSQL configuration.
- app/auth/dependencies.py for the APP_ENV fail-safe check.
- core/middleware.py for CORS.
- application startup for environment and logging settings.

Production environments should inject these values through the deployment
platform rather than shipping a `.env` file.
"""

from enum import StrEnum
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(StrEnum):
    """Deployment environment. Controls fail-safe behaviour such as dev auth."""

    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class AppSettings(BaseSettings):
    """Application and infrastructure configuration."""

    # Application
    app_env: AppEnv
    log_level: str = "INFO"
    cors_allowed_origins: str = ""

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "personal_finance"
    postgres_user: str = "postgres"
    postgres_password: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> AppSettings:
    """
    Return the application settings singleton.

    Caching avoids repeatedly parsing environment configuration throughout
    the application.
    """
    return AppSettings()

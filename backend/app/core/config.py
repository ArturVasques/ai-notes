"""
Central application configuration.

All configuration is loaded from environment variables or the local `.env`
file through Pydantic Settings.

Used by:
- database/connection.py and alembic/env.py for PostgreSQL configuration.
- app/auth/jwt_validator.py for the Microsoft Entra ID token contract.
- core/middleware.py for CORS.
- application startup for environment and logging settings.

Production environments should inject these values through the deployment
platform rather than shipping a `.env` file.

The Entra values are configuration, not secrets: the tenant id and the API
client id are public identifiers that also appear in the frontend. No client
secret is ever needed, because the API only validates tokens.
"""

from enum import StrEnum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(StrEnum):
    """Deployment environment. Controls fail-safe behaviour such as logging."""

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

    # Microsoft Entra ID (access tokens v2). Required, no defaults: an API
    # that cannot validate tokens must not start.
    entra_tenant_id: str = Field(min_length=1)
    entra_api_client_id: str = Field(min_length=1)
    entra_required_scope: str = Field(default="access_as_user", min_length=1)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def entra_issuer(self) -> str:
        """Expected `iss` claim of a v2 access token from this tenant."""
        return f"https://login.microsoftonline.com/{self.entra_tenant_id}/v2.0"

    @property
    def entra_jwks_url(self) -> str:
        """Where the tenant publishes its token signing keys."""
        return (
            f"https://login.microsoftonline.com/{self.entra_tenant_id}"
            "/discovery/v2.0/keys"
        )


@lru_cache
def get_settings() -> AppSettings:
    """
    Return the application settings singleton.

    Caching avoids repeatedly parsing environment configuration throughout
    the application.
    """
    return AppSettings()

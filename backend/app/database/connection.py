"""
PostgreSQL connection infrastructure.

Provides the shared asynchronous connection pool used by repositories.

Used by:
- FastAPI lifespan to open and close database connections.
- repositories to acquire PostgreSQL connections.

The API is asynchronous, so database I/O also uses psycopg's
AsyncConnectionPool instead of blocking the event loop with synchronous I/O.
"""

from psycopg_pool import AsyncConnectionPool

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger()


pool = AsyncConnectionPool(
    conninfo="",
    kwargs={
        "host": settings.postgres_host,
        "port": settings.postgres_port,
        "dbname": settings.postgres_db,
        "user": settings.postgres_user,
        "password": settings.postgres_password,
    },
    min_size=1,
    max_size=10,
    open=False,
)


POOL_STARTUP_TIMEOUT_SECONDS = 15.0


async def open_database_pool() -> None:
    """
    Open the shared database connection pool during application startup.

    Startup is intentionally fail-fast: if PostgreSQL is not reachable within
    the timeout the error is logged once with the target host and re-raised,
    so the process exits instead of serving requests without a database.
    Connection retries belong to the orchestrator (Docker/Kubernetes restart
    policies), not to the application.
    """

    try:
        await pool.open()
        await pool.wait(timeout=POOL_STARTUP_TIMEOUT_SECONDS)
    except Exception as exc:
        await pool.close()
        logger.error(
            "database_pool_unavailable",
            host=settings.postgres_host,
            port=settings.postgres_port,
            database=settings.postgres_db,
            timeout_seconds=POOL_STARTUP_TIMEOUT_SECONDS,
            error=str(exc),
        )
        raise

    logger.info(
        "database_pool_started",
        host=settings.postgres_host,
        database=settings.postgres_db,
        min_size=pool.min_size,
        max_size=pool.max_size,
    )


async def close_database_pool() -> None:
    """Close all pooled connections during application shutdown."""

    if pool.closed:
        return

    await pool.close()

    logger.info("database_pool_closed")

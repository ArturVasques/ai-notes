"""
Personal Finance application entry point.

Responsibilities:
- configure application-wide infrastructure.
- manage startup/shutdown resources through FastAPI lifespan.
- register HTTP routers.

Business logic must not be implemented in this file.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.accounts import router as accounts_router
from app.api.categories import router as categories_router
from app.api.errors import register_error_handlers
from app.api.health import router as health_router
from app.api.investment_assets import router as investment_assets_router
from app.api.me import router as me_router
from app.api.reports import router as reports_router
from app.api.transactions import router as transactions_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.middleware import configure_cors, request_id_middleware
from app.database.connection import (
    close_database_pool,
    open_database_pool,
)

configure_logging()
logger = get_logger()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Manage infrastructure resources for the application lifecycle.

    Startup fails loudly: if the database pool cannot be opened the exception
    propagates to uvicorn, which logs "Application startup failed" and exits
    with a non-zero status. Shutdown always closes the pool, even when the
    server is stopping because of an error.
    """

    logger.info("application_starting", app_env=settings.app_env)

    try:
        await open_database_pool()
    except Exception:
        logger.error("application_startup_failed")
        raise

    logger.info("application_started")

    try:
        yield
    finally:
        logger.info("application_stopping")
        await close_database_pool()
        logger.info("application_stopped")


app = FastAPI(
    title="Personal Finance API",
    version="0.1.0",
    lifespan=lifespan,
)

register_error_handlers(app)
configure_cors(app)
app.middleware("http")(request_id_middleware)

app.include_router(health_router)
app.include_router(me_router)
app.include_router(accounts_router)
app.include_router(categories_router)
app.include_router(investment_assets_router)
app.include_router(transactions_router)
app.include_router(reports_router)

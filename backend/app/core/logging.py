"""
Application logging configuration.

The application uses structured logs so production systems can search,
aggregate and correlate events instead of parsing arbitrary text.

In production these logs can be collected by platforms such as
Azure Monitor / Application Insights.
"""

import logging
import sys
from typing import Any

import structlog

from app.core.config import get_settings


def configure_logging() -> None:
    """Configure standard Python logging and structlog."""

    settings = get_settings()

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=settings.log_level.upper(),
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger() -> Any:
    """
    Return a structured application logger.

    structlog's lazy proxy resolves to the configured wrapper class
    (structlog.stdlib.BoundLogger) only on first use, so `Any` is the
    honest static type here rather than a class we don't fully control.
    """
    return structlog.get_logger()

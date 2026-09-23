"""
Cross-cutting HTTP concerns: request correlation and CORS.

Used by:
- main.py during application startup.
"""

import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import FastAPI, Request, Response
from starlette.middleware.cors import CORSMiddleware

from app.core.config import get_settings

REQUEST_ID_HEADER = "X-Request-ID"


async def request_id_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """
    Bind a request id into structlog context and echo it back to the caller.

    A caller-supplied X-Request-ID is trusted only as a correlation hint
    (never as identity or authorization) and propagated as-is; otherwise a
    new one is generated.

    Registered via app.middleware("http") in main.py, i.e. as
    BaseHTTPMiddleware rather than pure ASGI middleware. main.py registers
    this AFTER configure_cors(app): Starlette's add_middleware() prepends to
    the stack, so this ends up outermost and X-Request-ID also reaches CORS
    preflight/error responses. Registering it before configure_cors would
    silently break that header propagation for those responses.

    The request id is also stashed on request.state. A handler registered
    for the exact `Exception` class (the app/api/errors.py masked-500
    fallback) is special-cased by Starlette into ServerErrorMiddleware,
    which wraps the ENTIRE middleware stack including this one - so when
    that handler produces the response, execution never returns to the
    `response.headers[...] = request_id` line below. app/api/errors.py
    reads request.state.request_id itself so every error response still
    carries the header, not just the ones handled by inner middleware.
    """

    request_id = request.headers.get(REQUEST_ID_HEADER, str(uuid.uuid4()))
    request.state.request_id = request_id

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)

    response = await call_next(request)
    response.headers[REQUEST_ID_HEADER] = request_id

    return response


def configure_cors(app: FastAPI) -> None:
    """
    Enable CORS only when allowed origins are explicitly configured.

    CORS_ALLOWED_ORIGINS is a comma-separated list of origins. An empty
    value disables CORS entirely, which is the safe default.
    """

    settings = get_settings()

    origins = [
        origin.strip()
        for origin in settings.cors_allowed_origins.split(",")
        if origin.strip()
    ]

    if not origins:
        return

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

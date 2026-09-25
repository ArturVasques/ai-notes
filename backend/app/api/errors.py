"""
Uniform HTTP error handling.

Domain ValueErrors raised by services (a business rule rejecting the
request) become a consistent 400 JSON body instead of an unhandled 500 with
a leaked traceback. The application errors in app/core/errors.py map to 403,
404 and 409 with the same body shape. Every other unexpected exception is
logged with structlog and returns a generic body that never leaks internals
to the client.

A handler registered for the exact `Exception` class (the masked-500
fallback below) is special-cased by Starlette into ServerErrorMiddleware,
which wraps the entire middleware stack including app/core/middleware.py's
request_id_middleware. That means the response it produces never passes
back through request_id_middleware's own header-setting code, so every
handler here reads the request id from request.state directly (set by
request_id_middleware before call_next) and attaches it itself, instead of
relying on the middleware to do it on the way out.

Used by:
- main.py to register exception handlers.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError
from app.core.logging import get_logger
from app.core.middleware import REQUEST_ID_HEADER

logger = get_logger()


def _error_response(
    request: Request, status_code: int, code: str, message: str
) -> JSONResponse:
    response = JSONResponse(
        status_code=status_code,
        content={"code": code, "message": message},
    )

    request_id = getattr(request.state, "request_id", None)

    if request_id is not None:
        response.headers[REQUEST_ID_HEADER] = request_id

    return response


async def handle_value_error(request: Request, exc: Exception) -> JSONResponse:
    """Translate a domain validation failure into a 400 response."""

    logger.warning(
        "request_validation_error",
        path=request.url.path,
        error=str(exc),
    )

    return _error_response(
        request, status.HTTP_400_BAD_REQUEST, "VALIDATION_ERROR", str(exc)
    )


async def handle_not_found_error(request: Request, exc: Exception) -> JSONResponse:
    """Translate a missing (or not owned) resource into a 404 response."""

    return _error_response(request, status.HTTP_404_NOT_FOUND, "NOT_FOUND", str(exc))


async def handle_conflict_error(request: Request, exc: Exception) -> JSONResponse:
    """Translate a state conflict into a 409 response."""

    logger.info("request_conflict", path=request.url.path, error=str(exc))

    return _error_response(request, status.HTTP_409_CONFLICT, "CONFLICT", str(exc))


async def handle_permission_denied_error(
    request: Request, exc: Exception
) -> JSONResponse:
    """Translate a missing permission into a 403 response."""

    logger.warning("permission_denied", path=request.url.path)

    return _error_response(request, status.HTTP_403_FORBIDDEN, "FORBIDDEN", str(exc))


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Log and mask any exception not translated to a specific response."""

    logger.error(
        "unhandled_exception",
        path=request.url.path,
        error_type=type(exc).__name__,
        error=str(exc),
    )

    return _error_response(
        request,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "INTERNAL_ERROR",
        "An unexpected error occurred",
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register uniform error handlers for the application."""

    app.add_exception_handler(ValueError, handle_value_error)
    app.add_exception_handler(NotFoundError, handle_not_found_error)
    app.add_exception_handler(ConflictError, handle_conflict_error)
    app.add_exception_handler(PermissionDeniedError, handle_permission_denied_error)
    app.add_exception_handler(Exception, handle_unexpected_error)

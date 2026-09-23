"""
Uniform HTTP error handling.

Domain ValueErrors raised by services (e.g. ingestion_service rejecting an
empty note) become a consistent 400 JSON body instead of an unhandled
500 with a leaked traceback. An AssistantContractError from the assistant
output contract becomes a 502 instead of a stack trace. Every other
unexpected exception is logged with structlog and returns a generic body
that never leaks internals to the client.

AssistantContractError (not TypeError) is registered deliberately: mapping
every TypeError app-wide to "the assistant returned an unexpected response"
would misclassify an unrelated bug elsewhere in the request path (e.g. a
wrong-arity call in a repository) as an AI upstream failure, actively
misleading incident triage. Only the one narrow, intentional failure mode
in agent_service.py should ever produce a 502 here; any other TypeError
falls through to handle_unexpected_error's masked 500, which is correct.

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

from app.core.logging import get_logger
from app.core.middleware import REQUEST_ID_HEADER
from app.services.ai.agent_service import AssistantContractError

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


async def handle_assistant_contract_error(
    request: Request, exc: Exception
) -> JSONResponse:
    """Translate an unexpected assistant output contract failure into 502."""

    logger.error(
        "assistant_output_contract_violation",
        path=request.url.path,
        error=str(exc),
    )

    return _error_response(
        request,
        status.HTTP_502_BAD_GATEWAY,
        "UPSTREAM_ERROR",
        "The assistant returned an unexpected response",
    )


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
    app.add_exception_handler(AssistantContractError, handle_assistant_contract_error)
    app.add_exception_handler(Exception, handle_unexpected_error)

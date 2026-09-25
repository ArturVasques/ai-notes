"""
Application error types shared by services and the HTTP error handlers.

Services raise these instead of HTTP exceptions so the same rules can be
reused by future non-HTTP callers (AI agent tools, MCP, workers).

Validation failures keep using the built-in ValueError, which
app/api/errors.py maps to 400.

Used by:
- app/auth/context.py for permission checks.
- application services.
- app/api/errors.py to translate them into HTTP responses.
"""


class NotFoundError(Exception):
    """
    The requested resource does not exist for the authenticated user.

    Another user's resource is reported exactly like a missing one, so
    responses never reveal that it exists.
    """


class ConflictError(Exception):
    """The request conflicts with the current state (duplicate, in use)."""


class PermissionDeniedError(Exception):
    """The authenticated caller lacks the permission for the operation."""

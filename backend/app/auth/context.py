"""
Trusted identity and authorization context.

AppContext is created by the application after authentication and is passed
to application services as trusted runtime context. Future AI agent tools
will receive the same context; neither a request body nor a model ever
chooses user_id or permissions.

Used by:
- authentication layer to represent the authenticated caller.
- API endpoints and application services to enforce user boundaries.
"""

from dataclasses import dataclass
from uuid import UUID

from app.core.errors import PermissionDeniedError


@dataclass(frozen=True)
class AppContext:
    """Trusted identity and permissions for one authenticated request."""

    user_id: UUID
    permissions: frozenset[str]

    def has_permission(self, permission: str) -> bool:
        """Return whether the authenticated user owns a permission."""
        return permission in self.permissions

    def require_permission(self, permission: str) -> None:
        """Raise PermissionDeniedError unless the user owns the permission."""

        if not self.has_permission(permission):
            raise PermissionDeniedError("Insufficient permissions")

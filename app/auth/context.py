"""
Trusted identity and authorization context.

AppContext is created by the application after authentication and is passed
to agents and tools as trusted runtime context.

The LLM never chooses user_id or permissions.

Used by:
- authentication layer to represent the authenticated caller.
- Agents SDK Runner as execution context.
- tools to enforce user boundaries.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AppContext:
    """Trusted identity and permissions for one agent execution."""

    user_id: UUID
    permissions: frozenset[str]

    def has_permission(self, permission: str) -> bool:
        """Return whether the authenticated user owns a permission."""
        return permission in self.permissions

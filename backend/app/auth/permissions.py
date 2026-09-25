"""
Central registry of permission strings.

Every protected operation checks an explicit permission the same way, using
AppContext.has_permission / require_permission. Keeping the permission names
here (instead of duplicating string literals) avoids typos causing silent
permission checks that never match.

Today every authenticated user owns the full set: the application manages
one person's finances, so there are no roles yet. The set exists so that
future AI agent tools or restricted clients can be granted less.

Used by:
- application services to check the caller's trusted AppContext.permissions.
- app/auth/dependencies.py to grant the authenticated-user set.
"""

FINANCE_READ = "finance:read"
FINANCE_WRITE = "finance:write"
PROFILE_READ = "profile:read"

AUTHENTICATED_USER_PERMISSIONS = frozenset({FINANCE_READ, FINANCE_WRITE, PROFILE_READ})

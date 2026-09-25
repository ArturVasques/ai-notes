"""
Central registry of permission strings.

Every protected operation checks an explicit permission the same way, using
AppContext.has_permission. Keeping the permission names here (instead of
duplicating string literals) avoids typos causing silent permission checks
that never match.

Used by:
- API endpoints and application services to check the caller's trusted
  AppContext.permissions.
- app/auth/dependencies.py to grant the local development permission set.
"""

FINANCE_READ = "finance:read"
FINANCE_WRITE = "finance:write"
PROFILE_READ = "profile:read"

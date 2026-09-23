"""
Central registry of tool permission strings.

Every agent tool checks an explicit permission the same way, using
AppContext.has_permission. Keeping the permission names here (instead of
duplicating string literals) avoids typos causing silent permission checks
that never match.

Used by:
- app/tools/*.py to check the caller's trusted AppContext.permissions.
- app/auth/dependencies.py to grant the local development permission set.
- evals/run_evals.py to build the evaluation AppContext.
"""

KNOWLEDGE_READ = "knowledge:read"
NOTES_CREATE = "notes:create"
PROFILE_READ = "profile:read"

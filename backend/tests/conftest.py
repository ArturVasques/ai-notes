"""
Shared pytest configuration for the whole test suite.

Unit tests (tests/unit) must be runnable with no database reachable, so the
database pool lifecycle lives only in tests/integration/conftest.py, not
here. Do not add a database-dependent fixture to this file.

The Entra identifiers are required settings. Tests never contact Entra:
the unit suite builds its own settings or replaces the token validator, and
the integration suite replaces the authentication dependency. These
placeholders only let the application module load when a developer runs
the suite without them in the environment.
"""

import os

os.environ.setdefault("ENTRA_TENANT_ID", "00000000-0000-0000-0000-000000000000")
os.environ.setdefault("ENTRA_API_CLIENT_ID", "00000000-0000-0000-0000-000000000000")

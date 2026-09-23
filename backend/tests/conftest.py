"""
Shared pytest configuration for the whole test suite.

Unit tests (tests/unit) must be runnable with no database reachable, so the
database pool lifecycle lives only in tests/integration/conftest.py, not
here. Do not add a database-dependent fixture to this file.
"""

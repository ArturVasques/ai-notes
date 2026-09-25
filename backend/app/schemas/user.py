"""
User contracts exposed outside the persistence layer.

Used by:
- user repository and users service.
- api/me.py

Database rows should not leak directly into API responses: the external
identity id is intentionally not part of the public profile.
"""

from uuid import UUID

from pydantic import BaseModel


class UserProfile(BaseModel):
    """Public application representation of a user."""

    id: UUID
    name: str
    email: str | None

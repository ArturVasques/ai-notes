"""
User contracts exposed outside the persistence layer.

Used by:
- user repository.
- future HTTP APIs and services.

Database rows should not leak directly into API responses.
"""

from uuid import UUID

from pydantic import BaseModel


class UserProfile(BaseModel):
    """Public application representation of a user."""

    id: UUID
    name: str
    email: str

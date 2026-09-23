"""
User contracts exposed outside the persistence layer.

Used by:
- user repository.
- agent tools.
- future HTTP APIs.

Database rows should not leak directly into agents or API responses.
"""

from uuid import UUID

from pydantic import BaseModel


class UserProfile(BaseModel):
    """Public application representation of a user."""

    id: UUID
    name: str
    email: str

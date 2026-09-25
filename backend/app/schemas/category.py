"""
HTTP and service contracts for user-managed income and expense categories.

The icon is a stable key (e.g. "utensils", "shopping-cart") that the
frontend resolves through its own allowlist. Arbitrary SVG or HTML is never
stored; the key format is validated here and by a database CHECK.

Used by:
- api/categories.py
- services/finance/categories_service.py
- repositories/category_repository.py
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.schemas.common import Name

ICON_PATTERN = r"^[a-z0-9-]{1,40}$"

IconKey = Annotated[str, StringConstraints(pattern=ICON_PATTERN)]


class CategoryKind(StrEnum):
    """Which transaction kind a category classifies."""

    EXPENSE = "EXPENSE"
    INCOME = "INCOME"


class CategoryCreate(BaseModel):
    """Category submitted by the authenticated user."""

    model_config = ConfigDict(extra="forbid")

    name: Name
    kind: CategoryKind
    icon: IconKey


class CategoryUpdate(BaseModel):
    """
    Partial category update. Only the fields sent are changed.

    The kind cannot change: transactions already classified by the category
    must keep a category of their own kind.
    """

    model_config = ConfigDict(extra="forbid")

    name: Name | None = None
    icon: IconKey | None = None
    archived: bool | None = None


class Category(BaseModel):
    """Category returned to the owner."""

    id: UUID
    name: str
    kind: CategoryKind
    icon: str
    archived_at: datetime | None
    created_at: datetime

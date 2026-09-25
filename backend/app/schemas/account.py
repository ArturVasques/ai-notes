"""
HTTP and service contracts for accounts: the places where money exists.

Used by:
- api/accounts.py
- services/finance/accounts_service.py
- repositories/account_repository.py
"""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.common import Currency, Description, Name, SignedAmountMinor


class AccountType(StrEnum):
    """Small fixed set of account types (see docs/DOMAIN_MODEL.md)."""

    CHECKING = "CHECKING"
    SAVINGS = "SAVINGS"
    CASH = "CASH"
    BENEFITS = "BENEFITS"
    BROKERAGE = "BROKERAGE"


class AccountCreate(BaseModel):
    """Account submitted by the authenticated user."""

    model_config = ConfigDict(extra="forbid")

    name: Name
    type: AccountType
    description: Description | None = None
    currency: Currency = "EUR"
    opening_balance_minor: SignedAmountMinor = 0


class AccountUpdate(BaseModel):
    """
    Partial account update. Only the fields sent are changed.

    `archived` archives (true) or restores (false) the account. The currency
    cannot change once transactions may reference the account.
    """

    model_config = ConfigDict(extra="forbid")

    name: Name | None = None
    type: AccountType | None = None
    description: Description | None = None
    opening_balance_minor: SignedAmountMinor | None = None
    archived: bool | None = None


class Account(BaseModel):
    """Account returned to the owner."""

    id: UUID
    name: str
    type: AccountType
    description: str | None
    currency: str
    opening_balance_minor: int
    archived_at: datetime | None
    created_at: datetime

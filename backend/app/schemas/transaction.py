"""
HTTP and service contracts for transactions: one typed row per financial
movement (see docs/DOMAIN_MODEL.md, section 2).

`TransactionCreate` is a union discriminated by `kind`. Each member lists
exactly the references its kind requires and forbids every other field, so
the request shape already matches the database shape CHECK. The same union
is intended to become the structured output of "AI proposes a transaction".

Used by:
- api/transactions.py
- services/finance/transactions_service.py
- repositories/transaction_repository.py
"""

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from app.schemas.common import Description, PositiveAmountMinor


class TransactionKind(StrEnum):
    """The five kinds of financial movement."""

    INCOME = "INCOME"
    EXPENSE = "EXPENSE"
    TRANSFER = "TRANSFER"
    INVESTMENT = "INVESTMENT"
    REIMBURSEMENT = "REIMBURSEMENT"


class _TransactionCreateBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount_minor: PositiveAmountMinor
    occurred_on: date
    description: Description | None = None


class ExpenseCreate(_TransactionCreateBase):
    """Money spent from an account, classified by an expense category."""

    kind: Literal[TransactionKind.EXPENSE]
    from_account_id: UUID
    category_id: UUID


class IncomeCreate(_TransactionCreateBase):
    """Money earned into an account, classified by an income category."""

    kind: Literal[TransactionKind.INCOME]
    to_account_id: UUID
    category_id: UUID


class TransferCreate(_TransactionCreateBase):
    """Money moved between two of the user's own accounts."""

    kind: Literal[TransactionKind.TRANSFER]
    from_account_id: UUID
    to_account_id: UUID

    @model_validator(mode="after")
    def _accounts_differ(self) -> Self:
        if self.from_account_id == self.to_account_id:
            raise ValueError("A transfer needs two different accounts")

        return self


class InvestmentCreate(_TransactionCreateBase):
    """Money put from an account into an investment asset."""

    kind: Literal[TransactionKind.INVESTMENT]
    from_account_id: UUID
    investment_asset_id: UUID


class ReimbursementCreate(_TransactionCreateBase):
    """Money paid back into an account for an earlier expense."""

    kind: Literal[TransactionKind.REIMBURSEMENT]
    to_account_id: UUID
    reimburses_transaction_id: UUID


TransactionCreate = Annotated[
    ExpenseCreate
    | IncomeCreate
    | TransferCreate
    | InvestmentCreate
    | ReimbursementCreate,
    Field(discriminator="kind"),
]

transaction_create_adapter: TypeAdapter[TransactionCreate] = TypeAdapter(
    TransactionCreate
)

# Fields each kind carries besides the common amount/date/description.
KIND_REFERENCE_FIELDS: dict[TransactionKind, tuple[str, ...]] = {
    TransactionKind.EXPENSE: ("from_account_id", "category_id"),
    TransactionKind.INCOME: ("to_account_id", "category_id"),
    TransactionKind.TRANSFER: ("from_account_id", "to_account_id"),
    TransactionKind.INVESTMENT: ("from_account_id", "investment_asset_id"),
    TransactionKind.REIMBURSEMENT: ("to_account_id", "reimburses_transaction_id"),
}


class TransactionUpdate(BaseModel):
    """
    Partial transaction update. Only the fields sent are changed.

    The kind cannot change (delete and recreate instead). The merged result
    must still be a valid transaction of the existing kind: sending a
    reference that the kind does not use is rejected.
    """

    model_config = ConfigDict(extra="forbid")

    amount_minor: PositiveAmountMinor | None = None
    occurred_on: date | None = None
    description: Description | None = None
    from_account_id: UUID | None = None
    to_account_id: UUID | None = None
    category_id: UUID | None = None
    investment_asset_id: UUID | None = None
    reimburses_transaction_id: UUID | None = None


class Transaction(BaseModel):
    """
    Transaction returned to the owner.

    `reimbursed_amount_minor` is the sum of reimbursements linked to this
    transaction (always 0 for kinds other than EXPENSE).
    """

    id: UUID
    kind: TransactionKind
    amount_minor: int
    occurred_on: date
    description: str | None
    from_account_id: UUID | None
    to_account_id: UUID | None
    category_id: UUID | None
    investment_asset_id: UUID | None
    reimburses_transaction_id: UUID | None
    reimbursed_amount_minor: int
    created_at: datetime
    updated_at: datetime


class TransactionFilters(BaseModel):
    """
    History filters. Dates are inclusive.

    `account_id` matches either side of a movement. `category_id` also
    matches reimbursements of expenses in that category, because a
    reimbursement inherits its expense's category.
    """

    date_from: date | None = None
    date_to: date | None = None
    kind: TransactionKind | None = None
    category_id: UUID | None = None
    account_id: UUID | None = None
    investment_asset_id: UUID | None = None

    @model_validator(mode="after")
    def _period_is_ordered(self) -> Self:
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("'from' must not be after 'to'")

        return self


class TransactionPage(BaseModel):
    """One page of history, newest first."""

    items: list[Transaction]
    next_cursor: str | None

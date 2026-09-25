"""
Contracts for the deterministic financial reports (docs/DOMAIN_MODEL.md,
section 3). Every amount is an integer number of minor units.

Two kinds of numbers live here and must not be confused:
- flow metrics for a period (income, expenses, savings, cash flow);
- stock values at a point in time (account balances).

Used by:
- api/reports.py, api/accounts.py
- services/finance/reports_service.py, accounts_service.py
"""

from datetime import date
from typing import Self
from uuid import UUID

from pydantic import BaseModel, model_validator

from app.schemas.account import Account
from app.schemas.category import CategoryKind
from app.schemas.investment_asset import InvestmentAssetType


class Period(BaseModel):
    """Inclusive date range of a report."""

    date_from: date
    date_to: date

    @model_validator(mode="after")
    def _is_ordered(self) -> Self:
        if self.date_from > self.date_to:
            raise ValueError("'from' must not be after 'to'")

        return self


class SavingsAllocation(BaseModel):
    """Where the period's net savings went. The three lines add up."""

    savings_accounts_minor: int
    investments_minor: int
    retained_cash_minor: int


class FinancialOverview(BaseModel):
    """Headline metrics of a period."""

    date_from: date
    date_to: date

    income_minor: int
    gross_expenses_minor: int
    reimbursements_attributed_minor: int
    effective_expenses_minor: int

    net_savings_minor: int
    savings_rate: float | None
    allocation: SavingsAllocation

    reimbursements_received_minor: int
    net_cash_flow_minor: int
    transfers_minor: int


class CategoryBreakdownItem(BaseModel):
    """Effective amount of one category in the period."""

    category_id: UUID
    name: str
    icon: str
    kind: CategoryKind
    archived: bool
    gross_minor: int
    reimbursed_minor: int
    effective_minor: int
    transaction_count: int


class CategoryBreakdown(BaseModel):
    """Categories of one kind, largest effective amount first."""

    date_from: date
    date_to: date
    kind: CategoryKind
    total_minor: int
    items: list[CategoryBreakdownItem]


class SavingsAccountMovement(BaseModel):
    """Net movement of one savings account in the period."""

    account_id: UUID
    name: str
    archived: bool
    inflows_minor: int
    outflows_minor: int
    net_minor: int


class SavingsSummary(BaseModel):
    """Net savings, rate and allocation with the savings accounts detail."""

    date_from: date
    date_to: date
    income_minor: int
    effective_expenses_minor: int
    net_savings_minor: int
    savings_rate: float | None
    allocation: SavingsAllocation
    savings_accounts: list[SavingsAccountMovement]


class InvestmentByAsset(BaseModel):
    investment_asset_id: UUID
    name: str
    symbol: str | None
    type: InvestmentAssetType
    archived: bool
    invested_minor: int
    transaction_count: int


class InvestmentBySource(BaseModel):
    account_id: UUID
    name: str
    invested_minor: int


class InvestmentSummary(BaseModel):
    """Money put into investments, by asset and by source account."""

    date_from: date | None
    date_to: date | None
    total_invested_minor: int
    by_asset: list[InvestmentByAsset]
    by_source_account: list[InvestmentBySource]


class MonthlyPoint(BaseModel):
    """One calendar month of the trend."""

    month: str
    """`YYYY-MM`."""

    income_minor: int
    gross_expenses_minor: int
    effective_expenses_minor: int
    net_savings_minor: int
    savings_rate: float | None
    savings_accounts_minor: int
    invested_minor: int
    retained_cash_minor: int
    net_cash_flow_minor: int


class MonthlyTrend(BaseModel):
    months: list[MonthlyPoint]


class AccountBalance(BaseModel):
    """Stock value: opening balance plus every movement up to `as_of`."""

    account: Account
    balance_minor: int


class AccountBalances(BaseModel):
    as_of: date | None
    items: list[AccountBalance]
    total_minor: int

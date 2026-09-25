"""
Small builders for integration tests. They go through the application
services, so every row they create obeys the same rules as production data.
"""

from datetime import date
from typing import Any
from uuid import UUID

from app.auth.context import AppContext
from app.schemas.account import Account, AccountCreate, AccountType
from app.schemas.category import Category, CategoryCreate, CategoryKind
from app.schemas.investment_asset import (
    InvestmentAsset,
    InvestmentAssetCreate,
    InvestmentAssetType,
)
from app.schemas.transaction import Transaction, transaction_create_adapter
from app.services.finance import (
    accounts_service,
    categories_service,
    investment_assets_service,
    transactions_service,
)

DAY = date(2026, 9, 10)


async def account(
    context: AppContext,
    name: str = "Current Account",
    account_type: AccountType = AccountType.CHECKING,
) -> Account:
    return await accounts_service.create_account(
        context, AccountCreate(name=name, type=account_type)
    )


async def category(
    context: AppContext,
    name: str = "Restaurants",
    kind: CategoryKind = CategoryKind.EXPENSE,
    icon: str = "utensils",
) -> Category:
    return await categories_service.create_category(
        context, CategoryCreate(name=name, kind=kind, icon=icon)
    )


async def asset(
    context: AppContext,
    name: str = "S&P 500",
    symbol: str | None = None,
    asset_type: InvestmentAssetType = InvestmentAssetType.ETF,
) -> InvestmentAsset:
    return await investment_assets_service.create_investment_asset(
        context, InvestmentAssetCreate(name=name, symbol=symbol, type=asset_type)
    )


async def transaction(context: AppContext, **fields: Any) -> Transaction:
    """Create a transaction from raw fields (kind, amount_minor, ...)."""

    fields.setdefault("occurred_on", DAY)

    return await transactions_service.create_transaction(
        context, transaction_create_adapter.validate_python(fields)
    )


async def expense(
    context: AppContext,
    *,
    from_account_id: UUID,
    category_id: UUID,
    amount_minor: int = 10_000,
    occurred_on: date = DAY,
) -> Transaction:
    return await transaction(
        context,
        kind="EXPENSE",
        amount_minor=amount_minor,
        occurred_on=occurred_on,
        from_account_id=from_account_id,
        category_id=category_id,
    )


async def reimbursement(
    context: AppContext,
    *,
    to_account_id: UUID,
    expense_id: UUID,
    amount_minor: int,
    occurred_on: date = DAY,
) -> Transaction:
    return await transaction(
        context,
        kind="REIMBURSEMENT",
        amount_minor=amount_minor,
        occurred_on=occurred_on,
        to_account_id=to_account_id,
        reimburses_transaction_id=expense_id,
    )

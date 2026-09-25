"""
Integration tests for transaction history: ordering, filters, keyset
pagination and isolation between users.
"""

from datetime import date
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.auth.context import AppContext
from app.schemas.account import AccountType
from app.schemas.category import CategoryKind
from app.schemas.transaction import TransactionFilters, TransactionKind
from app.services.finance import transactions_service
from tests.integration import factories


async def _ids(context: AppContext, **filters: object) -> list[UUID]:
    page = await transactions_service.list_transactions(
        context, TransactionFilters.model_validate(filters), limit=200
    )

    return [item.id for item in page.items]


async def _scenario(context: AppContext) -> SimpleNamespace:
    """A small month of movements across every kind."""

    current = await factories.account(context, "Current")
    savings = await factories.account(context, "Savings", AccountType.SAVINGS)
    broker = await factories.account(context, "Broker", AccountType.BROKERAGE)
    food = await factories.category(context, "Restaurants")
    groceries = await factories.category(context, "Groceries", icon="shopping-cart")
    salary = await factories.category(
        context, "Salary", CategoryKind.INCOME, "briefcase"
    )
    sp500 = await factories.asset(context)

    income = await factories.transaction(
        context,
        kind="INCOME",
        amount_minor=300_000,
        occurred_on=date(2026, 9, 1),
        to_account_id=current.id,
        category_id=salary.id,
    )
    dinner = await factories.expense(
        context,
        from_account_id=current.id,
        category_id=food.id,
        amount_minor=10_000,
        occurred_on=date(2026, 9, 5),
    )
    shopping = await factories.expense(
        context,
        from_account_id=current.id,
        category_id=groceries.id,
        amount_minor=6_342,
        occurred_on=date(2026, 9, 5),
    )
    transfer = await factories.transaction(
        context,
        kind="TRANSFER",
        amount_minor=50_000,
        occurred_on=date(2026, 9, 10),
        from_account_id=current.id,
        to_account_id=savings.id,
    )
    investment = await factories.transaction(
        context,
        kind="INVESTMENT",
        amount_minor=30_000,
        occurred_on=date(2026, 9, 20),
        from_account_id=broker.id,
        investment_asset_id=sp500.id,
    )
    payback = await factories.reimbursement(
        context,
        to_account_id=savings.id,
        expense_id=dinner.id,
        amount_minor=5_000,
        occurred_on=date(2026, 10, 2),
    )

    return SimpleNamespace(
        income=income,
        dinner=dinner,
        shopping=shopping,
        transfer=transfer,
        investment=investment,
        payback=payback,
        current=current,
        savings=savings,
        food=food,
        sp500=sp500,
    )


async def test_history_is_newest_first(user: AppContext) -> None:
    s = await _scenario(user)

    ids = await _ids(user)

    # Same-day rows keep creation order (newest first).
    assert ids == [
        s.payback.id,
        s.investment.id,
        s.transfer.id,
        s.shopping.id,
        s.dinner.id,
        s.income.id,
    ]


async def test_history_can_be_filtered(user: AppContext) -> None:
    s = await _scenario(user)

    assert await _ids(user, kind=TransactionKind.EXPENSE) == [
        s.shopping.id,
        s.dinner.id,
    ]
    assert await _ids(user, date_from=date(2026, 9, 5), date_to=date(2026, 9, 10)) == [
        s.transfer.id,
        s.shopping.id,
        s.dinner.id,
    ]
    # An account matches either side of a movement.
    assert set(await _ids(user, account_id=s.savings.id)) == {
        s.transfer.id,
        s.payback.id,
    }
    assert await _ids(user, investment_asset_id=s.sp500.id) == [s.investment.id]


async def test_category_filter_includes_reimbursements_of_that_category(
    user: AppContext,
) -> None:
    s = await _scenario(user)

    assert await _ids(user, category_id=s.food.id) == [
        s.payback.id,
        s.dinner.id,
    ]


async def test_reversed_period_is_rejected() -> None:
    with pytest.raises(ValueError, match="'from' must not be after 'to'"):
        TransactionFilters(date_from=date(2026, 9, 30), date_to=date(2026, 9, 1))


async def test_pagination_walks_every_row_exactly_once(user: AppContext) -> None:
    s = await _scenario(user)
    expected = await _ids(user)

    seen: list[UUID] = []
    cursor: str | None = None

    while True:
        page = await transactions_service.list_transactions(
            user, TransactionFilters(), limit=4, cursor=cursor
        )
        seen.extend(item.id for item in page.items)

        if page.next_cursor is None:
            break

        cursor = page.next_cursor

    assert seen == expected
    assert len(seen) == 6
    assert s.dinner.id in seen


async def test_invalid_page_parameters_are_rejected(user: AppContext) -> None:
    with pytest.raises(ValueError, match="limit"):
        await transactions_service.list_transactions(
            user, TransactionFilters(), limit=0
        )

    with pytest.raises(ValueError, match="Invalid cursor"):
        await transactions_service.list_transactions(
            user, TransactionFilters(), cursor="not-a-cursor"
        )


async def test_history_is_isolated_between_users(
    user: AppContext, other_user: AppContext
) -> None:
    await _scenario(user)

    assert await _ids(other_user) == []

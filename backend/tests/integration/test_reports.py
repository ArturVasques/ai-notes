"""
Integration tests for the financial reports and account balances.

They reproduce the worked example of docs/DOMAIN_MODEL.md (section 3) to
the cent, including the late-reimbursement case that separates effective
spending (attributed to the expense's month) from cash flow (real dates).
"""

from datetime import date
from types import SimpleNamespace

import pytest

from app.auth.context import AppContext
from app.schemas.account import AccountCreate, AccountType
from app.schemas.category import CategoryKind
from app.schemas.report import Period
from app.services.finance import accounts_service, reports_service
from tests.integration import factories

SEPTEMBER = Period(date_from=date(2026, 9, 1), date_to=date(2026, 9, 30))
OCTOBER = Period(date_from=date(2026, 10, 1), date_to=date(2026, 10, 31))


async def _worked_example(
    context: AppContext, *, reimbursed_on: date = date(2026, 9, 12)
) -> SimpleNamespace:
    """
    Salary 3000 → Current; 2100 of expenses (2000 groceries + 100
    restaurant); 100 reimbursed (50 + 50); 500 to Savings; 300 to Broker;
    Broker invests 300 in the S&P 500.
    """

    current = await accounts_service.create_account(
        context,
        AccountCreate(
            name="Current", type=AccountType.CHECKING, opening_balance_minor=100_000
        ),
    )
    savings = await factories.account(context, "Savings", AccountType.SAVINGS)
    broker = await factories.account(context, "Broker", AccountType.BROKERAGE)
    groceries = await factories.category(context, "Groceries", icon="shopping-cart")
    restaurants = await factories.category(context, "Restaurants")
    salary = await factories.category(
        context, "Salary", CategoryKind.INCOME, "briefcase"
    )
    sp500 = await factories.asset(context)

    await factories.transaction(
        context,
        kind="INCOME",
        amount_minor=300_000,
        occurred_on=date(2026, 9, 1),
        to_account_id=current.id,
        category_id=salary.id,
    )
    big = await factories.expense(
        context,
        from_account_id=current.id,
        category_id=groceries.id,
        amount_minor=200_000,
        occurred_on=date(2026, 9, 5),
    )
    dinner = await factories.expense(
        context,
        from_account_id=current.id,
        category_id=restaurants.id,
        amount_minor=10_000,
        occurred_on=date(2026, 9, 10),
    )
    await factories.reimbursement(
        context,
        to_account_id=current.id,
        expense_id=dinner.id,
        amount_minor=5_000,
        occurred_on=reimbursed_on,
    )
    await factories.reimbursement(
        context,
        to_account_id=current.id,
        expense_id=big.id,
        amount_minor=5_000,
        occurred_on=reimbursed_on,
    )
    await factories.transaction(
        context,
        kind="TRANSFER",
        amount_minor=50_000,
        occurred_on=date(2026, 9, 20),
        from_account_id=current.id,
        to_account_id=savings.id,
    )
    await factories.transaction(
        context,
        kind="TRANSFER",
        amount_minor=30_000,
        occurred_on=date(2026, 9, 21),
        from_account_id=current.id,
        to_account_id=broker.id,
    )
    await factories.transaction(
        context,
        kind="INVESTMENT",
        amount_minor=30_000,
        occurred_on=date(2026, 9, 22),
        from_account_id=broker.id,
        investment_asset_id=sp500.id,
    )

    return SimpleNamespace(
        current=current,
        savings=savings,
        broker=broker,
        groceries=groceries,
        restaurants=restaurants,
        salary=salary,
        sp500=sp500,
    )


async def test_overview_matches_the_worked_example(user: AppContext) -> None:
    await _worked_example(user)

    overview = await reports_service.get_financial_overview(user, SEPTEMBER)

    assert overview.income_minor == 300_000
    assert overview.gross_expenses_minor == 210_000
    assert overview.reimbursements_attributed_minor == 10_000
    assert overview.effective_expenses_minor == 200_000
    assert overview.net_savings_minor == 100_000
    assert overview.savings_rate == pytest.approx(0.3333, abs=0.0001)
    assert overview.allocation.savings_accounts_minor == 50_000
    assert overview.allocation.investments_minor == 30_000
    assert overview.allocation.retained_cash_minor == 20_000
    assert overview.reimbursements_received_minor == 10_000
    assert overview.net_cash_flow_minor == 100_000
    assert overview.transfers_minor == 80_000


async def test_late_reimbursement_changes_cash_flow_but_not_effective_spending(
    user: AppContext,
) -> None:
    await _worked_example(user, reimbursed_on=date(2026, 10, 2))

    september = await reports_service.get_financial_overview(user, SEPTEMBER)
    october = await reports_service.get_financial_overview(user, OCTOBER)

    # September still owns the effective spending and the net savings...
    assert september.effective_expenses_minor == 200_000
    assert september.net_savings_minor == 100_000
    assert september.allocation.retained_cash_minor == 20_000
    # ...but the cash only arrives in October.
    assert september.reimbursements_received_minor == 0
    assert september.net_cash_flow_minor == 90_000
    assert october.income_minor == 0
    assert october.effective_expenses_minor == 0
    assert october.net_savings_minor == 0
    assert october.savings_rate is None
    assert october.reimbursements_received_minor == 10_000
    assert october.net_cash_flow_minor == 10_000


async def test_empty_period_is_all_zero(user: AppContext) -> None:
    overview = await reports_service.get_financial_overview(user, OCTOBER)

    assert overview.income_minor == 0
    assert overview.effective_expenses_minor == 0
    assert overview.net_savings_minor == 0
    assert overview.savings_rate is None
    assert overview.allocation.retained_cash_minor == 0


async def test_spending_by_category_uses_effective_amounts(user: AppContext) -> None:
    s = await _worked_example(user, reimbursed_on=date(2026, 10, 2))

    spending = await reports_service.get_spending_by_category(user, SEPTEMBER)
    income = await reports_service.get_income_summary(user, SEPTEMBER)

    assert [
        (i.category_id, i.gross_minor, i.reimbursed_minor, i.effective_minor)
        for i in spending.items
    ] == [
        (s.groceries.id, 200_000, 5_000, 195_000),
        (s.restaurants.id, 10_000, 5_000, 5_000),
    ]
    assert spending.total_minor == 200_000
    assert spending.items[0].icon == "shopping-cart"
    assert [(i.category_id, i.effective_minor) for i in income.items] == [
        (s.salary.id, 300_000)
    ]


async def test_savings_summary_details_the_savings_accounts(user: AppContext) -> None:
    s = await _worked_example(user)

    summary = await reports_service.get_savings_summary(user, SEPTEMBER)

    assert summary.net_savings_minor == 100_000
    assert summary.allocation.savings_accounts_minor == 50_000
    assert [
        (m.account_id, m.inflows_minor, m.outflows_minor, m.net_minor)
        for m in summary.savings_accounts
    ] == [(s.savings.id, 50_000, 0, 50_000)]


async def test_transfer_between_savings_accounts_is_not_new_saving(
    user: AppContext,
) -> None:
    first = await factories.account(user, "Savings A", AccountType.SAVINGS)
    second = await factories.account(user, "Savings B", AccountType.SAVINGS)
    await factories.transaction(
        user,
        kind="TRANSFER",
        amount_minor=40_000,
        occurred_on=date(2026, 9, 3),
        from_account_id=first.id,
        to_account_id=second.id,
    )

    summary = await reports_service.get_savings_summary(user, SEPTEMBER)

    assert summary.allocation.savings_accounts_minor == 0
    assert {m.account_id: m.net_minor for m in summary.savings_accounts} == {
        first.id: -40_000,
        second.id: 40_000,
    }


async def test_investment_summary_by_asset_and_source(user: AppContext) -> None:
    s = await _worked_example(user)

    all_time = await reports_service.get_investment_summary(user)
    october = await reports_service.get_investment_summary(user, OCTOBER)

    assert all_time.total_invested_minor == 30_000
    assert [
        (i.investment_asset_id, i.invested_minor, i.transaction_count)
        for i in all_time.by_asset
    ] == [(s.sp500.id, 30_000, 1)]
    assert [(i.account_id, i.invested_minor) for i in all_time.by_source_account] == [
        (s.broker.id, 30_000)
    ]
    assert october.total_invested_minor == 0
    assert october.by_asset == []


async def test_monthly_trend_covers_every_month_with_zeros(user: AppContext) -> None:
    await _worked_example(user, reimbursed_on=date(2026, 10, 2))

    trend = await reports_service.get_monthly_trend(
        user, months=3, until=date(2026, 10, 15)
    )

    assert [p.month for p in trend.months] == ["2026-08", "2026-09", "2026-10"]
    august, september, october = trend.months
    assert august.income_minor == 0 and august.savings_rate is None
    assert september.effective_expenses_minor == 200_000
    assert september.net_savings_minor == 100_000
    assert september.savings_accounts_minor == 50_000
    assert september.invested_minor == 30_000
    assert september.retained_cash_minor == 20_000
    assert september.net_cash_flow_minor == 90_000
    assert october.net_cash_flow_minor == 10_000
    assert october.effective_expenses_minor == 0


async def test_trend_length_is_bounded(user: AppContext) -> None:
    with pytest.raises(ValueError, match="months"):
        await reports_service.get_monthly_trend(user, months=0, until=date(2026, 9, 1))


async def test_account_balances_add_opening_balance_and_movements(
    user: AppContext,
) -> None:
    s = await _worked_example(user)

    now = await accounts_service.get_account_balances(user)
    early = await accounts_service.get_account_balances(user, as_of=date(2026, 9, 5))

    assert {b.account.id: b.balance_minor for b in now.items} == {
        s.current.id: 100_000 + 300_000 - 210_000 + 10_000 - 50_000 - 30_000,
        s.savings.id: 50_000,
        s.broker.id: 0,
    }
    assert now.total_minor == 120_000 + 50_000
    assert {b.account.id: b.balance_minor for b in early.items} == {
        s.current.id: 100_000 + 300_000 - 200_000,
        s.savings.id: 0,
        s.broker.id: 0,
    }


async def test_reports_are_isolated_between_users(
    user: AppContext, other_user: AppContext
) -> None:
    await _worked_example(user)

    overview = await reports_service.get_financial_overview(other_user, SEPTEMBER)
    balances = await accounts_service.get_account_balances(other_user)
    spending = await reports_service.get_spending_by_category(other_user, SEPTEMBER)

    assert overview.income_minor == 0
    assert balances.items == []
    assert spending.items == []


def test_reversed_period_is_rejected() -> None:
    with pytest.raises(ValueError, match="'from' must not be after 'to'"):
        Period(date_from=date(2026, 9, 30), date_to=date(2026, 9, 1))

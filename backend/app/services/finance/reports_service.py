"""
Application service for the deterministic financial reports.

All metrics are defined in docs/DOMAIN_MODEL.md, section 3, and computed
here from database aggregates. Nothing else in the system (frontend, future
AI tools) computes financial figures.

Flow metrics of a period [date_from, date_to]:

    effective_expenses = gross_expenses − reimbursements attributed
                         (linked to expenses of the period, any date)
    net_savings        = income − effective_expenses
    savings_rate       = net_savings / income          (None when income = 0)
    allocation:
        savings_accounts = net movement of SAVINGS accounts in the period
        investments      = INVESTMENT transactions in the period
        retained_cash    = net_savings − savings_accounts − investments
    net_cash_flow      = income + reimbursements received − gross_expenses
                         (everything by real transaction date)

Used by:
- api/reports.py
- future AI agent tools and MCP, through the same functions.
"""

from calendar import monthrange
from datetime import date

from psycopg import AsyncConnection

from app.auth.context import AppContext
from app.auth.permissions import FINANCE_READ
from app.database.connection import pool
from app.repositories import reports_repository
from app.schemas.category import CategoryKind
from app.schemas.report import (
    CategoryBreakdown,
    CategoryBreakdownItem,
    FinancialOverview,
    InvestmentByAsset,
    InvestmentBySource,
    InvestmentSummary,
    MonthlyPoint,
    MonthlyTrend,
    Period,
    SavingsAccountMovement,
    SavingsAllocation,
    SavingsSummary,
)

MAX_TREND_MONTHS = 36


def savings_rate(net_savings_minor: int, income_minor: int) -> float | None:
    """Share of income kept, as a ratio. Undefined without income."""

    if income_minor <= 0:
        return None

    return round(net_savings_minor / income_minor, 4)


def month_bounds(year: int, month: int) -> Period:
    """First and last day of a calendar month."""

    return Period(
        date_from=date(year, month, 1),
        date_to=date(year, month, monthrange(year, month)[1]),
    )


async def get_financial_overview(
    context: AppContext, period: Period
) -> FinancialOverview:
    """Headline metrics of the period."""

    context.require_permission(FINANCE_READ)

    async with pool.connection() as connection:
        return await _overview(connection, context, period)


async def _overview(
    connection: AsyncConnection, context: AppContext, period: Period
) -> FinancialOverview:
    totals = await reports_repository.get_flow_totals(
        connection,
        user_id=context.user_id,
        date_from=period.date_from,
        date_to=period.date_to,
    )
    attributed = await reports_repository.get_reimbursements_attributed(
        connection,
        user_id=context.user_id,
        date_from=period.date_from,
        date_to=period.date_to,
    )
    savings_accounts = await reports_repository.get_savings_account_movements(
        connection,
        user_id=context.user_id,
        date_from=period.date_from,
        date_to=period.date_to,
    )

    effective = totals["gross_expenses"] - attributed
    net_savings = totals["income"] - effective
    to_savings = sum(
        row["inflows_minor"] - row["outflows_minor"] for row in savings_accounts
    )

    return FinancialOverview(
        date_from=period.date_from,
        date_to=period.date_to,
        income_minor=totals["income"],
        gross_expenses_minor=totals["gross_expenses"],
        reimbursements_attributed_minor=attributed,
        effective_expenses_minor=effective,
        net_savings_minor=net_savings,
        savings_rate=savings_rate(net_savings, totals["income"]),
        allocation=SavingsAllocation(
            savings_accounts_minor=to_savings,
            investments_minor=totals["invested"],
            retained_cash_minor=net_savings - to_savings - totals["invested"],
        ),
        reimbursements_received_minor=totals["reimbursements_received"],
        net_cash_flow_minor=(
            totals["income"]
            + totals["reimbursements_received"]
            - totals["gross_expenses"]
        ),
        transfers_minor=totals["transfers"],
    )


async def get_category_breakdown(
    context: AppContext, period: Period, kind: CategoryKind
) -> CategoryBreakdown:
    """Effective amount per category of one kind, largest first."""

    context.require_permission(FINANCE_READ)

    async with pool.connection() as connection:
        rows = await reports_repository.get_category_breakdown(
            connection,
            user_id=context.user_id,
            kind=kind,
            date_from=period.date_from,
            date_to=period.date_to,
        )

    items = [
        CategoryBreakdownItem(
            **row, effective_minor=row["gross_minor"] - row["reimbursed_minor"]
        )
        for row in rows
    ]

    return CategoryBreakdown(
        date_from=period.date_from,
        date_to=period.date_to,
        kind=kind,
        total_minor=sum(item.effective_minor for item in items),
        items=items,
    )


async def get_spending_by_category(
    context: AppContext, period: Period
) -> CategoryBreakdown:
    """Effective expenses per category."""

    return await get_category_breakdown(context, period, CategoryKind.EXPENSE)


async def get_income_summary(context: AppContext, period: Period) -> CategoryBreakdown:
    """Income per category."""

    return await get_category_breakdown(context, period, CategoryKind.INCOME)


async def get_savings_summary(context: AppContext, period: Period) -> SavingsSummary:
    """Net savings, rate, allocation and the savings accounts detail."""

    context.require_permission(FINANCE_READ)

    async with pool.connection() as connection:
        overview = await _overview(connection, context, period)
        rows = await reports_repository.get_savings_account_movements(
            connection,
            user_id=context.user_id,
            date_from=period.date_from,
            date_to=period.date_to,
        )

    return SavingsSummary(
        date_from=period.date_from,
        date_to=period.date_to,
        income_minor=overview.income_minor,
        effective_expenses_minor=overview.effective_expenses_minor,
        net_savings_minor=overview.net_savings_minor,
        savings_rate=overview.savings_rate,
        allocation=overview.allocation,
        savings_accounts=[
            SavingsAccountMovement(
                **row, net_minor=row["inflows_minor"] - row["outflows_minor"]
            )
            for row in rows
        ],
    )


async def get_investment_summary(
    context: AppContext, period: Period | None = None
) -> InvestmentSummary:
    """Money invested by asset and by source account (all time by default)."""

    context.require_permission(FINANCE_READ)

    date_from = period.date_from if period else None
    date_to = period.date_to if period else None

    async with pool.connection() as connection:
        by_asset = await reports_repository.get_investments_by_asset(
            connection, user_id=context.user_id, date_from=date_from, date_to=date_to
        )
        by_source = await reports_repository.get_investments_by_source_account(
            connection, user_id=context.user_id, date_from=date_from, date_to=date_to
        )

    assets = [InvestmentByAsset(**row) for row in by_asset]

    return InvestmentSummary(
        date_from=date_from,
        date_to=date_to,
        total_invested_minor=sum(item.invested_minor for item in assets),
        by_asset=assets,
        by_source_account=[InvestmentBySource(**row) for row in by_source],
    )


async def get_monthly_trend(
    context: AppContext, *, months: int, until: date
) -> MonthlyTrend:
    """The last `months` calendar months ending with the month of `until`."""

    context.require_permission(FINANCE_READ)

    if not 1 <= months <= MAX_TREND_MONTHS:
        raise ValueError(f"months must be between 1 and {MAX_TREND_MONTHS}")

    keys = _month_keys(until, months)
    first_year, first_month = (int(part) for part in keys[0].split("-"))
    period = Period(
        date_from=date(first_year, first_month, 1),
        date_to=month_bounds(until.year, until.month).date_to,
    )

    async with pool.connection() as connection:
        flows = await reports_repository.get_monthly_flows(
            connection,
            user_id=context.user_id,
            date_from=period.date_from,
            date_to=period.date_to,
        )
        attributed = await reports_repository.get_monthly_reimbursements_attributed(
            connection,
            user_id=context.user_id,
            date_from=period.date_from,
            date_to=period.date_to,
        )

    points = []

    for key in keys:
        month = flows.get(key, {})
        income = month.get("income", 0)
        gross = month.get("gross_expenses", 0)
        effective = gross - attributed.get(key, 0)
        net_savings = income - effective
        to_savings = month.get("savings_accounts", 0)
        invested = month.get("invested", 0)

        points.append(
            MonthlyPoint(
                month=key,
                income_minor=income,
                gross_expenses_minor=gross,
                effective_expenses_minor=effective,
                net_savings_minor=net_savings,
                savings_rate=savings_rate(net_savings, income),
                savings_accounts_minor=to_savings,
                invested_minor=invested,
                retained_cash_minor=net_savings - to_savings - invested,
                net_cash_flow_minor=(
                    income + month.get("reimbursements_received", 0) - gross
                ),
            )
        )

    return MonthlyTrend(months=points)


def _month_keys(until: date, months: int) -> list[str]:
    """`YYYY-MM` keys of the `months` months ending with `until`'s month."""

    year, month = until.year, until.month
    keys: list[str] = []

    for _ in range(months):
        keys.append(f"{year:04d}-{month:02d}")
        month -= 1

        if month == 0:
            month = 12
            year -= 1

    return list(reversed(keys))

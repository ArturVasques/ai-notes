"""
HTTP API for the financial reports.

Every report is scoped to the caller through AppContext. Periods are
inclusive; when omitted they default to the current calendar month.
"""

from datetime import date

from fastapi import APIRouter, Depends, Query

from app.auth.context import AppContext
from app.auth.dependencies import get_app_context
from app.schemas.category import CategoryKind
from app.schemas.report import (
    CategoryBreakdown,
    FinancialOverview,
    InvestmentSummary,
    MonthlyTrend,
    Period,
    SavingsSummary,
)
from app.services.finance import reports_service
from app.services.finance.reports_service import MAX_TREND_MONTHS

router = APIRouter(
    prefix="/reports",
    tags=["Reports"],
)


def _period(date_from: date | None, date_to: date | None) -> Period:
    if date_from is None and date_to is None:
        today = date.today()
        return reports_service.month_bounds(today.year, today.month)

    if date_from is None or date_to is None:
        raise ValueError("'from' and 'to' must be provided together")

    return Period(date_from=date_from, date_to=date_to)


@router.get("/overview", response_model=FinancialOverview)
async def overview(
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    context: AppContext = Depends(get_app_context),
) -> FinancialOverview:
    """Income, expenses, net savings, allocation and cash flow of a period."""

    return await reports_service.get_financial_overview(
        context, _period(date_from, date_to)
    )


@router.get("/categories", response_model=CategoryBreakdown)
async def categories(
    kind: CategoryKind = CategoryKind.EXPENSE,
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    context: AppContext = Depends(get_app_context),
) -> CategoryBreakdown:
    """Effective amount per category of one kind."""

    return await reports_service.get_category_breakdown(
        context, _period(date_from, date_to), kind
    )


@router.get("/savings", response_model=SavingsSummary)
async def savings(
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    context: AppContext = Depends(get_app_context),
) -> SavingsSummary:
    """Net savings, savings rate and allocation with savings accounts."""

    return await reports_service.get_savings_summary(
        context, _period(date_from, date_to)
    )


@router.get("/investments", response_model=InvestmentSummary)
async def investments(
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    context: AppContext = Depends(get_app_context),
) -> InvestmentSummary:
    """Invested by asset and by source account (all time when no period)."""

    period = (
        None if date_from is None and date_to is None else _period(date_from, date_to)
    )

    return await reports_service.get_investment_summary(context, period)


@router.get("/monthly-trend", response_model=MonthlyTrend)
async def monthly_trend(
    months: int = Query(default=6, ge=1, le=MAX_TREND_MONTHS),
    until: date | None = None,
    context: AppContext = Depends(get_app_context),
) -> MonthlyTrend:
    """Month-by-month flow metrics ending with the month of `until`."""

    return await reports_service.get_monthly_trend(
        context, months=months, until=until or date.today()
    )

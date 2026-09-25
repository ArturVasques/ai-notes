"""
HTTP API for transactions.

Identity always comes from AppContext, never from the request body: every
create/update model forbids unknown fields, so a body carrying `user_id` is
rejected. Financial rules live in services/finance/transactions_service.py.
"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query, Response, status

from app.auth.context import AppContext
from app.auth.dependencies import get_app_context
from app.schemas.transaction import (
    Transaction,
    TransactionCreate,
    TransactionFilters,
    TransactionKind,
    TransactionPage,
    TransactionUpdate,
)
from app.services.finance import transactions_service
from app.services.finance.transactions_service import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
)

router = APIRouter(
    prefix="/transactions",
    tags=["Transactions"],
)


@router.get("", response_model=TransactionPage)
async def list_transactions(
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    kind: TransactionKind | None = None,
    category_id: UUID | None = None,
    account_id: UUID | None = None,
    investment_asset_id: UUID | None = None,
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    cursor: str | None = None,
    context: AppContext = Depends(get_app_context),
) -> TransactionPage:
    """List the caller's transactions, newest first, with optional filters."""

    filters = TransactionFilters(
        date_from=date_from,
        date_to=date_to,
        kind=kind,
        category_id=category_id,
        account_id=account_id,
        investment_asset_id=investment_asset_id,
    )

    return await transactions_service.list_transactions(
        context, filters, limit=limit, cursor=cursor
    )


@router.post("", response_model=Transaction, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    request: TransactionCreate = Body(),
    context: AppContext = Depends(get_app_context),
) -> Transaction:
    """Record an income, expense, transfer, investment or reimbursement."""

    return await transactions_service.create_transaction(context, request)


@router.get("/{transaction_id}", response_model=Transaction)
async def get_transaction(
    transaction_id: UUID,
    context: AppContext = Depends(get_app_context),
) -> Transaction:
    """Return one of the caller's transactions."""

    return await transactions_service.get_transaction(context, transaction_id)


@router.patch("/{transaction_id}", response_model=Transaction)
async def update_transaction(
    transaction_id: UUID,
    request: TransactionUpdate,
    context: AppContext = Depends(get_app_context),
) -> Transaction:
    """Edit a transaction. Its kind cannot change."""

    return await transactions_service.update_transaction(
        context, transaction_id, request
    )


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    transaction_id: UUID,
    context: AppContext = Depends(get_app_context),
) -> Response:
    """Delete a transaction. An expense with reimbursements cannot be deleted."""

    await transactions_service.delete_transaction(context, transaction_id)

    return Response(status_code=status.HTTP_204_NO_CONTENT)

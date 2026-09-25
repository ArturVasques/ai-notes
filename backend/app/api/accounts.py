"""
HTTP API for accounts.

Identity always comes from AppContext, never from the request: an account
belongs to the authenticated user who creates it. Business rules live in
services/finance/accounts_service.py.
"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.auth.context import AppContext
from app.auth.dependencies import get_app_context
from app.schemas.account import Account, AccountCreate, AccountUpdate
from app.schemas.report import AccountBalances
from app.services.finance import accounts_service

router = APIRouter(
    prefix="/accounts",
    tags=["Accounts"],
)


@router.get("", response_model=list[Account])
async def list_accounts(
    include_archived: bool = False,
    context: AppContext = Depends(get_app_context),
) -> list[Account]:
    """List the caller's accounts (active only unless include_archived)."""

    return await accounts_service.list_accounts(
        context, include_archived=include_archived
    )


@router.post("", response_model=Account, status_code=status.HTTP_201_CREATED)
async def create_account(
    request: AccountCreate,
    context: AppContext = Depends(get_app_context),
) -> Account:
    """Create an account owned by the caller."""

    return await accounts_service.create_account(context, request)


# Declared before "/{account_id}" so the literal path wins.
@router.get("/balances", response_model=AccountBalances)
async def get_account_balances(
    as_of: date | None = None,
    include_archived: bool = False,
    context: AppContext = Depends(get_app_context),
) -> AccountBalances:
    """Current balance of every account (opening balance + movements)."""

    return await accounts_service.get_account_balances(
        context, as_of=as_of, include_archived=include_archived
    )


@router.get("/{account_id}", response_model=Account)
async def get_account(
    account_id: UUID,
    context: AppContext = Depends(get_app_context),
) -> Account:
    """Return one of the caller's accounts."""

    return await accounts_service.get_account(context, account_id)


@router.patch("/{account_id}", response_model=Account)
async def update_account(
    account_id: UUID,
    request: AccountUpdate,
    context: AppContext = Depends(get_app_context),
) -> Account:
    """Edit, archive (`archived: true`) or restore an account."""

    return await accounts_service.update_account(context, account_id, request)

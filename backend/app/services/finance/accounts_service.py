"""
Application service for accounts.

Accounts are never deleted: they are archived so historical transactions
keep pointing at them. Identity always comes from the trusted AppContext.

Used by:
- api/accounts.py
- future AI agent tools and MCP, through the same functions.
"""

from uuid import UUID, uuid4

from psycopg import errors

from app.auth.context import AppContext
from app.auth.permissions import FINANCE_READ, FINANCE_WRITE
from app.core.errors import ConflictError, NotFoundError
from app.database.connection import pool
from app.repositories import account_repository
from app.schemas.account import Account, AccountCreate, AccountUpdate
from app.services.finance.updates import apply_archive_flag, reject_nulls

_DUPLICATE_NAME = "An active account with this name already exists"


async def create_account(context: AppContext, request: AccountCreate) -> Account:
    """Create an account owned by the authenticated user."""

    context.require_permission(FINANCE_WRITE)

    try:
        async with pool.connection() as connection, connection.transaction():
            return await account_repository.insert_account(
                connection,
                user_id=context.user_id,
                account_id=uuid4(),
                name=request.name,
                account_type=request.type,
                description=request.description,
                currency=request.currency,
                opening_balance_minor=request.opening_balance_minor,
            )
    except errors.UniqueViolation as exc:
        raise ConflictError(_DUPLICATE_NAME) from exc


async def list_accounts(
    context: AppContext, *, include_archived: bool = False
) -> list[Account]:
    """List the authenticated user's accounts."""

    context.require_permission(FINANCE_READ)

    async with pool.connection() as connection:
        return await account_repository.list_accounts(
            connection, user_id=context.user_id, include_archived=include_archived
        )


async def get_account(context: AppContext, account_id: UUID) -> Account:
    """Return one of the authenticated user's accounts."""

    context.require_permission(FINANCE_READ)

    async with pool.connection() as connection:
        account = await account_repository.get_account(
            connection, user_id=context.user_id, account_id=account_id
        )

    if account is None:
        raise NotFoundError("Account not found")

    return account


async def update_account(
    context: AppContext, account_id: UUID, request: AccountUpdate
) -> Account:
    """Edit, archive or restore one of the authenticated user's accounts."""

    context.require_permission(FINANCE_WRITE)

    changes = request.model_dump(exclude_unset=True)
    reject_nulls(changes, ("name", "type", "opening_balance_minor", "archived"))

    try:
        async with pool.connection() as connection, connection.transaction():
            current = await account_repository.get_account(
                connection,
                user_id=context.user_id,
                account_id=account_id,
                for_update=True,
            )

            if current is None:
                raise NotFoundError("Account not found")

            apply_archive_flag(changes, current.archived_at)

            if not changes:
                return current

            updated = await account_repository.update_account(
                connection,
                user_id=context.user_id,
                account_id=account_id,
                changes=changes,
            )
    except errors.UniqueViolation as exc:
        raise ConflictError(_DUPLICATE_NAME) from exc

    assert updated is not None
    return updated

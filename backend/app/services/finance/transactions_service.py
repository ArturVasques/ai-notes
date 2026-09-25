"""
Application service for transactions: the financial rules of the domain.

Every write runs in one database transaction that validates references,
locks what must not change concurrently and then writes, so a movement is
either fully valid and stored or not stored at all.

Rules (see docs/DOMAIN_MODEL.md, section 2):
- referenced accounts, categories, assets and expenses must belong to the
  caller; another user's id is reported like a missing one.
- a category's kind must match the transaction kind.
- archived accounts, categories and assets cannot be used in new
  references, but an existing reference to them may stay.
- a transfer needs two different accounts with the same currency.
- a reimbursement repays an EXPENSE, uses the expense's currency, is not
  dated before it, and all reimbursements of an expense never exceed it.
  The expense row is locked, so concurrent reimbursements are serialized.
- an expense cannot shrink below, or move after, its reimbursements, and
  cannot be deleted while it has any.
- the kind never changes after creation.

Used by:
- api/transactions.py
- future AI agent tools and MCP, through the same functions.
"""

import base64
import binascii
import json
from datetime import date, datetime
from uuid import UUID, uuid4

from psycopg import AsyncConnection
from pydantic import ValidationError

from app.auth.context import AppContext
from app.auth.permissions import FINANCE_READ, FINANCE_WRITE
from app.core.errors import ConflictError, NotFoundError
from app.database.connection import pool
from app.repositories import (
    account_repository,
    category_repository,
    investment_asset_repository,
    transaction_repository,
)
from app.schemas.account import Account
from app.schemas.category import CategoryKind
from app.schemas.transaction import (
    KIND_REFERENCE_FIELDS,
    ExpenseCreate,
    ReimbursementCreate,
    Transaction,
    TransactionCreate,
    TransactionFilters,
    TransactionKind,
    TransactionPage,
    TransactionUpdate,
    TransferCreate,
    transaction_create_adapter,
)

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


async def create_transaction(
    context: AppContext, request: TransactionCreate
) -> Transaction:
    """Record a financial movement for the authenticated user."""

    context.require_permission(FINANCE_WRITE)

    transaction_id = uuid4()

    async with pool.connection() as connection, connection.transaction():
        await _validate(connection, context.user_id, request, previous=None)

        await transaction_repository.insert_transaction(
            connection,
            user_id=context.user_id,
            transaction_id=transaction_id,
            kind=request.kind,
            values=request.model_dump(exclude={"kind"}),
        )

        created = await transaction_repository.get_transaction(
            connection, user_id=context.user_id, transaction_id=transaction_id
        )

    assert created is not None
    return created


async def get_transaction(context: AppContext, transaction_id: UUID) -> Transaction:
    """Return one of the authenticated user's transactions."""

    context.require_permission(FINANCE_READ)

    async with pool.connection() as connection:
        transaction = await transaction_repository.get_transaction(
            connection, user_id=context.user_id, transaction_id=transaction_id
        )

    if transaction is None:
        raise NotFoundError("Transaction not found")

    return transaction


async def update_transaction(
    context: AppContext, transaction_id: UUID, request: TransactionUpdate
) -> Transaction:
    """
    Edit one of the authenticated user's transactions.

    The changes are merged into the stored transaction and the result is
    validated exactly like a new transaction of the same kind.
    """

    context.require_permission(FINANCE_WRITE)

    changes = request.model_dump(exclude_unset=True)

    async with pool.connection() as connection, connection.transaction():
        current = await _lock_and_get(connection, context.user_id, transaction_id)

        fields = (
            "amount_minor",
            "occurred_on",
            "description",
            *KIND_REFERENCE_FIELDS[current.kind],
        )
        merged = {field: getattr(current, field) for field in fields}
        merged.update(changes)
        merged["kind"] = current.kind

        try:
            candidate = transaction_create_adapter.validate_python(merged)
        except ValidationError as exc:
            raise ValueError(_describe_validation_error(exc)) from exc

        await _validate(connection, context.user_id, candidate, previous=current)

        await transaction_repository.update_transaction(
            connection,
            user_id=context.user_id,
            transaction_id=transaction_id,
            values=candidate.model_dump(exclude={"kind"}),
        )

        updated = await transaction_repository.get_transaction(
            connection, user_id=context.user_id, transaction_id=transaction_id
        )

    assert updated is not None
    return updated


async def delete_transaction(context: AppContext, transaction_id: UUID) -> None:
    """Delete one of the authenticated user's transactions."""

    context.require_permission(FINANCE_WRITE)

    async with pool.connection() as connection, connection.transaction():
        current = await _lock_and_get(connection, context.user_id, transaction_id)

        if current.reimbursed_amount_minor > 0:
            raise ConflictError(
                "This expense has reimbursements; delete them before the expense"
            )

        await transaction_repository.delete_transaction(
            connection, user_id=context.user_id, transaction_id=transaction_id
        )


async def list_transactions(
    context: AppContext,
    filters: TransactionFilters,
    *,
    limit: int = DEFAULT_PAGE_SIZE,
    cursor: str | None = None,
) -> TransactionPage:
    """
    Return the authenticated user's transactions, newest first.

    Pass the returned `next_cursor` to get the following page.
    """

    context.require_permission(FINANCE_READ)

    if not 1 <= limit <= MAX_PAGE_SIZE:
        raise ValueError(f"limit must be between 1 and {MAX_PAGE_SIZE}")

    after = decode_cursor(cursor) if cursor else None

    async with pool.connection() as connection:
        rows = await transaction_repository.list_transactions(
            connection,
            user_id=context.user_id,
            filters=filters,
            limit=limit + 1,
            after=after,
        )

    has_more = len(rows) > limit
    items = rows[:limit]

    return TransactionPage(
        items=items,
        next_cursor=encode_cursor(items[-1]) if has_more else None,
    )


def encode_cursor(transaction: Transaction) -> str:
    """Opaque keyset cursor pointing after the given transaction."""

    payload = json.dumps(
        [
            transaction.occurred_on.isoformat(),
            transaction.created_at.isoformat(),
            str(transaction.id),
        ]
    )

    return base64.urlsafe_b64encode(payload.encode()).decode()


def decode_cursor(cursor: str) -> tuple[date, datetime, UUID]:
    """Decode a cursor produced by encode_cursor."""

    try:
        occurred_on, created_at, transaction_id = json.loads(
            base64.urlsafe_b64decode(cursor.encode())
        )

        return (
            date.fromisoformat(occurred_on),
            datetime.fromisoformat(created_at),
            UUID(transaction_id),
        )
    except (binascii.Error, ValueError, TypeError) as exc:
        raise ValueError("Invalid cursor") from exc


async def _lock_and_get(
    connection: AsyncConnection, user_id: UUID, transaction_id: UUID
) -> Transaction:
    locked = await transaction_repository.lock_transaction(
        connection, user_id=user_id, transaction_id=transaction_id
    )

    transaction = (
        await transaction_repository.get_transaction(
            connection, user_id=user_id, transaction_id=transaction_id
        )
        if locked
        else None
    )

    if transaction is None:
        raise NotFoundError("Transaction not found")

    return transaction


async def _validate(
    connection: AsyncConnection,
    user_id: UUID,
    candidate: TransactionCreate,
    *,
    previous: Transaction | None,
) -> None:
    """Check every rule that depends on other rows (see module docstring)."""

    def is_new_reference(field: str) -> bool:
        return previous is None or getattr(previous, field) != getattr(candidate, field)

    accounts: dict[str, Account] = {}

    for field in ("from_account_id", "to_account_id"):
        account_id: UUID | None = getattr(candidate, field, None)

        if account_id is None:
            continue

        account = await account_repository.get_account(
            connection, user_id=user_id, account_id=account_id
        )

        if account is None:
            raise ValueError(f"{field} does not reference one of your accounts")

        if account.archived_at is not None and is_new_reference(field):
            raise ValueError(f"{field} references an archived account")

        accounts[field] = account

    if isinstance(candidate, TransferCreate) and (
        accounts["from_account_id"].currency != accounts["to_account_id"].currency
    ):
        raise ValueError("A transfer needs two accounts with the same currency")

    category_id: UUID | None = getattr(candidate, "category_id", None)

    if category_id is not None:
        category = await category_repository.get_category(
            connection, user_id=user_id, category_id=category_id
        )

        if category is None:
            raise ValueError("category_id does not reference one of your categories")

        expected_kind = CategoryKind(candidate.kind.value)

        if category.kind != expected_kind:
            raise ValueError(
                f"category_id must reference a category of kind {expected_kind}"
            )

        if category.archived_at is not None and is_new_reference("category_id"):
            raise ValueError("category_id references an archived category")

    investment_asset_id: UUID | None = getattr(candidate, "investment_asset_id", None)

    if investment_asset_id is not None:
        asset = await investment_asset_repository.get_investment_asset(
            connection, user_id=user_id, investment_asset_id=investment_asset_id
        )

        if asset is None:
            raise ValueError(
                "investment_asset_id does not reference one of your investment assets"
            )

        if asset.archived_at is not None and is_new_reference("investment_asset_id"):
            raise ValueError("investment_asset_id references an archived asset")

    if isinstance(candidate, ReimbursementCreate):
        await _validate_reimbursement(
            connection,
            user_id,
            candidate,
            to_account=accounts["to_account_id"],
            previous=previous,
        )

    if isinstance(candidate, ExpenseCreate) and previous is not None:
        await _validate_expense_against_reimbursements(
            connection, user_id, candidate, expense_id=previous.id
        )


async def _validate_reimbursement(
    connection: AsyncConnection,
    user_id: UUID,
    candidate: ReimbursementCreate,
    *,
    to_account: Account,
    previous: Transaction | None,
) -> None:
    expense_id = candidate.reimburses_transaction_id

    # Lock the expense first: every change to how much of it is reimbursed
    # takes this lock, so the cap check below cannot race.
    locked = await transaction_repository.lock_transaction(
        connection, user_id=user_id, transaction_id=expense_id
    )

    expense = (
        await transaction_repository.get_transaction(
            connection, user_id=user_id, transaction_id=expense_id
        )
        if locked
        else None
    )

    if expense is None:
        raise ValueError(
            "reimburses_transaction_id does not reference one of your transactions"
        )

    if expense.kind != TransactionKind.EXPENSE:
        raise ValueError("Only an expense can be reimbursed")

    if candidate.occurred_on < expense.occurred_on:
        raise ValueError("A reimbursement cannot be dated before its expense")

    assert expense.from_account_id is not None
    expense_account = await account_repository.get_account(
        connection, user_id=user_id, account_id=expense.from_account_id
    )

    assert expense_account is not None
    if expense_account.currency != to_account.currency:
        raise ValueError("A reimbursement must use the currency of its expense")

    already_reimbursed, _ = await transaction_repository.get_reimbursement_totals(
        connection,
        user_id=user_id,
        expense_id=expense_id,
        exclude_transaction_id=previous.id if previous else None,
    )

    remaining = expense.amount_minor - already_reimbursed

    if candidate.amount_minor > remaining:
        raise ValueError(
            "Reimbursements cannot exceed the expense: "
            f"{remaining} minor units left to reimburse"
        )


async def _validate_expense_against_reimbursements(
    connection: AsyncConnection,
    user_id: UUID,
    candidate: ExpenseCreate,
    *,
    expense_id: UUID,
) -> None:
    reimbursed, earliest = await transaction_repository.get_reimbursement_totals(
        connection, user_id=user_id, expense_id=expense_id
    )

    if candidate.amount_minor < reimbursed:
        raise ValueError(
            "The expense cannot be smaller than what was already reimbursed "
            f"({reimbursed} minor units)"
        )

    if earliest is not None and candidate.occurred_on > earliest:
        raise ValueError("The expense cannot be dated after its reimbursements")


def _describe_validation_error(exc: ValidationError) -> str:
    """Readable message for an invalid merged transaction (PATCH)."""

    messages = []

    for error in exc.errors():
        # The first location element is the discriminator tag (the kind).
        field = ".".join(str(part) for part in error["loc"][1:]) or "transaction"
        messages.append(f"{field}: {error['msg']}")

    return "; ".join(messages)

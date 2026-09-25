"""
Unit tests for the finance services that need no database:

- every service function refuses before touching PostgreSQL when the
  caller lacks the permission (the unit suite runs with no database, so a
  missing check would fail with a connection error instead);
- pagination cursors round-trip and reject garbage;
- default categories are well-formed;
- partial-update helpers.
"""

import re
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

import pytest

from app.auth.context import AppContext
from app.auth.permissions import FINANCE_READ, FINANCE_WRITE
from app.core.errors import PermissionDeniedError
from app.schemas.account import AccountCreate, AccountUpdate
from app.schemas.category import (
    ICON_PATTERN,
    CategoryCreate,
    CategoryKind,
    CategoryUpdate,
)
from app.schemas.investment_asset import InvestmentAssetCreate, InvestmentAssetUpdate
from app.schemas.transaction import (
    Transaction,
    TransactionFilters,
    TransactionKind,
    TransactionUpdate,
    transaction_create_adapter,
)
from app.services.finance import (
    accounts_service,
    categories_service,
    investment_assets_service,
    transactions_service,
)
from app.services.finance.categories_service import DEFAULT_CATEGORIES
from app.services.finance.updates import apply_archive_flag, reject_nulls

ID = uuid4()

EXPENSE = transaction_create_adapter.validate_python(
    {
        "kind": "EXPENSE",
        "amount_minor": 100,
        "occurred_on": "2026-09-25",
        "from_account_id": str(uuid4()),
        "category_id": str(uuid4()),
    }
)

ServiceCall = Callable[[AppContext], Awaitable[Any]]

READ_CALLS: list[ServiceCall] = [
    lambda c: accounts_service.list_accounts(c),
    lambda c: accounts_service.get_account(c, ID),
    lambda c: categories_service.list_categories(c),
    lambda c: categories_service.get_category(c, ID),
    lambda c: investment_assets_service.list_investment_assets(c),
    lambda c: investment_assets_service.get_investment_asset(c, ID),
    lambda c: transactions_service.list_transactions(c, TransactionFilters()),
    lambda c: transactions_service.get_transaction(c, ID),
]

WRITE_CALLS: list[ServiceCall] = [
    lambda c: accounts_service.create_account(
        c, AccountCreate.model_validate({"name": "A", "type": "CASH"})
    ),
    lambda c: accounts_service.update_account(c, ID, AccountUpdate(name="B")),
    lambda c: categories_service.create_category(
        c, CategoryCreate(name="C", kind=CategoryKind.EXPENSE, icon="circle")
    ),
    lambda c: categories_service.update_category(c, ID, CategoryUpdate(name="D")),
    lambda c: investment_assets_service.create_investment_asset(
        c, InvestmentAssetCreate.model_validate({"name": "E", "type": "ETF"})
    ),
    lambda c: investment_assets_service.update_investment_asset(
        c, ID, InvestmentAssetUpdate(name="F")
    ),
    lambda c: transactions_service.create_transaction(c, EXPENSE),
    lambda c: transactions_service.update_transaction(
        c, ID, TransactionUpdate(amount_minor=1)
    ),
    lambda c: transactions_service.delete_transaction(c, ID),
]


def _context(*permissions: str) -> AppContext:
    return AppContext(user_id=uuid4(), permissions=frozenset(permissions))


@pytest.mark.parametrize("call", READ_CALLS)
async def test_reads_require_finance_read(call: ServiceCall) -> None:
    with pytest.raises(PermissionDeniedError):
        await call(_context(FINANCE_WRITE))


@pytest.mark.parametrize("call", WRITE_CALLS)
async def test_writes_require_finance_write(call: ServiceCall) -> None:
    with pytest.raises(PermissionDeniedError):
        await call(_context(FINANCE_READ))


def _transaction() -> Transaction:
    return Transaction(
        id=uuid4(),
        kind=TransactionKind.EXPENSE,
        amount_minor=100,
        occurred_on=date(2026, 9, 25),
        description=None,
        from_account_id=uuid4(),
        to_account_id=None,
        category_id=uuid4(),
        investment_asset_id=None,
        reimburses_transaction_id=None,
        reimbursed_amount_minor=0,
        created_at=datetime(2026, 9, 25, 12, 30, 1, 123456, tzinfo=UTC),
        updated_at=datetime(2026, 9, 25, 12, 30, 1, 123456, tzinfo=UTC),
    )


def test_cursor_round_trips_the_keyset_position() -> None:
    transaction = _transaction()

    decoded = transactions_service.decode_cursor(
        transactions_service.encode_cursor(transaction)
    )

    assert decoded == (
        transaction.occurred_on,
        transaction.created_at,
        transaction.id,
    )


@pytest.mark.parametrize("cursor", ["garbage", "", "W10=", "WyJhIiwiYiIsImMiXQ=="])
def test_malformed_cursor_is_rejected(cursor: str) -> None:
    with pytest.raises(ValueError, match="Invalid cursor"):
        transactions_service.decode_cursor(cursor)


def test_default_categories_are_well_formed() -> None:
    keys = [(name.lower(), kind) for name, kind, _ in DEFAULT_CATEGORIES]

    assert len(keys) == len(set(keys))
    assert {kind for _, kind, _ in DEFAULT_CATEGORIES} == set(CategoryKind)
    assert all(re.fullmatch(ICON_PATTERN, icon) for _, _, icon in DEFAULT_CATEGORIES)


def test_reject_nulls_only_rejects_listed_fields() -> None:
    reject_nulls({"description": None}, ("name",))

    with pytest.raises(ValueError, match="'name' cannot be null"):
        reject_nulls({"name": None}, ("name",))


def test_archive_flag_keeps_the_original_timestamp() -> None:
    original = datetime(2026, 1, 1, tzinfo=UTC)

    archive_again: dict[str, Any] = {"archived": True}
    apply_archive_flag(archive_again, original)

    archive_now: dict[str, Any] = {"archived": True}
    apply_archive_flag(archive_now, None)

    restore: dict[str, Any] = {"archived": False}
    apply_archive_flag(restore, original)

    assert archive_again == {"archived_at": original}
    assert archive_now["archived_at"] is not None
    assert restore == {"archived_at": None}

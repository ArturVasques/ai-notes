"""
Integration tests for the finance baseline schema and its database-level
integrity rules, independent of the application services.

Uses the real PostgreSQL database with migrations applied.

- the baseline runs on plain PostgreSQL (no pgvector) and contains exactly
  the finance tables.
- users keep their identity uniqueness constraints.
- CHECK constraints reject non-positive amounts and malformed kinds.
- composite (user_id, id) foreign keys make it impossible to reference
  another user's rows, even with raw SQL.
- referenced rows cannot be deleted; deleting a user removes all its data.
"""

from uuid import UUID, uuid4

import pytest
from psycopg import errors

from app.auth.context import AppContext
from app.database.connection import pool
from tests.integration import factories
from tests.integration.conftest import UserFactory


async def _fetch_values(query: str) -> set[str]:
    async with pool.connection() as connection, connection.cursor() as cursor:
        await cursor.execute(query)
        rows = await cursor.fetchall()

    return {row[0] for row in rows}


async def _execute(query: str, params: tuple[object, ...]) -> None:
    async with pool.connection() as connection, connection.transaction():
        await connection.execute(query, params)


async def _insert_transaction(
    user_id: UUID,
    kind: str,
    amount_minor: int = 100,
    *,
    from_account_id: UUID | None = None,
    to_account_id: UUID | None = None,
    category_id: UUID | None = None,
) -> None:
    await _execute(
        """
        INSERT INTO transactions (
            id, user_id, kind, amount_minor, occurred_on,
            from_account_id, to_account_id, category_id
        )
        VALUES (%s, %s, %s, %s, '2026-09-10', %s, %s, %s)
        """,
        (
            uuid4(),
            user_id,
            kind,
            amount_minor,
            from_account_id,
            to_account_id,
            category_id,
        ),
    )


async def test_migration_head_is_the_finance_baseline() -> None:
    versions = await _fetch_values("SELECT version_num FROM alembic_version")

    assert versions == {"0001"}


async def test_schema_has_no_vector_extension() -> None:
    extensions = await _fetch_values("SELECT extname FROM pg_extension")

    assert "vector" not in extensions


async def test_schema_contains_exactly_the_finance_tables() -> None:
    tables = await _fetch_values(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        """
    )

    assert tables == {
        "alembic_version",
        "users",
        "accounts",
        "categories",
        "investment_assets",
        "transactions",
    }


async def test_money_columns_are_bigint() -> None:
    columns = await _fetch_values(
        """
        SELECT table_name || '.' || column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND column_name LIKE '%%_minor'
          AND data_type = 'bigint'
        """
    )

    assert columns == {
        "accounts.opening_balance_minor",
        "transactions.amount_minor",
    }


async def test_user_external_identity_must_be_unique(user: AppContext) -> None:
    with pytest.raises(errors.UniqueViolation):
        await _execute(
            """
            INSERT INTO users (id, external_identity_id, name, email)
            VALUES (%s, %s, 'Duplicate', %s)
            """,
            (uuid4(), f"test-{user.user_id}", f"{uuid4()}@test.local"),
        )


async def test_user_email_is_optional_and_not_an_identity_key(
    user: AppContext,
) -> None:
    """Email may be missing or shared; only external_identity_id identifies."""

    first = f"test-{uuid4()}"
    second = f"test-{uuid4()}"

    try:
        await _execute(
            """
            INSERT INTO users (id, external_identity_id, name, email)
            VALUES (%s, %s, 'No email', NULL)
            """,
            (uuid4(), first),
        )
        await _execute(
            """
            INSERT INTO users (id, external_identity_id, name, email)
            VALUES (%s, %s, 'Same email', %s)
            """,
            (uuid4(), second, f"{user.user_id}@test.local"),
        )
    finally:
        await _execute(
            "DELETE FROM users WHERE external_identity_id = ANY(%s)",
            ([first, second],),
        )


@pytest.mark.parametrize("amount_minor", [0, -1])
async def test_transaction_amount_must_be_positive(
    user: AppContext, amount_minor: int
) -> None:
    account = await factories.account(user)
    category = await factories.category(user)

    with pytest.raises(errors.CheckViolation):
        await _insert_transaction(
            user.user_id,
            "EXPENSE",
            amount_minor,
            from_account_id=account.id,
            category_id=category.id,
        )


async def test_expense_without_category_violates_the_shape_check(
    user: AppContext,
) -> None:
    account = await factories.account(user)

    with pytest.raises(errors.CheckViolation, match="transactions_kind_shape_check"):
        await _insert_transaction(user.user_id, "EXPENSE", from_account_id=account.id)


async def test_transfer_to_the_same_account_violates_the_shape_check(
    user: AppContext,
) -> None:
    account = await factories.account(user)

    with pytest.raises(errors.CheckViolation, match="transactions_kind_shape_check"):
        await _insert_transaction(
            user.user_id,
            "TRANSFER",
            from_account_id=account.id,
            to_account_id=account.id,
        )


async def test_transfer_with_a_category_violates_the_shape_check(
    user: AppContext,
) -> None:
    source = await factories.account(user, "Current")
    target = await factories.account(user, "Savings")
    category = await factories.category(user)

    with pytest.raises(errors.CheckViolation, match="transactions_kind_shape_check"):
        await _insert_transaction(
            user.user_id,
            "TRANSFER",
            from_account_id=source.id,
            to_account_id=target.id,
            category_id=category.id,
        )


async def test_raw_sql_cannot_reference_another_users_account(
    user: AppContext, other_user: AppContext
) -> None:
    foreign_account = await factories.account(other_user)
    own_category = await factories.category(user)

    with pytest.raises(errors.ForeignKeyViolation):
        await _insert_transaction(
            user.user_id,
            "EXPENSE",
            from_account_id=foreign_account.id,
            category_id=own_category.id,
        )


async def test_raw_sql_cannot_reference_another_users_category(
    user: AppContext, other_user: AppContext
) -> None:
    own_account = await factories.account(user)
    foreign_category = await factories.category(other_user)

    with pytest.raises(errors.ForeignKeyViolation):
        await _insert_transaction(
            user.user_id,
            "EXPENSE",
            from_account_id=own_account.id,
            category_id=foreign_category.id,
        )


async def test_account_used_by_a_transaction_cannot_be_deleted(
    user: AppContext,
) -> None:
    account = await factories.account(user)
    category = await factories.category(user)
    await factories.expense(user, from_account_id=account.id, category_id=category.id)

    with pytest.raises(errors.ForeignKeyViolation):
        await _execute("DELETE FROM accounts WHERE id = %s", (account.id,))


async def test_deleting_a_user_removes_all_its_finance_rows(
    make_user: UserFactory,
) -> None:
    doomed = await make_user()

    account = await factories.account(doomed)
    category = await factories.category(doomed)
    expense = await factories.expense(
        doomed, from_account_id=account.id, category_id=category.id
    )
    await factories.reimbursement(
        doomed, to_account_id=account.id, expense_id=expense.id, amount_minor=500
    )

    await _execute("DELETE FROM users WHERE id = %s", (doomed.user_id,))

    async with pool.connection() as connection, connection.cursor() as cursor:
        await cursor.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM accounts WHERE user_id = %(user_id)s),
                (SELECT COUNT(*) FROM categories WHERE user_id = %(user_id)s),
                (SELECT COUNT(*) FROM transactions WHERE user_id = %(user_id)s)
            """,
            {"user_id": doomed.user_id},
        )
        counts = await cursor.fetchone()

    assert counts == (0, 0, 0)

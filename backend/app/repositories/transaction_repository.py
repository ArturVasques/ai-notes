"""
Persistence for transactions.

Every query is scoped to the owner's user_id in SQL. Functions receive the
connection from the calling service so validation, locking and writes share
one database transaction.

Used by:
- services/finance/transactions_service.py
"""

from collections.abc import Mapping
from datetime import date, datetime
from uuid import UUID

from psycopg import AsyncConnection, sql
from psycopg.rows import class_row

from app.schemas.transaction import Transaction, TransactionFilters

# Columns of the transaction plus the total already reimbursed against it.
_SELECT = sql.SQL("""
    SELECT
        t.id,
        t.kind,
        t.amount_minor,
        t.occurred_on,
        t.description,
        t.from_account_id,
        t.to_account_id,
        t.category_id,
        t.investment_asset_id,
        t.reimburses_transaction_id,
        COALESCE(reimbursed.total, 0)::BIGINT AS reimbursed_amount_minor,
        t.created_at,
        t.updated_at
    FROM transactions t
    LEFT JOIN LATERAL (
        SELECT SUM(r.amount_minor) AS total
        FROM transactions r
        WHERE r.user_id = t.user_id
          AND r.reimburses_transaction_id = t.id
    ) reimbursed ON TRUE
""")

WRITABLE_COLUMNS = (
    "amount_minor",
    "occurred_on",
    "description",
    "from_account_id",
    "to_account_id",
    "category_id",
    "investment_asset_id",
    "reimburses_transaction_id",
)


async def insert_transaction(
    connection: AsyncConnection,
    *,
    user_id: UUID,
    transaction_id: UUID,
    kind: str,
    values: Mapping[str, object],
) -> None:
    """
    Insert a transaction owned by the user.

    `values` holds the writable columns; columns the kind does not use are
    stored as NULL.
    """

    await connection.execute(
        """
        INSERT INTO transactions (
            id, user_id, kind, amount_minor, occurred_on, description,
            from_account_id, to_account_id, category_id, investment_asset_id,
            reimburses_transaction_id
        )
        VALUES (
            %(id)s, %(user_id)s, %(kind)s, %(amount_minor)s, %(occurred_on)s,
            %(description)s, %(from_account_id)s, %(to_account_id)s,
            %(category_id)s, %(investment_asset_id)s,
            %(reimburses_transaction_id)s
        )
        """,
        {
            **{column: values.get(column) for column in WRITABLE_COLUMNS},
            "id": transaction_id,
            "user_id": user_id,
            "kind": kind,
        },
    )


async def update_transaction(
    connection: AsyncConnection,
    *,
    user_id: UUID,
    transaction_id: UUID,
    values: Mapping[str, object],
) -> None:
    """
    Replace every writable column of the user's transaction.

    The kind is never updated. Columns missing from `values` become NULL,
    which keeps the row consistent with the database shape CHECK.
    """

    await connection.execute(
        """
        UPDATE transactions
        SET amount_minor = %(amount_minor)s,
            occurred_on = %(occurred_on)s,
            description = %(description)s,
            from_account_id = %(from_account_id)s,
            to_account_id = %(to_account_id)s,
            category_id = %(category_id)s,
            investment_asset_id = %(investment_asset_id)s,
            reimburses_transaction_id = %(reimburses_transaction_id)s,
            updated_at = NOW()
        WHERE user_id = %(user_id)s AND id = %(id)s
        """,
        {
            **{column: values.get(column) for column in WRITABLE_COLUMNS},
            "id": transaction_id,
            "user_id": user_id,
        },
    )


async def delete_transaction(
    connection: AsyncConnection,
    *,
    user_id: UUID,
    transaction_id: UUID,
) -> None:
    """Delete the user's transaction."""

    await connection.execute(
        "DELETE FROM transactions WHERE user_id = %s AND id = %s",
        (user_id, transaction_id),
    )


async def lock_transaction(
    connection: AsyncConnection,
    *,
    user_id: UUID,
    transaction_id: UUID,
) -> bool:
    """
    Lock the user's transaction row until the current database transaction
    ends. Returns False when it does not exist for this user.

    Locking an expense serializes every operation that changes how much of
    it is reimbursed, so concurrent reimbursements cannot exceed it.
    """

    async with connection.cursor() as cursor:
        await cursor.execute(
            """
            SELECT 1
            FROM transactions
            WHERE user_id = %s AND id = %s
            FOR UPDATE
            """,
            (user_id, transaction_id),
        )

        return await cursor.fetchone() is not None


async def get_transaction(
    connection: AsyncConnection,
    *,
    user_id: UUID,
    transaction_id: UUID,
) -> Transaction | None:
    """Return the user's transaction."""

    async with connection.cursor(row_factory=class_row(Transaction)) as cursor:
        await cursor.execute(
            _SELECT + sql.SQL(" WHERE t.user_id = %s AND t.id = %s"),
            (user_id, transaction_id),
        )

        return await cursor.fetchone()


async def get_reimbursement_totals(
    connection: AsyncConnection,
    *,
    user_id: UUID,
    expense_id: UUID,
    exclude_transaction_id: UUID | None = None,
) -> tuple[int, date | None]:
    """
    Return (sum of amounts, earliest date) of the reimbursements linked to
    an expense, optionally ignoring one reimbursement (the one being edited).
    """

    async with connection.cursor() as cursor:
        await cursor.execute(
            """
            SELECT COALESCE(SUM(amount_minor), 0)::BIGINT, MIN(occurred_on)
            FROM transactions
            WHERE user_id = %s
              AND reimburses_transaction_id = %s
              AND (%s::UUID IS NULL OR id <> %s::UUID)
            """,
            (user_id, expense_id, exclude_transaction_id, exclude_transaction_id),
        )

        row = await cursor.fetchone()

    assert row is not None
    return int(row[0]), row[1]


async def list_transactions(
    connection: AsyncConnection,
    *,
    user_id: UUID,
    filters: TransactionFilters,
    limit: int,
    after: tuple[date, datetime, UUID] | None,
) -> list[Transaction]:
    """
    Return the user's transactions, newest first, using keyset pagination.

    `after` is the (occurred_on, created_at, id) of the last row of the
    previous page.
    """

    conditions = [sql.SQL("t.user_id = %(user_id)s")]
    params: dict[str, object] = {"user_id": user_id, "limit": limit}

    if filters.date_from is not None:
        conditions.append(sql.SQL("t.occurred_on >= %(date_from)s"))
        params["date_from"] = filters.date_from

    if filters.date_to is not None:
        conditions.append(sql.SQL("t.occurred_on <= %(date_to)s"))
        params["date_to"] = filters.date_to

    if filters.kind is not None:
        conditions.append(sql.SQL("t.kind = %(kind)s"))
        params["kind"] = filters.kind.value

    if filters.account_id is not None:
        conditions.append(
            sql.SQL(
                "(t.from_account_id = %(account_id)s"
                " OR t.to_account_id = %(account_id)s)"
            )
        )
        params["account_id"] = filters.account_id

    if filters.category_id is not None:
        # A reimbursement inherits the category of the expense it repays.
        conditions.append(
            sql.SQL("""
                (t.category_id = %(category_id)s
                 OR EXISTS (
                     SELECT 1
                     FROM transactions e
                     WHERE e.user_id = t.user_id
                       AND e.id = t.reimburses_transaction_id
                       AND e.category_id = %(category_id)s
                 ))
            """)
        )
        params["category_id"] = filters.category_id

    if filters.investment_asset_id is not None:
        conditions.append(sql.SQL("t.investment_asset_id = %(investment_asset_id)s"))
        params["investment_asset_id"] = filters.investment_asset_id

    if after is not None:
        conditions.append(
            sql.SQL(
                "(t.occurred_on, t.created_at, t.id)"
                " < (%(after_date)s, %(after_created_at)s, %(after_id)s)"
            )
        )
        params["after_date"], params["after_created_at"], params["after_id"] = after

    query = (
        _SELECT
        + sql.SQL(" WHERE ")
        + sql.SQL(" AND ").join(conditions)
        + sql.SQL(
            " ORDER BY t.occurred_on DESC, t.created_at DESC, t.id DESC LIMIT %(limit)s"
        )
    )

    async with connection.cursor(row_factory=class_row(Transaction)) as cursor:
        await cursor.execute(query, params)

        return await cursor.fetchall()

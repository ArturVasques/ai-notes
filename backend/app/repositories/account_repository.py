"""
Persistence for accounts.

Every query is scoped to the owner's user_id in SQL. Functions receive the
connection from the calling service so several operations can share one
database transaction.

Used by:
- services/finance/accounts_service.py
- services/finance/transactions_service.py (reference validation)
"""

from collections.abc import Mapping
from uuid import UUID

from psycopg import AsyncConnection, sql
from psycopg.rows import class_row

from app.database.sql import set_clause
from app.schemas.account import Account

_COLUMNS = sql.SQL("""
    id, name, type, description, currency, opening_balance_minor,
    archived_at, created_at
""")

UPDATABLE_COLUMNS = frozenset(
    {"name", "type", "description", "opening_balance_minor", "archived_at"}
)


async def insert_account(
    connection: AsyncConnection,
    *,
    user_id: UUID,
    account_id: UUID,
    name: str,
    account_type: str,
    description: str | None,
    currency: str,
    opening_balance_minor: int,
) -> Account:
    """Insert an account owned by the user."""

    async with connection.cursor(row_factory=class_row(Account)) as cursor:
        await cursor.execute(
            sql.SQL("""
                INSERT INTO accounts (
                    id, user_id, name, type, description, currency,
                    opening_balance_minor
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING {columns}
            """).format(columns=_COLUMNS),
            (
                account_id,
                user_id,
                name,
                account_type,
                description,
                currency,
                opening_balance_minor,
            ),
        )

        row = await cursor.fetchone()

    assert row is not None
    return row


async def get_account(
    connection: AsyncConnection,
    *,
    user_id: UUID,
    account_id: UUID,
    for_update: bool = False,
) -> Account | None:
    """Return the user's account, optionally locking it for update."""

    lock = sql.SQL("FOR UPDATE") if for_update else sql.SQL("")

    async with connection.cursor(row_factory=class_row(Account)) as cursor:
        await cursor.execute(
            sql.SQL("""
                SELECT {columns}
                FROM accounts
                WHERE user_id = %s AND id = %s
                {lock}
            """).format(columns=_COLUMNS, lock=lock),
            (user_id, account_id),
        )

        return await cursor.fetchone()


async def list_accounts(
    connection: AsyncConnection,
    *,
    user_id: UUID,
    include_archived: bool,
) -> list[Account]:
    """Return the user's accounts, active first, then by name."""

    async with connection.cursor(row_factory=class_row(Account)) as cursor:
        await cursor.execute(
            sql.SQL("""
                SELECT {columns}
                FROM accounts
                WHERE user_id = %s
                  AND (%s OR archived_at IS NULL)
                ORDER BY archived_at IS NOT NULL, lower(name), created_at
            """).format(columns=_COLUMNS),
            (user_id, include_archived),
        )

        return await cursor.fetchall()


async def update_account(
    connection: AsyncConnection,
    *,
    user_id: UUID,
    account_id: UUID,
    changes: Mapping[str, object],
) -> Account | None:
    """Apply a partial update to the user's account."""

    if not changes.keys() <= UPDATABLE_COLUMNS:
        raise ValueError(f"Columns not updatable: {set(changes) - UPDATABLE_COLUMNS}")

    async with connection.cursor(row_factory=class_row(Account)) as cursor:
        await cursor.execute(
            sql.SQL("""
                UPDATE accounts
                SET {assignments}
                WHERE user_id = %(user_id)s AND id = %(account_id)s
                RETURNING {columns}
            """).format(assignments=set_clause(changes), columns=_COLUMNS),
            {**changes, "user_id": user_id, "account_id": account_id},
        )

        return await cursor.fetchone()

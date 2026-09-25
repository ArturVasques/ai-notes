"""
Persistence for investment assets.

Every query is scoped to the owner's user_id in SQL. Functions receive the
connection from the calling service so several operations can share one
database transaction.

Used by:
- services/finance/investment_assets_service.py
- services/finance/transactions_service.py (reference validation)
"""

from collections.abc import Mapping
from uuid import UUID

from psycopg import AsyncConnection, sql
from psycopg.rows import class_row

from app.database.sql import set_clause
from app.schemas.investment_asset import InvestmentAsset

_COLUMNS = sql.SQL("id, name, symbol, type, archived_at, created_at")

UPDATABLE_COLUMNS = frozenset({"name", "symbol", "type", "archived_at"})


async def insert_investment_asset(
    connection: AsyncConnection,
    *,
    user_id: UUID,
    investment_asset_id: UUID,
    name: str,
    symbol: str | None,
    asset_type: str,
) -> InvestmentAsset:
    """Insert an investment asset owned by the user."""

    async with connection.cursor(row_factory=class_row(InvestmentAsset)) as cursor:
        await cursor.execute(
            sql.SQL("""
                INSERT INTO investment_assets (id, user_id, name, symbol, type)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING {columns}
            """).format(columns=_COLUMNS),
            (investment_asset_id, user_id, name, symbol, asset_type),
        )

        row = await cursor.fetchone()

    assert row is not None
    return row


async def get_investment_asset(
    connection: AsyncConnection,
    *,
    user_id: UUID,
    investment_asset_id: UUID,
    for_update: bool = False,
) -> InvestmentAsset | None:
    """Return the user's investment asset, optionally locking it for update."""

    lock = sql.SQL("FOR UPDATE") if for_update else sql.SQL("")

    async with connection.cursor(row_factory=class_row(InvestmentAsset)) as cursor:
        await cursor.execute(
            sql.SQL("""
                SELECT {columns}
                FROM investment_assets
                WHERE user_id = %s AND id = %s
                {lock}
            """).format(columns=_COLUMNS, lock=lock),
            (user_id, investment_asset_id),
        )

        return await cursor.fetchone()


async def list_investment_assets(
    connection: AsyncConnection,
    *,
    user_id: UUID,
    include_archived: bool,
) -> list[InvestmentAsset]:
    """Return the user's investment assets, active first, then by name."""

    async with connection.cursor(row_factory=class_row(InvestmentAsset)) as cursor:
        await cursor.execute(
            sql.SQL("""
                SELECT {columns}
                FROM investment_assets
                WHERE user_id = %s
                  AND (%s OR archived_at IS NULL)
                ORDER BY archived_at IS NOT NULL, lower(name), created_at
            """).format(columns=_COLUMNS),
            (user_id, include_archived),
        )

        return await cursor.fetchall()


async def update_investment_asset(
    connection: AsyncConnection,
    *,
    user_id: UUID,
    investment_asset_id: UUID,
    changes: Mapping[str, object],
) -> InvestmentAsset | None:
    """Apply a partial update to the user's investment asset."""

    if not changes.keys() <= UPDATABLE_COLUMNS:
        raise ValueError(f"Columns not updatable: {set(changes) - UPDATABLE_COLUMNS}")

    async with connection.cursor(row_factory=class_row(InvestmentAsset)) as cursor:
        await cursor.execute(
            sql.SQL("""
                UPDATE investment_assets
                SET {assignments}
                WHERE user_id = %(user_id)s AND id = %(investment_asset_id)s
                RETURNING {columns}
            """).format(assignments=set_clause(changes), columns=_COLUMNS),
            {
                **changes,
                "user_id": user_id,
                "investment_asset_id": investment_asset_id,
            },
        )

        return await cursor.fetchone()

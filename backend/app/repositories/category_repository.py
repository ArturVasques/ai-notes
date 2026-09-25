"""
Persistence for income and expense categories.

Every query is scoped to the owner's user_id in SQL. Functions receive the
connection from the calling service so several operations can share one
database transaction.

Used by:
- services/finance/categories_service.py
- services/finance/transactions_service.py (reference validation)
"""

from collections.abc import Mapping, Sequence
from uuid import UUID, uuid4

from psycopg import AsyncConnection, sql
from psycopg.rows import class_row

from app.database.sql import set_clause
from app.schemas.category import Category

_COLUMNS = sql.SQL("id, name, kind, icon, archived_at, created_at")

UPDATABLE_COLUMNS = frozenset({"name", "icon", "archived_at"})


async def insert_category(
    connection: AsyncConnection,
    *,
    user_id: UUID,
    category_id: UUID,
    name: str,
    kind: str,
    icon: str,
) -> Category:
    """Insert a category owned by the user."""

    async with connection.cursor(row_factory=class_row(Category)) as cursor:
        await cursor.execute(
            sql.SQL("""
                INSERT INTO categories (id, user_id, name, kind, icon)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING {columns}
            """).format(columns=_COLUMNS),
            (category_id, user_id, name, kind, icon),
        )

        row = await cursor.fetchone()

    assert row is not None
    return row


async def insert_missing_categories(
    connection: AsyncConnection,
    *,
    user_id: UUID,
    categories: Sequence[tuple[str, str, str]],
) -> int:
    """
    Insert (name, kind, icon) categories the user does not have yet.

    An active category with the same kind and name (case-insensitive) is
    left untouched, which makes provisioning idempotent. Returns the number
    of categories inserted.
    """

    inserted = 0

    async with connection.cursor() as cursor:
        for name, kind, icon in categories:
            await cursor.execute(
                """
                INSERT INTO categories (id, user_id, name, kind, icon)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (user_id, kind, lower(name))
                    WHERE archived_at IS NULL
                    DO NOTHING
                """,
                (uuid4(), user_id, name, kind, icon),
            )

            inserted += cursor.rowcount

    return inserted


async def get_category(
    connection: AsyncConnection,
    *,
    user_id: UUID,
    category_id: UUID,
    for_update: bool = False,
) -> Category | None:
    """Return the user's category, optionally locking it for update."""

    lock = sql.SQL("FOR UPDATE") if for_update else sql.SQL("")

    async with connection.cursor(row_factory=class_row(Category)) as cursor:
        await cursor.execute(
            sql.SQL("""
                SELECT {columns}
                FROM categories
                WHERE user_id = %s AND id = %s
                {lock}
            """).format(columns=_COLUMNS, lock=lock),
            (user_id, category_id),
        )

        return await cursor.fetchone()


async def list_categories(
    connection: AsyncConnection,
    *,
    user_id: UUID,
    kind: str | None,
    include_archived: bool,
) -> list[Category]:
    """Return the user's categories, active first, then by kind and name."""

    async with connection.cursor(row_factory=class_row(Category)) as cursor:
        await cursor.execute(
            sql.SQL("""
                SELECT {columns}
                FROM categories
                WHERE user_id = %s
                  AND (%s::TEXT IS NULL OR kind = %s)
                  AND (%s OR archived_at IS NULL)
                ORDER BY archived_at IS NOT NULL, kind, lower(name), created_at
            """).format(columns=_COLUMNS),
            (user_id, kind, kind, include_archived),
        )

        return await cursor.fetchall()


async def update_category(
    connection: AsyncConnection,
    *,
    user_id: UUID,
    category_id: UUID,
    changes: Mapping[str, object],
) -> Category | None:
    """Apply a partial update to the user's category."""

    if not changes.keys() <= UPDATABLE_COLUMNS:
        raise ValueError(f"Columns not updatable: {set(changes) - UPDATABLE_COLUMNS}")

    async with connection.cursor(row_factory=class_row(Category)) as cursor:
        await cursor.execute(
            sql.SQL("""
                UPDATE categories
                SET {assignments}
                WHERE user_id = %(user_id)s AND id = %(category_id)s
                RETURNING {columns}
            """).format(assignments=set_clause(changes), columns=_COLUMNS),
            {**changes, "user_id": user_id, "category_id": category_id},
        )

        return await cursor.fetchone()

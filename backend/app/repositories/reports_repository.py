"""
Aggregation queries behind the financial reports.

Every query is scoped to the owner's user_id in SQL. Amounts are summed in
PostgreSQL as BIGINT and returned as Python ints. Dates are inclusive.

Used by:
- services/finance/reports_service.py
- services/finance/accounts_service.py (balances)
"""

from datetime import date
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.rows import dict_row


async def get_flow_totals(
    connection: AsyncConnection, *, user_id: UUID, date_from: date, date_to: date
) -> dict[str, int]:
    """Sum of each transaction kind dated inside the period."""

    async with connection.cursor(row_factory=dict_row) as cursor:
        await cursor.execute(
            """
            SELECT
                COALESCE(SUM(amount_minor) FILTER (WHERE kind = 'INCOME'), 0)::BIGINT
                    AS income,
                COALESCE(SUM(amount_minor) FILTER (WHERE kind = 'EXPENSE'), 0)::BIGINT
                    AS gross_expenses,
                COALESCE(
                    SUM(amount_minor) FILTER (WHERE kind = 'REIMBURSEMENT'), 0
                )::BIGINT AS reimbursements_received,
                COALESCE(
                    SUM(amount_minor) FILTER (WHERE kind = 'INVESTMENT'), 0
                )::BIGINT AS invested,
                COALESCE(SUM(amount_minor) FILTER (WHERE kind = 'TRANSFER'), 0)::BIGINT
                    AS transfers
            FROM transactions
            WHERE user_id = %s AND occurred_on BETWEEN %s AND %s
            """,
            (user_id, date_from, date_to),
        )

        row = await cursor.fetchone()

    assert row is not None
    return {key: int(value) for key, value in row.items()}


async def get_reimbursements_attributed(
    connection: AsyncConnection, *, user_id: UUID, date_from: date, date_to: date
) -> int:
    """
    Reimbursements linked to expenses dated inside the period, whatever the
    date the reimbursement itself arrived (effective spending, D3).
    """

    async with connection.cursor() as cursor:
        await cursor.execute(
            """
            SELECT COALESCE(SUM(r.amount_minor), 0)::BIGINT
            FROM transactions r
            JOIN transactions e
              ON e.user_id = r.user_id
             AND e.id = r.reimburses_transaction_id
            WHERE r.user_id = %s
              AND r.kind = 'REIMBURSEMENT'
              AND e.occurred_on BETWEEN %s AND %s
            """,
            (user_id, date_from, date_to),
        )

        row = await cursor.fetchone()

    assert row is not None
    return int(row[0])


async def get_savings_account_movements(
    connection: AsyncConnection, *, user_id: UUID, date_from: date, date_to: date
) -> list[dict[str, Any]]:
    """Inflows and outflows of every SAVINGS account inside the period."""

    async with connection.cursor(row_factory=dict_row) as cursor:
        await cursor.execute(
            """
            SELECT
                a.id AS account_id,
                a.name,
                a.archived_at IS NOT NULL AS archived,
                COALESCE(
                    SUM(t.amount_minor) FILTER (WHERE t.to_account_id = a.id), 0
                )::BIGINT AS inflows_minor,
                COALESCE(
                    SUM(t.amount_minor) FILTER (WHERE t.from_account_id = a.id), 0
                )::BIGINT AS outflows_minor
            FROM accounts a
            LEFT JOIN transactions t
              ON t.user_id = a.user_id
             AND (t.from_account_id = a.id OR t.to_account_id = a.id)
             AND t.occurred_on BETWEEN %s AND %s
            WHERE a.user_id = %s AND a.type = 'SAVINGS'
            GROUP BY a.id, a.name, a.archived_at
            ORDER BY a.archived_at IS NOT NULL, lower(a.name)
            """,
            (date_from, date_to, user_id),
        )

        return await cursor.fetchall()


async def get_category_breakdown(
    connection: AsyncConnection,
    *,
    user_id: UUID,
    kind: str,
    date_from: date,
    date_to: date,
) -> list[dict[str, Any]]:
    """
    Per-category totals of transactions dated inside the period, with the
    reimbursements linked to those transactions (any reimbursement date).
    """

    async with connection.cursor(row_factory=dict_row) as cursor:
        await cursor.execute(
            """
            SELECT
                c.id AS category_id,
                c.name,
                c.icon,
                c.kind,
                c.archived_at IS NOT NULL AS archived,
                COALESCE(SUM(t.amount_minor), 0)::BIGINT AS gross_minor,
                COALESCE(SUM(reimbursed.total), 0)::BIGINT AS reimbursed_minor,
                COUNT(t.id)::INTEGER AS transaction_count
            FROM categories c
            JOIN transactions t
              ON t.user_id = c.user_id
             AND t.category_id = c.id
             AND t.occurred_on BETWEEN %s AND %s
            LEFT JOIN LATERAL (
                SELECT SUM(r.amount_minor) AS total
                FROM transactions r
                WHERE r.user_id = t.user_id
                  AND r.reimburses_transaction_id = t.id
            ) reimbursed ON TRUE
            WHERE c.user_id = %s AND c.kind = %s
            GROUP BY c.id, c.name, c.icon, c.kind, c.archived_at
            ORDER BY
                COALESCE(SUM(t.amount_minor), 0)
                    - COALESCE(SUM(reimbursed.total), 0) DESC,
                lower(c.name)
            """,
            (date_from, date_to, user_id, kind),
        )

        return await cursor.fetchall()


async def get_investments_by_asset(
    connection: AsyncConnection,
    *,
    user_id: UUID,
    date_from: date | None,
    date_to: date | None,
) -> list[dict[str, Any]]:
    """Money invested per asset, optionally limited to a period."""

    async with connection.cursor(row_factory=dict_row) as cursor:
        await cursor.execute(
            """
            SELECT
                ia.id AS investment_asset_id,
                ia.name,
                ia.symbol,
                ia.type,
                ia.archived_at IS NOT NULL AS archived,
                COALESCE(SUM(t.amount_minor), 0)::BIGINT AS invested_minor,
                COUNT(t.id)::INTEGER AS transaction_count
            FROM investment_assets ia
            JOIN transactions t
              ON t.user_id = ia.user_id
             AND t.investment_asset_id = ia.id
             AND t.kind = 'INVESTMENT'
             AND (%(date_from)s::DATE IS NULL OR t.occurred_on >= %(date_from)s)
             AND (%(date_to)s::DATE IS NULL OR t.occurred_on <= %(date_to)s)
            WHERE ia.user_id = %(user_id)s
            GROUP BY ia.id, ia.name, ia.symbol, ia.type, ia.archived_at
            ORDER BY COALESCE(SUM(t.amount_minor), 0) DESC, lower(ia.name)
            """,
            {"user_id": user_id, "date_from": date_from, "date_to": date_to},
        )

        return await cursor.fetchall()


async def get_investments_by_source_account(
    connection: AsyncConnection,
    *,
    user_id: UUID,
    date_from: date | None,
    date_to: date | None,
) -> list[dict[str, Any]]:
    """Money invested per account it left from, optionally for a period."""

    async with connection.cursor(row_factory=dict_row) as cursor:
        await cursor.execute(
            """
            SELECT
                a.id AS account_id,
                a.name,
                COALESCE(SUM(t.amount_minor), 0)::BIGINT AS invested_minor
            FROM accounts a
            JOIN transactions t
              ON t.user_id = a.user_id
             AND t.from_account_id = a.id
             AND t.kind = 'INVESTMENT'
             AND (%(date_from)s::DATE IS NULL OR t.occurred_on >= %(date_from)s)
             AND (%(date_to)s::DATE IS NULL OR t.occurred_on <= %(date_to)s)
            WHERE a.user_id = %(user_id)s
            GROUP BY a.id, a.name
            ORDER BY COALESCE(SUM(t.amount_minor), 0) DESC, lower(a.name)
            """,
            {"user_id": user_id, "date_from": date_from, "date_to": date_to},
        )

        return await cursor.fetchall()


async def get_monthly_flows(
    connection: AsyncConnection, *, user_id: UUID, date_from: date, date_to: date
) -> dict[str, dict[str, int]]:
    """
    Per calendar month (`YYYY-MM`): income, gross expenses, reimbursements
    received, investments, and the net movement of SAVINGS accounts, all by
    real transaction date.
    """

    async with connection.cursor(row_factory=dict_row) as cursor:
        await cursor.execute(
            """
            SELECT
                to_char(date_trunc('month', t.occurred_on), 'YYYY-MM') AS month,
                COALESCE(
                    SUM(t.amount_minor) FILTER (WHERE t.kind = 'INCOME'), 0
                )::BIGINT AS income,
                COALESCE(
                    SUM(t.amount_minor) FILTER (WHERE t.kind = 'EXPENSE'), 0
                )::BIGINT AS gross_expenses,
                COALESCE(
                    SUM(t.amount_minor) FILTER (WHERE t.kind = 'REIMBURSEMENT'), 0
                )::BIGINT AS reimbursements_received,
                COALESCE(
                    SUM(t.amount_minor) FILTER (WHERE t.kind = 'INVESTMENT'), 0
                )::BIGINT AS invested,
                COALESCE(
                    SUM(t.amount_minor) FILTER (WHERE ta.type = 'SAVINGS'), 0
                )::BIGINT
                - COALESCE(
                    SUM(t.amount_minor) FILTER (WHERE fa.type = 'SAVINGS'), 0
                )::BIGINT AS savings_accounts
            FROM transactions t
            LEFT JOIN accounts ta
              ON ta.user_id = t.user_id AND ta.id = t.to_account_id
            LEFT JOIN accounts fa
              ON fa.user_id = t.user_id AND fa.id = t.from_account_id
            WHERE t.user_id = %s AND t.occurred_on BETWEEN %s AND %s
            GROUP BY 1
            """,
            (user_id, date_from, date_to),
        )

        rows = await cursor.fetchall()

    return {
        row["month"]: {key: int(value) for key, value in row.items() if key != "month"}
        for row in rows
    }


async def get_monthly_reimbursements_attributed(
    connection: AsyncConnection, *, user_id: UUID, date_from: date, date_to: date
) -> dict[str, int]:
    """Reimbursements grouped by the month of the expense they repay."""

    async with connection.cursor() as cursor:
        await cursor.execute(
            """
            SELECT
                to_char(date_trunc('month', e.occurred_on), 'YYYY-MM') AS month,
                COALESCE(SUM(r.amount_minor), 0)::BIGINT
            FROM transactions r
            JOIN transactions e
              ON e.user_id = r.user_id
             AND e.id = r.reimburses_transaction_id
            WHERE r.user_id = %s
              AND r.kind = 'REIMBURSEMENT'
              AND e.occurred_on BETWEEN %s AND %s
            GROUP BY 1
            """,
            (user_id, date_from, date_to),
        )

        rows = await cursor.fetchall()

    return {row[0]: int(row[1]) for row in rows}


async def get_account_balances(
    connection: AsyncConnection,
    *,
    user_id: UUID,
    as_of: date | None,
    include_archived: bool,
) -> list[dict[str, Any]]:
    """Opening balance plus every movement dated up to `as_of` (or all)."""

    async with connection.cursor(row_factory=dict_row) as cursor:
        await cursor.execute(
            """
            SELECT
                a.id, a.name, a.type, a.description, a.currency,
                a.opening_balance_minor, a.archived_at, a.created_at,
                (
                    a.opening_balance_minor
                    + COALESCE(
                        SUM(t.amount_minor) FILTER (WHERE t.to_account_id = a.id), 0
                    )
                    - COALESCE(
                        SUM(t.amount_minor) FILTER (WHERE t.from_account_id = a.id), 0
                    )
                )::BIGINT AS balance_minor
            FROM accounts a
            LEFT JOIN transactions t
              ON t.user_id = a.user_id
             AND (t.from_account_id = a.id OR t.to_account_id = a.id)
             AND (%(as_of)s::DATE IS NULL OR t.occurred_on <= %(as_of)s)
            WHERE a.user_id = %(user_id)s
              AND (%(include_archived)s OR a.archived_at IS NULL)
            GROUP BY a.id
            ORDER BY a.archived_at IS NOT NULL, lower(a.name), a.created_at
            """,
            {"user_id": user_id, "as_of": as_of, "include_archived": include_archived},
        )

        return await cursor.fetchall()

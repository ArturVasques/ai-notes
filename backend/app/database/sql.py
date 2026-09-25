"""
Small SQL composition helpers shared by repositories.

Used by:
- repositories that support partial updates (PATCH).
"""

from collections.abc import Mapping

from psycopg import sql


def set_clause(changes: Mapping[str, object]) -> sql.Composed:
    """
    Build `col_a = %(col_a)s, col_b = %(col_b)s` for a partial update.

    Column names are composed as identifiers, never interpolated as text.
    Callers must pass only columns they explicitly allow.
    """

    if not changes:
        raise ValueError("A partial update needs at least one column")

    return sql.SQL(", ").join(
        sql.SQL("{} = {}").format(sql.Identifier(column), sql.Placeholder(column))
        for column in changes
    )

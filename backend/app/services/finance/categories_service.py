"""
Application service for income and expense categories.

Categories are never deleted: they are archived so historical transactions
keep their classification. Identity always comes from the trusted AppContext.

Used by:
- api/categories.py
- services/users_service.py: default categories on first login.
- future AI agent tools and MCP, through the same functions.
"""

from uuid import UUID, uuid4

from psycopg import AsyncConnection, errors

from app.auth.context import AppContext
from app.auth.permissions import FINANCE_READ, FINANCE_WRITE
from app.core.errors import ConflictError, NotFoundError
from app.database.connection import pool
from app.repositories import category_repository
from app.schemas.category import Category, CategoryCreate, CategoryKind, CategoryUpdate
from app.services.finance.updates import apply_archive_flag, reject_nulls

_DUPLICATE_NAME = "An active category with this name and kind already exists"

# Defaults every new user starts with (name, kind, icon key). They are
# ordinary user-editable categories once created.
DEFAULT_CATEGORIES: tuple[tuple[str, CategoryKind, str], ...] = (
    ("Groceries", CategoryKind.EXPENSE, "shopping-cart"),
    ("Restaurants", CategoryKind.EXPENSE, "utensils"),
    ("Housing", CategoryKind.EXPENSE, "house"),
    ("Transport", CategoryKind.EXPENSE, "bus"),
    ("Car", CategoryKind.EXPENSE, "car"),
    ("Health", CategoryKind.EXPENSE, "heart-pulse"),
    ("Shopping", CategoryKind.EXPENSE, "shopping-bag"),
    ("Entertainment", CategoryKind.EXPENSE, "film"),
    ("Travel", CategoryKind.EXPENSE, "plane"),
    ("Subscriptions", CategoryKind.EXPENSE, "repeat"),
    ("Salary", CategoryKind.INCOME, "briefcase"),
    ("Meal Allowance", CategoryKind.INCOME, "sandwich"),
    ("Benefits", CategoryKind.INCOME, "gift"),
    ("Interest", CategoryKind.INCOME, "percent"),
    ("Dividends", CategoryKind.INCOME, "trending-up"),
    ("Other Income", CategoryKind.INCOME, "circle-plus"),
)


async def provision_default_categories(
    connection: AsyncConnection, *, user_id: UUID
) -> int:
    """
    Create the default categories the user does not have yet.

    A trusted system operation (user provisioning, development seed), not a
    user request, so it takes the user id directly. Idempotent. Returns the
    number of categories created.
    """

    return await category_repository.insert_missing_categories(
        connection,
        user_id=user_id,
        categories=[(name, kind, icon) for name, kind, icon in DEFAULT_CATEGORIES],
    )


async def create_category(context: AppContext, request: CategoryCreate) -> Category:
    """Create a category owned by the authenticated user."""

    context.require_permission(FINANCE_WRITE)

    try:
        async with pool.connection() as connection, connection.transaction():
            return await category_repository.insert_category(
                connection,
                user_id=context.user_id,
                category_id=uuid4(),
                name=request.name,
                kind=request.kind,
                icon=request.icon,
            )
    except errors.UniqueViolation as exc:
        raise ConflictError(_DUPLICATE_NAME) from exc


async def list_categories(
    context: AppContext,
    *,
    kind: CategoryKind | None = None,
    include_archived: bool = False,
) -> list[Category]:
    """List the authenticated user's categories."""

    context.require_permission(FINANCE_READ)

    async with pool.connection() as connection:
        return await category_repository.list_categories(
            connection,
            user_id=context.user_id,
            kind=kind,
            include_archived=include_archived,
        )


async def get_category(context: AppContext, category_id: UUID) -> Category:
    """Return one of the authenticated user's categories."""

    context.require_permission(FINANCE_READ)

    async with pool.connection() as connection:
        category = await category_repository.get_category(
            connection, user_id=context.user_id, category_id=category_id
        )

    if category is None:
        raise NotFoundError("Category not found")

    return category


async def update_category(
    context: AppContext, category_id: UUID, request: CategoryUpdate
) -> Category:
    """Rename, change the icon of, archive or restore a category."""

    context.require_permission(FINANCE_WRITE)

    changes = request.model_dump(exclude_unset=True)
    reject_nulls(changes, ("name", "icon", "archived"))

    try:
        async with pool.connection() as connection, connection.transaction():
            current = await category_repository.get_category(
                connection,
                user_id=context.user_id,
                category_id=category_id,
                for_update=True,
            )

            if current is None:
                raise NotFoundError("Category not found")

            apply_archive_flag(changes, current.archived_at)

            if not changes:
                return current

            updated = await category_repository.update_category(
                connection,
                user_id=context.user_id,
                category_id=category_id,
                changes=changes,
            )
    except errors.UniqueViolation as exc:
        raise ConflictError(_DUPLICATE_NAME) from exc

    assert updated is not None
    return updated

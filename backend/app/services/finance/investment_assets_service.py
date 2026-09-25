"""
Application service for investment assets.

Assets are never deleted: they are archived so historical investments keep
their destination. Identity always comes from the trusted AppContext.

Used by:
- api/investment_assets.py
- future AI agent tools and MCP, through the same functions.
"""

from uuid import UUID, uuid4

from psycopg import errors

from app.auth.context import AppContext
from app.auth.permissions import FINANCE_READ, FINANCE_WRITE
from app.core.errors import ConflictError, NotFoundError
from app.database.connection import pool
from app.repositories import investment_asset_repository
from app.schemas.investment_asset import (
    InvestmentAsset,
    InvestmentAssetCreate,
    InvestmentAssetUpdate,
)
from app.services.finance.updates import apply_archive_flag, reject_nulls

_DUPLICATE_NAME = "An active investment asset with this name already exists"


async def create_investment_asset(
    context: AppContext, request: InvestmentAssetCreate
) -> InvestmentAsset:
    """Create an investment asset owned by the authenticated user."""

    context.require_permission(FINANCE_WRITE)

    try:
        async with pool.connection() as connection, connection.transaction():
            return await investment_asset_repository.insert_investment_asset(
                connection,
                user_id=context.user_id,
                investment_asset_id=uuid4(),
                name=request.name,
                symbol=request.symbol,
                asset_type=request.type,
            )
    except errors.UniqueViolation as exc:
        raise ConflictError(_DUPLICATE_NAME) from exc


async def list_investment_assets(
    context: AppContext, *, include_archived: bool = False
) -> list[InvestmentAsset]:
    """List the authenticated user's investment assets."""

    context.require_permission(FINANCE_READ)

    async with pool.connection() as connection:
        return await investment_asset_repository.list_investment_assets(
            connection, user_id=context.user_id, include_archived=include_archived
        )


async def get_investment_asset(
    context: AppContext, investment_asset_id: UUID
) -> InvestmentAsset:
    """Return one of the authenticated user's investment assets."""

    context.require_permission(FINANCE_READ)

    async with pool.connection() as connection:
        asset = await investment_asset_repository.get_investment_asset(
            connection,
            user_id=context.user_id,
            investment_asset_id=investment_asset_id,
        )

    if asset is None:
        raise NotFoundError("Investment asset not found")

    return asset


async def update_investment_asset(
    context: AppContext,
    investment_asset_id: UUID,
    request: InvestmentAssetUpdate,
) -> InvestmentAsset:
    """Edit, archive or restore one of the authenticated user's assets."""

    context.require_permission(FINANCE_WRITE)

    changes = request.model_dump(exclude_unset=True)
    reject_nulls(changes, ("name", "type", "archived"))

    try:
        async with pool.connection() as connection, connection.transaction():
            current = await investment_asset_repository.get_investment_asset(
                connection,
                user_id=context.user_id,
                investment_asset_id=investment_asset_id,
                for_update=True,
            )

            if current is None:
                raise NotFoundError("Investment asset not found")

            apply_archive_flag(changes, current.archived_at)

            if not changes:
                return current

            updated = await investment_asset_repository.update_investment_asset(
                connection,
                user_id=context.user_id,
                investment_asset_id=investment_asset_id,
                changes=changes,
            )
    except errors.UniqueViolation as exc:
        raise ConflictError(_DUPLICATE_NAME) from exc

    assert updated is not None
    return updated

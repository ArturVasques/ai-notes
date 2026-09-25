"""
HTTP API for income and expense categories.

Identity always comes from AppContext, never from the request. Business
rules live in services/finance/categories_service.py.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.auth.context import AppContext
from app.auth.dependencies import get_app_context
from app.schemas.category import Category, CategoryCreate, CategoryKind, CategoryUpdate
from app.services.finance import categories_service

router = APIRouter(
    prefix="/categories",
    tags=["Categories"],
)


@router.get("", response_model=list[Category])
async def list_categories(
    kind: CategoryKind | None = None,
    include_archived: bool = False,
    context: AppContext = Depends(get_app_context),
) -> list[Category]:
    """List the caller's categories, optionally of one kind."""

    return await categories_service.list_categories(
        context, kind=kind, include_archived=include_archived
    )


@router.post("", response_model=Category, status_code=status.HTTP_201_CREATED)
async def create_category(
    request: CategoryCreate,
    context: AppContext = Depends(get_app_context),
) -> Category:
    """Create a category owned by the caller."""

    return await categories_service.create_category(context, request)


@router.get("/{category_id}", response_model=Category)
async def get_category(
    category_id: UUID,
    context: AppContext = Depends(get_app_context),
) -> Category:
    """Return one of the caller's categories."""

    return await categories_service.get_category(context, category_id)


@router.patch("/{category_id}", response_model=Category)
async def update_category(
    category_id: UUID,
    request: CategoryUpdate,
    context: AppContext = Depends(get_app_context),
) -> Category:
    """Rename, change the icon of, archive or restore a category."""

    return await categories_service.update_category(context, category_id, request)

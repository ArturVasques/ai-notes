"""
HTTP API for investment assets.

Identity always comes from AppContext, never from the request. Business
rules live in services/finance/investment_assets_service.py.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.auth.context import AppContext
from app.auth.dependencies import get_app_context
from app.schemas.investment_asset import (
    InvestmentAsset,
    InvestmentAssetCreate,
    InvestmentAssetUpdate,
)
from app.services.finance import investment_assets_service

router = APIRouter(
    prefix="/investment-assets",
    tags=["Investment assets"],
)


@router.get("", response_model=list[InvestmentAsset])
async def list_investment_assets(
    include_archived: bool = False,
    context: AppContext = Depends(get_app_context),
) -> list[InvestmentAsset]:
    """List the caller's investment assets."""

    return await investment_assets_service.list_investment_assets(
        context, include_archived=include_archived
    )


@router.post("", response_model=InvestmentAsset, status_code=status.HTTP_201_CREATED)
async def create_investment_asset(
    request: InvestmentAssetCreate,
    context: AppContext = Depends(get_app_context),
) -> InvestmentAsset:
    """Create an investment asset owned by the caller."""

    return await investment_assets_service.create_investment_asset(context, request)


@router.get("/{investment_asset_id}", response_model=InvestmentAsset)
async def get_investment_asset(
    investment_asset_id: UUID,
    context: AppContext = Depends(get_app_context),
) -> InvestmentAsset:
    """Return one of the caller's investment assets."""

    return await investment_assets_service.get_investment_asset(
        context, investment_asset_id
    )


@router.patch("/{investment_asset_id}", response_model=InvestmentAsset)
async def update_investment_asset(
    investment_asset_id: UUID,
    request: InvestmentAssetUpdate,
    context: AppContext = Depends(get_app_context),
) -> InvestmentAsset:
    """Edit, archive or restore an investment asset."""

    return await investment_assets_service.update_investment_asset(
        context, investment_asset_id, request
    )

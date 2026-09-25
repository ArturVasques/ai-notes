"""
HTTP and service contracts for investment assets: the destinations of
investments (e.g. "S&P 500" ETF, "Nike" stock). The symbol is optional
because not every investment has a ticker.

Used by:
- api/investment_assets.py
- services/finance/investment_assets_service.py
- repositories/investment_asset_repository.py
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.schemas.common import Name

Symbol = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)
]


class InvestmentAssetType(StrEnum):
    """Small fixed set of investment asset types."""

    ETF = "ETF"
    STOCK = "STOCK"
    FUND = "FUND"
    BOND = "BOND"
    CRYPTO = "CRYPTO"
    OTHER = "OTHER"


class InvestmentAssetCreate(BaseModel):
    """Investment asset submitted by the authenticated user."""

    model_config = ConfigDict(extra="forbid")

    name: Name
    symbol: Symbol | None = None
    type: InvestmentAssetType


class InvestmentAssetUpdate(BaseModel):
    """Partial investment asset update. Only the fields sent are changed."""

    model_config = ConfigDict(extra="forbid")

    name: Name | None = None
    symbol: Symbol | None = None
    type: InvestmentAssetType | None = None
    archived: bool | None = None


class InvestmentAsset(BaseModel):
    """Investment asset returned to the owner."""

    id: UUID
    name: str
    symbol: str | None
    type: InvestmentAssetType
    archived_at: datetime | None
    created_at: datetime

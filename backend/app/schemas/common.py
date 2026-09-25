"""
Shared field types for the finance HTTP contracts.

Money is always an integer number of minor units (cents). Amounts are strict
integers: a JSON float such as 24.8 or 24.0, a numeric string or a boolean is
rejected instead of being coerced, so a client can never send a floating
point amount by accident. See docs/DOMAIN_MODEL.md, decision D2.

Used by:
- app/schemas/account.py, category.py, investment_asset.py, transaction.py.
"""

from typing import Annotated, Literal

from pydantic import Field, StringConstraints

# Upper bound for any single amount: 9 999 999 999.99 in the account
# currency. Far below the BIGINT limit, so sums of many rows stay safe.
MAX_AMOUNT_MINOR = 999_999_999_999

PositiveAmountMinor = Annotated[int, Field(strict=True, gt=0, le=MAX_AMOUNT_MINOR)]

SignedAmountMinor = Annotated[
    int, Field(strict=True, ge=-MAX_AMOUNT_MINOR, le=MAX_AMOUNT_MINOR)
]

Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]

Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]

# Multi-currency is prepared for in the schema (accounts.currency) but v1
# only supports EUR.
Currency = Literal["EUR"]

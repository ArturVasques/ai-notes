"""
Unit tests for the finance request contracts: money, discriminated
transaction kinds, forbidden fields and field formats. No database.
"""

from datetime import date
from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.account import AccountCreate, AccountUpdate
from app.schemas.category import CategoryCreate, CategoryUpdate
from app.schemas.common import MAX_AMOUNT_MINOR
from app.schemas.investment_asset import InvestmentAssetCreate
from app.schemas.transaction import (
    KIND_REFERENCE_FIELDS,
    ExpenseCreate,
    IncomeCreate,
    InvestmentCreate,
    ReimbursementCreate,
    TransactionKind,
    TransactionUpdate,
    TransferCreate,
    transaction_create_adapter,
)


def _expense(**overrides: Any) -> dict[str, Any]:
    return {
        "kind": "EXPENSE",
        "amount_minor": 2480,
        "occurred_on": "2026-09-25",
        "from_account_id": str(uuid4()),
        "category_id": str(uuid4()),
        **overrides,
    }


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (_expense(), ExpenseCreate),
        (
            {
                "kind": "INCOME",
                "amount_minor": 1,
                "occurred_on": "2026-09-25",
                "to_account_id": str(uuid4()),
                "category_id": str(uuid4()),
            },
            IncomeCreate,
        ),
        (
            {
                "kind": "TRANSFER",
                "amount_minor": 1,
                "occurred_on": "2026-09-25",
                "from_account_id": str(uuid4()),
                "to_account_id": str(uuid4()),
            },
            TransferCreate,
        ),
        (
            {
                "kind": "INVESTMENT",
                "amount_minor": 1,
                "occurred_on": "2026-09-25",
                "from_account_id": str(uuid4()),
                "investment_asset_id": str(uuid4()),
            },
            InvestmentCreate,
        ),
        (
            {
                "kind": "REIMBURSEMENT",
                "amount_minor": 1,
                "occurred_on": "2026-09-25",
                "to_account_id": str(uuid4()),
                "reimburses_transaction_id": str(uuid4()),
            },
            ReimbursementCreate,
        ),
    ],
)
def test_kind_selects_the_matching_contract(
    body: dict[str, Any], expected: type
) -> None:
    parsed = transaction_create_adapter.validate_python(body)

    assert isinstance(parsed, expected)
    assert parsed.occurred_on == date(2026, 9, 25)


def test_every_kind_has_reference_fields() -> None:
    assert set(KIND_REFERENCE_FIELDS) == set(TransactionKind)


def test_unknown_kind_is_rejected() -> None:
    with pytest.raises(ValidationError):
        transaction_create_adapter.validate_python(_expense(kind="SAVING"))


@pytest.mark.parametrize("amount", [24.8, 24.0, "2480", True, 0, -1])
def test_amount_must_be_a_strict_positive_integer(amount: object) -> None:
    with pytest.raises(ValidationError):
        transaction_create_adapter.validate_python(_expense(amount_minor=amount))


def test_amount_has_an_upper_bound() -> None:
    transaction_create_adapter.validate_python(_expense(amount_minor=MAX_AMOUNT_MINOR))

    with pytest.raises(ValidationError):
        transaction_create_adapter.validate_python(
            _expense(amount_minor=MAX_AMOUNT_MINOR + 1)
        )


def test_json_amount_is_parsed_as_integer_minor_units() -> None:
    parsed = transaction_create_adapter.validate_json(
        '{"kind": "EXPENSE", "amount_minor": 2480, "occurred_on": "2026-09-25",'
        f' "from_account_id": "{uuid4()}", "category_id": "{uuid4()}"}}'
    )

    assert parsed.amount_minor == 2480


@pytest.mark.parametrize("field", ["user_id", "to_account_id", "investment_asset_id"])
def test_fields_outside_the_kind_are_forbidden(field: str) -> None:
    with pytest.raises(ValidationError):
        transaction_create_adapter.validate_python(_expense(**{field: str(uuid4())}))


def test_missing_required_reference_is_rejected() -> None:
    body = _expense()
    del body["category_id"]

    with pytest.raises(ValidationError):
        transaction_create_adapter.validate_python(body)


def test_transfer_needs_two_different_accounts() -> None:
    account_id = str(uuid4())

    with pytest.raises(ValidationError, match="two different accounts"):
        transaction_create_adapter.validate_python(
            {
                "kind": "TRANSFER",
                "amount_minor": 100,
                "occurred_on": "2026-09-25",
                "from_account_id": account_id,
                "to_account_id": account_id,
            }
        )


def test_description_is_trimmed_and_bounded() -> None:
    parsed = transaction_create_adapter.validate_python(
        _expense(description="  Sushi Yama  ")
    )

    assert parsed.description == "Sushi Yama"

    with pytest.raises(ValidationError):
        transaction_create_adapter.validate_python(_expense(description="x" * 501))


def test_transaction_update_cannot_change_kind_or_owner() -> None:
    with pytest.raises(ValidationError):
        TransactionUpdate.model_validate({"kind": "INCOME"})

    with pytest.raises(ValidationError):
        TransactionUpdate.model_validate({"user_id": str(uuid4())})


def test_account_name_is_trimmed_and_required() -> None:
    account = AccountCreate(name="  Current Account ", type="CHECKING")

    assert account.name == "Current Account"
    assert account.currency == "EUR"

    with pytest.raises(ValidationError):
        AccountCreate(name="   ", type="CHECKING")


def test_account_currency_is_eur_only_in_v1() -> None:
    with pytest.raises(ValidationError):
        AccountCreate.model_validate(
            {"name": "US", "type": "CHECKING", "currency": "USD"}
        )


def test_account_type_must_be_known() -> None:
    with pytest.raises(ValidationError):
        AccountCreate.model_validate({"name": "Card", "type": "CREDIT_CARD"})


def test_opening_balance_may_be_negative_but_is_strict() -> None:
    account = AccountCreate.model_validate(
        {"name": "Overdraft", "type": "CHECKING", "opening_balance_minor": -5_000}
    )

    assert account.opening_balance_minor == -5_000

    with pytest.raises(ValidationError):
        AccountCreate.model_validate(
            {"name": "Float", "type": "CHECKING", "opening_balance_minor": 10.5}
        )


def test_account_update_cannot_change_currency() -> None:
    with pytest.raises(ValidationError):
        AccountUpdate.model_validate({"currency": "EUR"})


@pytest.mark.parametrize("icon", ["utensils", "shopping-cart", "heart-pulse", "a1"])
def test_valid_icon_keys_are_accepted(icon: str) -> None:
    CategoryCreate.model_validate({"name": "Food", "kind": "EXPENSE", "icon": icon})


@pytest.mark.parametrize(
    "icon",
    ["", "Utensils", "<svg onload=alert(1)>", "shopping cart", "x" * 41, "a_b"],
)
def test_invalid_icon_keys_are_rejected(icon: str) -> None:
    with pytest.raises(ValidationError):
        CategoryCreate.model_validate({"name": "Food", "kind": "EXPENSE", "icon": icon})


def test_category_update_cannot_change_kind() -> None:
    with pytest.raises(ValidationError):
        CategoryUpdate.model_validate({"kind": "INCOME"})


def test_investment_asset_symbol_is_optional() -> None:
    asset = InvestmentAssetCreate.model_validate({"name": "Pension", "type": "FUND"})

    assert asset.symbol is None

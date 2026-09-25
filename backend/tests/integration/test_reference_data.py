"""
Integration tests for accounts, categories and investment assets:
create, list, update, archive/restore, default categories, duplicate names
and isolation between users.
"""

import pytest

from app.auth.context import AppContext
from app.core.errors import ConflictError, NotFoundError
from app.database.connection import pool
from app.schemas.account import AccountType, AccountUpdate
from app.schemas.category import CategoryKind, CategoryUpdate
from app.schemas.investment_asset import InvestmentAssetType, InvestmentAssetUpdate
from app.services.finance import (
    accounts_service,
    categories_service,
    investment_assets_service,
)
from app.services.finance.categories_service import (
    DEFAULT_CATEGORIES,
    provision_default_categories,
)
from tests.integration import factories

# --- Accounts ---------------------------------------------------------------


async def test_account_is_created_with_defaults(user: AppContext) -> None:
    account = await factories.account(user, "Meal Card", AccountType.BENEFITS)

    assert account.name == "Meal Card"
    assert account.type is AccountType.BENEFITS
    assert account.currency == "EUR"
    assert account.opening_balance_minor == 0
    assert account.archived_at is None


async def test_account_can_be_edited(user: AppContext) -> None:
    account = await factories.account(user)

    updated = await accounts_service.update_account(
        user,
        account.id,
        AccountUpdate(
            name="Main Account",
            description="Salary account",
            opening_balance_minor=-1_500,
        ),
    )

    assert updated.name == "Main Account"
    assert updated.description == "Salary account"
    assert updated.opening_balance_minor == -1_500
    assert updated.type is AccountType.CHECKING


async def test_archived_account_is_hidden_by_default_and_can_be_restored(
    user: AppContext,
) -> None:
    active = await factories.account(user, "Current")
    archived = await factories.account(user, "Old Bank")

    archived_row = await accounts_service.update_account(
        user, archived.id, AccountUpdate(archived=True)
    )
    again = await accounts_service.update_account(
        user, archived.id, AccountUpdate(archived=True)
    )

    assert archived_row.archived_at is not None
    assert again.archived_at == archived_row.archived_at

    visible = await accounts_service.list_accounts(user)
    everything = await accounts_service.list_accounts(user, include_archived=True)

    assert [a.id for a in visible] == [active.id]
    assert {a.id for a in everything} == {active.id, archived.id}

    restored = await accounts_service.update_account(
        user, archived.id, AccountUpdate(archived=False)
    )

    assert restored.archived_at is None


async def test_active_account_names_are_unique_case_insensitively(
    user: AppContext,
) -> None:
    first = await factories.account(user, "Savings")

    with pytest.raises(ConflictError):
        await factories.account(user, "savings")

    await accounts_service.update_account(user, first.id, AccountUpdate(archived=True))

    # Once archived, the name is free again; restoring the old one conflicts.
    await factories.account(user, "SAVINGS")

    with pytest.raises(ConflictError):
        await accounts_service.update_account(
            user, first.id, AccountUpdate(archived=False)
        )


async def test_required_account_fields_cannot_be_nulled(user: AppContext) -> None:
    account = await factories.account(user)

    with pytest.raises(ValueError, match="'name' cannot be null"):
        await accounts_service.update_account(
            user, account.id, AccountUpdate(name=None)
        )


async def test_accounts_are_isolated_between_users(
    user: AppContext, other_user: AppContext
) -> None:
    own = await factories.account(user, "Mine")
    await factories.account(other_user, "Theirs")

    assert [a.id for a in await accounts_service.list_accounts(user)] == [own.id]

    with pytest.raises(NotFoundError):
        await accounts_service.get_account(other_user, own.id)

    with pytest.raises(NotFoundError):
        await accounts_service.update_account(
            other_user, own.id, AccountUpdate(name="Hijacked")
        )

    assert (await accounts_service.get_account(user, own.id)).name == "Mine"


async def test_same_account_name_is_allowed_for_different_users(
    user: AppContext, other_user: AppContext
) -> None:
    await factories.account(user, "Cash", AccountType.CASH)
    await factories.account(other_user, "Cash", AccountType.CASH)


# --- Categories -------------------------------------------------------------


async def test_default_categories_are_provisioned_once(user: AppContext) -> None:
    async with pool.connection() as connection, connection.transaction():
        first = await provision_default_categories(connection, user_id=user.user_id)
        second = await provision_default_categories(connection, user_id=user.user_id)

    categories = await categories_service.list_categories(user)

    assert first == len(DEFAULT_CATEGORIES)
    assert second == 0
    assert {(c.name, c.kind, c.icon) for c in categories} == set(DEFAULT_CATEGORIES)


async def test_provisioning_keeps_a_renamed_or_existing_category(
    user: AppContext,
) -> None:
    existing = await factories.category(user, "restaurants", icon="pizza")

    async with pool.connection() as connection, connection.transaction():
        created = await provision_default_categories(connection, user_id=user.user_id)

    restaurants = [
        c
        for c in await categories_service.list_categories(user)
        if c.name.lower() == "restaurants"
    ]

    assert created == len(DEFAULT_CATEGORIES) - 1
    assert [c.id for c in restaurants] == [existing.id]
    assert restaurants[0].icon == "pizza"


async def test_categories_can_be_filtered_by_kind(user: AppContext) -> None:
    expense = await factories.category(user, "Groceries", CategoryKind.EXPENSE)
    income = await factories.category(user, "Salary", CategoryKind.INCOME, "briefcase")

    expenses = await categories_service.list_categories(user, kind=CategoryKind.EXPENSE)
    incomes = await categories_service.list_categories(user, kind=CategoryKind.INCOME)

    assert [c.id for c in expenses] == [expense.id]
    assert [c.id for c in incomes] == [income.id]


async def test_same_name_is_allowed_for_different_kinds(user: AppContext) -> None:
    await factories.category(user, "Other", CategoryKind.EXPENSE, "circle")
    await factories.category(user, "Other", CategoryKind.INCOME, "circle")

    with pytest.raises(ConflictError):
        await factories.category(user, "OTHER", CategoryKind.INCOME, "circle")


async def test_category_can_be_renamed_reiconed_and_archived(user: AppContext) -> None:
    category = await factories.category(user)

    updated = await categories_service.update_category(
        user,
        category.id,
        CategoryUpdate(name="Eating Out", icon="pizza", archived=True),
    )

    assert updated.name == "Eating Out"
    assert updated.icon == "pizza"
    assert updated.kind is CategoryKind.EXPENSE
    assert updated.archived_at is not None
    assert await categories_service.list_categories(user) == []


async def test_categories_are_isolated_between_users(
    user: AppContext, other_user: AppContext
) -> None:
    own = await factories.category(user)

    assert await categories_service.list_categories(other_user) == []

    with pytest.raises(NotFoundError):
        await categories_service.get_category(other_user, own.id)

    with pytest.raises(NotFoundError):
        await categories_service.update_category(
            other_user, own.id, CategoryUpdate(archived=True)
        )


# --- Investment assets ------------------------------------------------------


async def test_investment_asset_symbol_is_optional(user: AppContext) -> None:
    fund = await factories.asset(user, "Pension Fund", None, InvestmentAssetType.FUND)
    stock = await factories.asset(user, "Nike", "NKE", InvestmentAssetType.STOCK)

    assert fund.symbol is None
    assert stock.symbol == "NKE"
    assert stock.type is InvestmentAssetType.STOCK


async def test_investment_asset_can_be_edited_and_archived(user: AppContext) -> None:
    asset = await factories.asset(user, "MSCI World")

    updated = await investment_assets_service.update_investment_asset(
        user,
        asset.id,
        InvestmentAssetUpdate(symbol="IWDA", archived=True),
    )

    assert updated.symbol == "IWDA"
    assert updated.archived_at is not None
    assert await investment_assets_service.list_investment_assets(user) == []

    cleared = await investment_assets_service.update_investment_asset(
        user, asset.id, InvestmentAssetUpdate(symbol=None)
    )

    assert cleared.symbol is None


async def test_duplicate_active_asset_name_conflicts(user: AppContext) -> None:
    await factories.asset(user, "S&P 500")

    with pytest.raises(ConflictError):
        await factories.asset(user, "s&p 500")


async def test_investment_assets_are_isolated_between_users(
    user: AppContext, other_user: AppContext
) -> None:
    own = await factories.asset(user)

    assert await investment_assets_service.list_investment_assets(other_user) == []

    with pytest.raises(NotFoundError):
        await investment_assets_service.get_investment_asset(other_user, own.id)

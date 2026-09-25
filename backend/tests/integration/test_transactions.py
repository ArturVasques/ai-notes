"""
Integration tests for the five transaction kinds and the reference rules
enforced by the transactions service (everything except reimbursement
amounts, which live in test_reimbursements.py).
"""

from datetime import date

import pytest
from pydantic import ValidationError

from app.auth.context import AppContext
from app.core.errors import NotFoundError
from app.database.connection import pool
from app.schemas.account import AccountType, AccountUpdate
from app.schemas.category import CategoryKind, CategoryUpdate
from app.schemas.investment_asset import InvestmentAssetUpdate
from app.schemas.transaction import TransactionKind, TransactionUpdate
from app.services.finance import (
    accounts_service,
    categories_service,
    investment_assets_service,
    transactions_service,
)
from tests.integration import factories


async def test_income_is_stored_with_its_shape(user: AppContext) -> None:
    account = await factories.account(user)
    salary = await factories.category(user, "Salary", CategoryKind.INCOME, "briefcase")

    income = await factories.transaction(
        user,
        kind="INCOME",
        amount_minor=300_000,
        to_account_id=account.id,
        category_id=salary.id,
        description="September salary",
    )

    assert income.kind is TransactionKind.INCOME
    assert income.amount_minor == 300_000
    assert income.to_account_id == account.id
    assert income.from_account_id is None
    assert income.category_id == salary.id
    assert income.description == "September salary"
    assert income.reimbursed_amount_minor == 0


async def test_expense_is_stored_with_its_shape(user: AppContext) -> None:
    account = await factories.account(user)
    category = await factories.category(user)

    expense = await factories.expense(
        user, from_account_id=account.id, category_id=category.id, amount_minor=2_480
    )

    assert expense.kind is TransactionKind.EXPENSE
    assert expense.amount_minor == 2_480
    assert expense.from_account_id == account.id
    assert expense.to_account_id is None
    assert expense.occurred_on == factories.DAY


async def test_transfer_is_one_row_with_both_accounts(user: AppContext) -> None:
    current = await factories.account(user, "Current")
    savings = await factories.account(user, "Savings", AccountType.SAVINGS)

    transfer = await factories.transaction(
        user,
        kind="TRANSFER",
        amount_minor=50_000,
        from_account_id=current.id,
        to_account_id=savings.id,
    )

    async with pool.connection() as connection, connection.cursor() as cursor:
        await cursor.execute(
            "SELECT COUNT(*) FROM transactions WHERE user_id = %s", (user.user_id,)
        )
        row = await cursor.fetchone()

    assert row == (1,)
    assert transfer.from_account_id == current.id
    assert transfer.to_account_id == savings.id
    assert transfer.category_id is None


async def test_investment_goes_from_an_account_to_an_asset(user: AppContext) -> None:
    broker = await factories.account(user, "Broker", AccountType.BROKERAGE)
    sp500 = await factories.asset(user, "S&P 500")

    investment = await factories.transaction(
        user,
        kind="INVESTMENT",
        amount_minor=30_000,
        from_account_id=broker.id,
        investment_asset_id=sp500.id,
    )

    assert investment.kind is TransactionKind.INVESTMENT
    assert investment.investment_asset_id == sp500.id
    assert investment.to_account_id is None


async def test_expense_needs_an_expense_category(user: AppContext) -> None:
    account = await factories.account(user)
    salary = await factories.category(user, "Salary", CategoryKind.INCOME, "briefcase")

    with pytest.raises(ValueError, match="category of kind EXPENSE"):
        await factories.expense(user, from_account_id=account.id, category_id=salary.id)


async def test_income_needs_an_income_category(user: AppContext) -> None:
    account = await factories.account(user)
    food = await factories.category(user)

    with pytest.raises(ValueError, match="category of kind INCOME"):
        await factories.transaction(
            user,
            kind="INCOME",
            amount_minor=100,
            to_account_id=account.id,
            category_id=food.id,
        )


async def test_another_users_references_are_rejected(
    user: AppContext, other_user: AppContext
) -> None:
    own_account = await factories.account(user)
    own_category = await factories.category(user)
    foreign_account = await factories.account(other_user)
    foreign_category = await factories.category(other_user)
    foreign_asset = await factories.asset(other_user)

    with pytest.raises(ValueError, match="from_account_id does not reference"):
        await factories.expense(
            user, from_account_id=foreign_account.id, category_id=own_category.id
        )

    with pytest.raises(ValueError, match="category_id does not reference"):
        await factories.expense(
            user, from_account_id=own_account.id, category_id=foreign_category.id
        )

    with pytest.raises(ValueError, match="investment_asset_id does not reference"):
        await factories.transaction(
            user,
            kind="INVESTMENT",
            amount_minor=100,
            from_account_id=own_account.id,
            investment_asset_id=foreign_asset.id,
        )


async def test_archived_references_cannot_be_used_in_new_transactions(
    user: AppContext,
) -> None:
    account = await factories.account(user)
    archived_account = await factories.account(user, "Closed")
    category = await factories.category(user)
    archived_category = await factories.category(user, "Old", icon="archive")
    archived_asset = await factories.asset(user)

    await accounts_service.update_account(
        user, archived_account.id, AccountUpdate(archived=True)
    )
    await categories_service.update_category(
        user, archived_category.id, CategoryUpdate(archived=True)
    )
    await investment_assets_service.update_investment_asset(
        user, archived_asset.id, InvestmentAssetUpdate(archived=True)
    )

    with pytest.raises(ValueError, match="archived account"):
        await factories.expense(
            user, from_account_id=archived_account.id, category_id=category.id
        )

    with pytest.raises(ValueError, match="archived category"):
        await factories.expense(
            user, from_account_id=account.id, category_id=archived_category.id
        )

    with pytest.raises(ValueError, match="archived asset"):
        await factories.transaction(
            user,
            kind="INVESTMENT",
            amount_minor=100,
            from_account_id=account.id,
            investment_asset_id=archived_asset.id,
        )


async def test_existing_transactions_keep_archived_references(
    user: AppContext,
) -> None:
    account = await factories.account(user)
    category = await factories.category(user)
    expense = await factories.expense(
        user, from_account_id=account.id, category_id=category.id
    )

    await accounts_service.update_account(
        user, account.id, AccountUpdate(archived=True)
    )
    await categories_service.update_category(
        user, category.id, CategoryUpdate(archived=True)
    )

    # History is untouched and an unrelated edit is still allowed.
    updated = await transactions_service.update_transaction(
        user, expense.id, TransactionUpdate(description="Dinner")
    )

    assert updated.from_account_id == account.id
    assert updated.category_id == category.id
    assert updated.description == "Dinner"


async def test_transfer_needs_accounts_with_the_same_currency(
    user: AppContext,
) -> None:
    euro = await factories.account(user, "Euro")
    dollar = await factories.account(user, "Dollar")

    # The API only accepts EUR today; simulate a future multi-currency row.
    async with pool.connection() as connection, connection.transaction():
        await connection.execute(
            "UPDATE accounts SET currency = 'USD' WHERE id = %s", (dollar.id,)
        )

    with pytest.raises(ValueError, match="same currency"):
        await factories.transaction(
            user,
            kind="TRANSFER",
            amount_minor=100,
            from_account_id=euro.id,
            to_account_id=dollar.id,
        )


async def test_transaction_can_be_edited_within_its_kind(user: AppContext) -> None:
    current = await factories.account(user, "Current")
    card = await factories.account(user, "Meal Card", AccountType.BENEFITS)
    food = await factories.category(user)
    groceries = await factories.category(user, "Groceries", icon="shopping-cart")
    expense = await factories.expense(
        user, from_account_id=current.id, category_id=food.id
    )

    updated = await transactions_service.update_transaction(
        user,
        expense.id,
        TransactionUpdate(
            amount_minor=6_342,
            occurred_on=date(2026, 9, 11),
            from_account_id=card.id,
            category_id=groceries.id,
        ),
    )

    assert updated.kind is TransactionKind.EXPENSE
    assert updated.amount_minor == 6_342
    assert updated.occurred_on == date(2026, 9, 11)
    assert updated.from_account_id == card.id
    assert updated.category_id == groceries.id
    assert updated.updated_at > expense.updated_at


async def test_edit_cannot_add_a_reference_the_kind_does_not_use(
    user: AppContext,
) -> None:
    account = await factories.account(user)
    other = await factories.account(user, "Other")
    category = await factories.category(user)
    expense = await factories.expense(
        user, from_account_id=account.id, category_id=category.id
    )

    with pytest.raises(ValueError, match="to_account_id"):
        await transactions_service.update_transaction(
            user, expense.id, TransactionUpdate(to_account_id=other.id)
        )

    with pytest.raises(ValueError, match="category_id"):
        await transactions_service.update_transaction(
            user, expense.id, TransactionUpdate(category_id=None)
        )


async def test_edit_revalidates_references(user: AppContext) -> None:
    account = await factories.account(user)
    category = await factories.category(user)
    salary = await factories.category(user, "Salary", CategoryKind.INCOME, "briefcase")
    expense = await factories.expense(
        user, from_account_id=account.id, category_id=category.id
    )

    with pytest.raises(ValueError, match="category of kind EXPENSE"):
        await transactions_service.update_transaction(
            user, expense.id, TransactionUpdate(category_id=salary.id)
        )


async def test_kind_cannot_be_changed() -> None:
    with pytest.raises(ValidationError):
        TransactionUpdate.model_validate({"kind": "INCOME"})


async def test_transaction_can_be_deleted(user: AppContext) -> None:
    account = await factories.account(user)
    category = await factories.category(user)
    expense = await factories.expense(
        user, from_account_id=account.id, category_id=category.id
    )

    await transactions_service.delete_transaction(user, expense.id)

    with pytest.raises(NotFoundError):
        await transactions_service.get_transaction(user, expense.id)


async def test_transactions_are_isolated_between_users(
    user: AppContext, other_user: AppContext
) -> None:
    account = await factories.account(user)
    category = await factories.category(user)
    expense = await factories.expense(
        user, from_account_id=account.id, category_id=category.id
    )

    with pytest.raises(NotFoundError):
        await transactions_service.get_transaction(other_user, expense.id)

    with pytest.raises(NotFoundError):
        await transactions_service.update_transaction(
            other_user, expense.id, TransactionUpdate(amount_minor=1)
        )

    with pytest.raises(NotFoundError):
        await transactions_service.delete_transaction(other_user, expense.id)

    unchanged = await transactions_service.get_transaction(user, expense.id)

    assert unchanged.amount_minor == expense.amount_minor

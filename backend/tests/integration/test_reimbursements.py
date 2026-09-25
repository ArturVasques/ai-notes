"""
Integration tests for reimbursements (docs/DOMAIN_MODEL.md, D3):

- a reimbursement repays an EXPENSE of the same user and keeps its own date;
- the reimbursements of an expense never exceed it, including under
  concurrent requests;
- an expense cannot shrink below, move after, or be deleted while it has
  reimbursements.
"""

import asyncio
from datetime import date
from uuid import UUID

import pytest

from app.auth.context import AppContext
from app.core.errors import ConflictError
from app.schemas.category import CategoryKind
from app.schemas.transaction import TransactionKind, TransactionUpdate
from app.services.finance import transactions_service
from tests.integration import factories


async def _expense(
    context: AppContext, amount_minor: int = 10_000
) -> tuple[UUID, UUID]:
    """Create an account and a restaurant expense; return their ids."""

    account = await factories.account(context)
    category = await factories.category(context)
    expense = await factories.expense(
        context,
        from_account_id=account.id,
        category_id=category.id,
        amount_minor=amount_minor,
    )

    return account.id, expense.id


async def test_shared_bill_is_partially_reimbursed(user: AppContext) -> None:
    account_id, expense_id = await _expense(user)

    reimbursement = await factories.reimbursement(
        user,
        to_account_id=account_id,
        expense_id=expense_id,
        amount_minor=5_000,
        occurred_on=date(2026, 10, 3),
    )
    expense = await transactions_service.get_transaction(user, expense_id)

    assert reimbursement.kind is TransactionKind.REIMBURSEMENT
    assert reimbursement.reimburses_transaction_id == expense_id
    assert reimbursement.category_id is None
    # D3: the reimbursement keeps the real date it arrived.
    assert reimbursement.occurred_on == date(2026, 10, 3)
    assert expense.reimbursed_amount_minor == 5_000


async def test_reimbursements_cannot_exceed_the_expense(user: AppContext) -> None:
    account_id, expense_id = await _expense(user)

    await factories.reimbursement(
        user, to_account_id=account_id, expense_id=expense_id, amount_minor=5_000
    )
    await factories.reimbursement(
        user, to_account_id=account_id, expense_id=expense_id, amount_minor=5_000
    )

    with pytest.raises(ValueError, match="cannot exceed the expense: 0"):
        await factories.reimbursement(
            user, to_account_id=account_id, expense_id=expense_id, amount_minor=1
        )

    expense = await transactions_service.get_transaction(user, expense_id)

    assert expense.reimbursed_amount_minor == 10_000


async def test_single_reimbursement_larger_than_the_expense_is_rejected(
    user: AppContext,
) -> None:
    account_id, expense_id = await _expense(user)

    with pytest.raises(ValueError, match="10000 minor units left"):
        await factories.reimbursement(
            user, to_account_id=account_id, expense_id=expense_id, amount_minor=10_001
        )


async def test_concurrent_reimbursements_cannot_exceed_the_expense(
    user: AppContext,
) -> None:
    account_id, expense_id = await _expense(user)

    results = await asyncio.gather(
        *(
            factories.reimbursement(
                user,
                to_account_id=account_id,
                expense_id=expense_id,
                amount_minor=6_000,
            )
            for _ in range(4)
        ),
        return_exceptions=True,
    )

    succeeded = [r for r in results if not isinstance(r, BaseException)]
    rejected = [r for r in results if isinstance(r, ValueError)]
    expense = await transactions_service.get_transaction(user, expense_id)

    assert len(succeeded) == 1
    assert len(rejected) == 3
    assert expense.reimbursed_amount_minor == 6_000


async def test_only_an_expense_can_be_reimbursed(user: AppContext) -> None:
    account = await factories.account(user)
    salary = await factories.category(user, "Salary", CategoryKind.INCOME, "briefcase")
    income = await factories.transaction(
        user,
        kind="INCOME",
        amount_minor=100_000,
        to_account_id=account.id,
        category_id=salary.id,
    )

    with pytest.raises(ValueError, match="Only an expense"):
        await factories.reimbursement(
            user, to_account_id=account.id, expense_id=income.id, amount_minor=100
        )


async def test_another_users_expense_cannot_be_reimbursed(
    user: AppContext, other_user: AppContext
) -> None:
    _, foreign_expense_id = await _expense(other_user)
    own_account = await factories.account(user)

    with pytest.raises(
        ValueError, match="reimburses_transaction_id does not reference"
    ):
        await factories.reimbursement(
            user,
            to_account_id=own_account.id,
            expense_id=foreign_expense_id,
            amount_minor=100,
        )

    foreign = await transactions_service.get_transaction(other_user, foreign_expense_id)

    assert foreign.reimbursed_amount_minor == 0


async def test_reimbursement_cannot_be_dated_before_its_expense(
    user: AppContext,
) -> None:
    account_id, expense_id = await _expense(user)

    with pytest.raises(ValueError, match="before its expense"):
        await factories.reimbursement(
            user,
            to_account_id=account_id,
            expense_id=expense_id,
            amount_minor=100,
            occurred_on=date(2026, 9, 9),
        )


async def test_reimbursement_can_arrive_in_another_account(user: AppContext) -> None:
    card_account_id, expense_id = await _expense(user)
    savings = await factories.account(user, "Savings")

    reimbursement = await factories.reimbursement(
        user, to_account_id=savings.id, expense_id=expense_id, amount_minor=2_000
    )

    assert reimbursement.to_account_id == savings.id
    assert reimbursement.to_account_id != card_account_id


async def test_editing_a_reimbursement_rechecks_the_cap_without_counting_itself(
    user: AppContext,
) -> None:
    account_id, expense_id = await _expense(user)
    first = await factories.reimbursement(
        user, to_account_id=account_id, expense_id=expense_id, amount_minor=4_000
    )
    await factories.reimbursement(
        user, to_account_id=account_id, expense_id=expense_id, amount_minor=5_000
    )

    raised = await transactions_service.update_transaction(
        user, first.id, TransactionUpdate(amount_minor=5_000)
    )

    assert raised.amount_minor == 5_000

    with pytest.raises(ValueError, match="cannot exceed the expense"):
        await transactions_service.update_transaction(
            user, first.id, TransactionUpdate(amount_minor=5_001)
        )


async def test_reimbursement_can_be_moved_to_another_expense_within_its_cap(
    user: AppContext,
) -> None:
    account_id, big_expense_id = await _expense(user, 10_000)
    category = await factories.category(user, "Groceries", icon="shopping-cart")
    small_expense = await factories.expense(
        user, from_account_id=account_id, category_id=category.id, amount_minor=1_000
    )
    reimbursement = await factories.reimbursement(
        user, to_account_id=account_id, expense_id=big_expense_id, amount_minor=3_000
    )

    with pytest.raises(ValueError, match="1000 minor units left"):
        await transactions_service.update_transaction(
            user,
            reimbursement.id,
            TransactionUpdate(reimburses_transaction_id=small_expense.id),
        )

    moved = await transactions_service.update_transaction(
        user,
        reimbursement.id,
        TransactionUpdate(
            reimburses_transaction_id=small_expense.id, amount_minor=1_000
        ),
    )

    assert moved.reimburses_transaction_id == small_expense.id
    big = await transactions_service.get_transaction(user, big_expense_id)
    assert big.reimbursed_amount_minor == 0


async def test_expense_cannot_shrink_below_its_reimbursements(
    user: AppContext,
) -> None:
    account_id, expense_id = await _expense(user)
    await factories.reimbursement(
        user, to_account_id=account_id, expense_id=expense_id, amount_minor=5_000
    )

    with pytest.raises(ValueError, match="already reimbursed"):
        await transactions_service.update_transaction(
            user, expense_id, TransactionUpdate(amount_minor=4_999)
        )

    shrunk = await transactions_service.update_transaction(
        user, expense_id, TransactionUpdate(amount_minor=5_000)
    )

    assert shrunk.amount_minor == 5_000


async def test_expense_cannot_move_after_its_reimbursements(user: AppContext) -> None:
    account_id, expense_id = await _expense(user)
    await factories.reimbursement(
        user,
        to_account_id=account_id,
        expense_id=expense_id,
        amount_minor=100,
        occurred_on=date(2026, 9, 15),
    )

    with pytest.raises(ValueError, match="dated after its reimbursements"):
        await transactions_service.update_transaction(
            user, expense_id, TransactionUpdate(occurred_on=date(2026, 9, 16))
        )


async def test_expense_with_reimbursements_cannot_be_deleted(user: AppContext) -> None:
    account_id, expense_id = await _expense(user)
    reimbursement = await factories.reimbursement(
        user, to_account_id=account_id, expense_id=expense_id, amount_minor=100
    )

    with pytest.raises(ConflictError):
        await transactions_service.delete_transaction(user, expense_id)

    await transactions_service.delete_transaction(user, reimbursement.id)
    await transactions_service.delete_transaction(user, expense_id)

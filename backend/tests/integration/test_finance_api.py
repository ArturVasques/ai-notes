"""
End-to-end HTTP tests for the finance endpoints against the real database.

The application is called in-process through httpx's ASGI transport with
the session database pool already open (the lifespan is not run). Identity
comes from the development authentication boundary exactly as in local
development: the `X-User-Id` header with APP_ENV=development.
"""

from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import app.auth.dependencies as dependencies
from app.auth.context import AppContext
from app.core.config import AppEnv, AppSettings
from main import app


@pytest_asyncio.fixture
async def client(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[AsyncClient]:
    development = AppSettings(app_env=AppEnv.DEVELOPMENT, postgres_password="unused")
    monkeypatch.setattr(dependencies, "settings", development)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http:
        yield http


def _as(context: AppContext) -> dict[str, str]:
    return {"X-User-Id": str(context.user_id)}


async def _post(
    client: AsyncClient, context: AppContext, path: str, body: dict[str, Any]
) -> dict[str, Any]:
    response = await client.post(path, json=body, headers=_as(context))

    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


async def test_quick_add_expense_flow(client: AsyncClient, user: AppContext) -> None:
    account = await _post(
        client, user, "/accounts", {"name": "Meal Card", "type": "BENEFITS"}
    )
    category = await _post(
        client,
        user,
        "/categories",
        {"name": "Restaurants", "kind": "EXPENSE", "icon": "utensils"},
    )

    expense = await _post(
        client,
        user,
        "/transactions",
        {
            "kind": "EXPENSE",
            "amount_minor": 2480,
            "occurred_on": "2026-09-25",
            "from_account_id": account["id"],
            "category_id": category["id"],
            "description": "Sushi Yama",
        },
    )

    listed = await client.get("/transactions", headers=_as(user))

    assert expense["amount_minor"] == 2480
    assert expense["kind"] == "EXPENSE"
    assert "user_id" not in expense
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [expense["id"]]
    assert listed.json()["next_cursor"] is None


async def test_body_cannot_choose_the_owner(
    client: AsyncClient, user: AppContext, other_user: AppContext
) -> None:
    response = await client.post(
        "/accounts",
        json={"name": "Sneaky", "type": "CASH", "user_id": str(other_user.user_id)},
        headers=_as(user),
    )

    assert response.status_code == 422


@pytest.mark.parametrize("amount", [24.8, 24.0, "2480", 0, -100, True])
async def test_non_integer_or_non_positive_amounts_are_rejected(
    client: AsyncClient, user: AppContext, amount: object
) -> None:
    account = await _post(client, user, "/accounts", {"name": "Cash", "type": "CASH"})
    category = await _post(
        client,
        user,
        "/categories",
        {"name": "Food", "kind": "EXPENSE", "icon": "utensils"},
    )

    response = await client.post(
        "/transactions",
        json={
            "kind": "EXPENSE",
            "amount_minor": amount,
            "occurred_on": "2026-09-25",
            "from_account_id": account["id"],
            "category_id": category["id"],
        },
        headers=_as(user),
    )

    assert response.status_code == 422


async def test_business_rule_violation_returns_400(
    client: AsyncClient, user: AppContext
) -> None:
    account = await _post(client, user, "/accounts", {"name": "Cash", "type": "CASH"})
    salary = await _post(
        client,
        user,
        "/categories",
        {"name": "Salary", "kind": "INCOME", "icon": "briefcase"},
    )

    response = await client.post(
        "/transactions",
        json={
            "kind": "EXPENSE",
            "amount_minor": 100,
            "occurred_on": "2026-09-25",
            "from_account_id": account["id"],
            "category_id": salary["id"],
        },
        headers=_as(user),
    )

    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_other_users_resources_answer_404(
    client: AsyncClient, user: AppContext, other_user: AppContext
) -> None:
    account = await _post(client, user, "/accounts", {"name": "Mine", "type": "CASH"})

    read = await client.get(f"/accounts/{account['id']}", headers=_as(other_user))
    patch = await client.patch(
        f"/accounts/{account['id']}",
        json={"archived": True},
        headers=_as(other_user),
    )

    assert read.status_code == 404
    assert read.json()["code"] == "NOT_FOUND"
    assert patch.status_code == 404


async def test_duplicate_name_answers_409(
    client: AsyncClient, user: AppContext
) -> None:
    await _post(client, user, "/accounts", {"name": "Savings", "type": "SAVINGS"})

    response = await client.post(
        "/accounts", json={"name": "savings", "type": "SAVINGS"}, headers=_as(user)
    )

    assert response.status_code == 409
    assert response.json()["code"] == "CONFLICT"


async def test_transaction_lifecycle_over_http(
    client: AsyncClient, user: AppContext
) -> None:
    account = await _post(client, user, "/accounts", {"name": "Cash", "type": "CASH"})
    category = await _post(
        client,
        user,
        "/categories",
        {"name": "Food", "kind": "EXPENSE", "icon": "utensils"},
    )
    expense = await _post(
        client,
        user,
        "/transactions",
        {
            "kind": "EXPENSE",
            "amount_minor": 10000,
            "occurred_on": "2026-09-10",
            "from_account_id": account["id"],
            "category_id": category["id"],
        },
    )
    reimbursement = await _post(
        client,
        user,
        "/transactions",
        {
            "kind": "REIMBURSEMENT",
            "amount_minor": 5000,
            "occurred_on": "2026-09-12",
            "to_account_id": account["id"],
            "reimburses_transaction_id": expense["id"],
        },
    )

    blocked = await client.delete(f"/transactions/{expense['id']}", headers=_as(user))
    change_kind = await client.patch(
        f"/transactions/{expense['id']}", json={"kind": "INCOME"}, headers=_as(user)
    )
    edited = await client.patch(
        f"/transactions/{expense['id']}",
        json={"description": "Team dinner"},
        headers=_as(user),
    )
    removed = await client.delete(
        f"/transactions/{reimbursement['id']}", headers=_as(user)
    )
    removed_expense = await client.delete(
        f"/transactions/{expense['id']}", headers=_as(user)
    )

    assert blocked.status_code == 409
    assert change_kind.status_code == 422
    assert edited.status_code == 200
    assert edited.json()["description"] == "Team dinner"
    assert edited.json()["reimbursed_amount_minor"] == 5000
    assert removed.status_code == 204
    assert removed_expense.status_code == 204


async def test_history_query_parameters(client: AsyncClient, user: AppContext) -> None:
    reversed_period = await client.get(
        "/transactions",
        params={"from": "2026-09-30", "to": "2026-09-01"},
        headers=_as(user),
    )
    too_large = await client.get(
        "/transactions", params={"limit": 201}, headers=_as(user)
    )
    bad_cursor = await client.get(
        "/transactions", params={"cursor": "garbage"}, headers=_as(user)
    )

    assert reversed_period.status_code == 400
    assert too_large.status_code == 422
    assert bad_cursor.status_code == 400


async def test_requests_without_identity_are_rejected(client: AsyncClient) -> None:
    response = await client.get("/accounts")

    assert response.status_code == 401

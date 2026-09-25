"""
End-to-end HTTP tests for the finance endpoints against the real database.

The application is called in-process through httpx's ASGI transport with
the session database pool already open (the lifespan is not run). The
authentication dependency is replaced with `app.dependency_overrides`, so
the tests choose which trusted AppContext a request runs as without any
identity provider. Only the last test exercises the real boundary.
"""

from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.auth.context import AppContext
from app.auth.dependencies import get_app_context
from main import app


class Api:
    """Thin wrapper choosing the authenticated user of the next requests."""

    def __init__(self, http: AsyncClient) -> None:
        self.http = http

    def as_user(self, context: AppContext) -> AsyncClient:
        app.dependency_overrides[get_app_context] = lambda: context
        return self.http

    def anonymous(self) -> AsyncClient:
        app.dependency_overrides.pop(get_app_context, None)
        return self.http


@pytest_asyncio.fixture
async def api() -> AsyncIterator[Api]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http:
        yield Api(http)

    app.dependency_overrides.clear()


async def _post(
    api: Api, context: AppContext, path: str, body: dict[str, Any]
) -> dict[str, Any]:
    response = await api.as_user(context).post(path, json=body)

    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


async def test_quick_add_expense_flow(api: Api, user: AppContext) -> None:
    account = await _post(
        api, user, "/accounts", {"name": "Meal Card", "type": "BENEFITS"}
    )
    category = await _post(
        api,
        user,
        "/categories",
        {"name": "Restaurants", "kind": "EXPENSE", "icon": "utensils"},
    )

    expense = await _post(
        api,
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

    listed = await api.as_user(user).get("/transactions")

    assert expense["amount_minor"] == 2480
    assert expense["kind"] == "EXPENSE"
    assert "user_id" not in expense
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [expense["id"]]
    assert listed.json()["next_cursor"] is None


async def test_body_cannot_choose_the_owner(
    api: Api, user: AppContext, other_user: AppContext
) -> None:
    response = await api.as_user(user).post(
        "/accounts",
        json={"name": "Sneaky", "type": "CASH", "user_id": str(other_user.user_id)},
    )

    assert response.status_code == 422


@pytest.mark.parametrize("amount", [24.8, 24.0, "2480", 0, -100, True])
async def test_non_integer_or_non_positive_amounts_are_rejected(
    api: Api, user: AppContext, amount: object
) -> None:
    account = await _post(api, user, "/accounts", {"name": "Cash", "type": "CASH"})
    category = await _post(
        api,
        user,
        "/categories",
        {"name": "Food", "kind": "EXPENSE", "icon": "utensils"},
    )

    response = await api.as_user(user).post(
        "/transactions",
        json={
            "kind": "EXPENSE",
            "amount_minor": amount,
            "occurred_on": "2026-09-25",
            "from_account_id": account["id"],
            "category_id": category["id"],
        },
    )

    assert response.status_code == 422


async def test_business_rule_violation_returns_400(api: Api, user: AppContext) -> None:
    account = await _post(api, user, "/accounts", {"name": "Cash", "type": "CASH"})
    salary = await _post(
        api,
        user,
        "/categories",
        {"name": "Salary", "kind": "INCOME", "icon": "briefcase"},
    )

    response = await api.as_user(user).post(
        "/transactions",
        json={
            "kind": "EXPENSE",
            "amount_minor": 100,
            "occurred_on": "2026-09-25",
            "from_account_id": account["id"],
            "category_id": salary["id"],
        },
    )

    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_other_users_resources_answer_404(
    api: Api, user: AppContext, other_user: AppContext
) -> None:
    account = await _post(api, user, "/accounts", {"name": "Mine", "type": "CASH"})

    read = await api.as_user(other_user).get(f"/accounts/{account['id']}")
    patch = await api.as_user(other_user).patch(
        f"/accounts/{account['id']}", json={"archived": True}
    )

    assert read.status_code == 404
    assert read.json()["code"] == "NOT_FOUND"
    assert patch.status_code == 404


async def test_duplicate_name_answers_409(api: Api, user: AppContext) -> None:
    await _post(api, user, "/accounts", {"name": "Savings", "type": "SAVINGS"})

    response = await api.as_user(user).post(
        "/accounts", json={"name": "savings", "type": "SAVINGS"}
    )

    assert response.status_code == 409
    assert response.json()["code"] == "CONFLICT"


async def test_transaction_lifecycle_over_http(api: Api, user: AppContext) -> None:
    account = await _post(api, user, "/accounts", {"name": "Cash", "type": "CASH"})
    category = await _post(
        api,
        user,
        "/categories",
        {"name": "Food", "kind": "EXPENSE", "icon": "utensils"},
    )
    expense = await _post(
        api,
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
        api,
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

    http = api.as_user(user)
    blocked = await http.delete(f"/transactions/{expense['id']}")
    change_kind = await http.patch(
        f"/transactions/{expense['id']}", json={"kind": "INCOME"}
    )
    edited = await http.patch(
        f"/transactions/{expense['id']}", json={"description": "Team dinner"}
    )
    removed = await http.delete(f"/transactions/{reimbursement['id']}")
    removed_expense = await http.delete(f"/transactions/{expense['id']}")

    assert blocked.status_code == 409
    assert change_kind.status_code == 422
    assert edited.status_code == 200
    assert edited.json()["description"] == "Team dinner"
    assert edited.json()["reimbursed_amount_minor"] == 5000
    assert removed.status_code == 204
    assert removed_expense.status_code == 204


async def test_history_query_parameters(api: Api, user: AppContext) -> None:
    http = api.as_user(user)

    reversed_period = await http.get(
        "/transactions", params={"from": "2026-09-30", "to": "2026-09-01"}
    )
    too_large = await http.get("/transactions", params={"limit": 201})
    bad_cursor = await http.get("/transactions", params={"cursor": "garbage"})

    assert reversed_period.status_code == 400
    assert too_large.status_code == 422
    assert bad_cursor.status_code == 400


async def test_profile_endpoint_returns_the_caller(api: Api, user: AppContext) -> None:
    response = await api.as_user(user).get("/me")

    assert response.status_code == 200
    assert response.json()["id"] == str(user.user_id)
    assert response.json()["name"] == "Test User"


async def test_requests_without_a_bearer_token_are_rejected(api: Api) -> None:
    response = await api.anonymous().get("/accounts")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"

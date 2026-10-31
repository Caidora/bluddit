"""HTTP response contracts must not expose repository-only fields."""

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
import pytest

from bluddit_api.main import create_app
from bluddit_api.models.accounts import Account
from bluddit_api.routes import accounts
from bluddit_api.routes.responses import AccountResponse
from bluddit_api.utils.auth import current_account
from bluddit_api.utils.dependencies import get_membership_repository


class InternalAccount(Account):
    password_hash: str
    internal_note: str


@pytest.fixture
def account_record():
    return InternalAccount.model_validate(
        {
            "id": 2,
            "username": "member",
            "display_name": "Member",
            "membership_state": "active",
            "role_name": "member",
            "timezone": None,
            "password_hash": "private-hash",
            "internal_note": "private-note",
        }
    )


@pytest.fixture
def response_client(monkeypatch, account_record):
    monkeypatch.delenv("PGHOST", raising=False)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", "http://testserver")
    app = create_app()
    repository = AsyncMock()
    app.dependency_overrides[get_membership_repository] = lambda: repository
    app.dependency_overrides[current_account] = lambda: account_record.model_copy(
        update={"id": 1, "role_name": "guild_master"}
    )
    with TestClient(app) as client:
        client.headers.update({"Origin": "http://testserver", "X-CSRF-Protection": "1"})
        yield client, repository


@pytest.mark.parametrize(
    "operation,state,role",
    [
        (None, "active", "member"),
        ("approve", "pending", "member"),
        ("reject", "pending", "member"),
        ("deactivate", "active", "member"),
        ("activate", "inactive", "member"),
        ("promote_to_officer", "active", "member"),
        ("demote_to_member", "active", "officer"),
        ("pass_guild_master", "active", "member"),
    ],
)
@pytest.mark.anyio
async def test_account_handlers_convert_repository_records(
    account_record, operation, state, role
):
    repository = AsyncMock()
    repository.get_account.return_value = account_record.model_copy(
        update={"membership_state": state, "role_name": role}
    )
    if operation:
        getattr(repository, operation).return_value = account_record
    handler = getattr(accounts, operation or "account")
    arguments = {
        "account_id": 2,
        "actor": account_record.model_copy(update={"id": 1}),
        "repository": repository,
    }
    if operation in {"reject", "deactivate"}:
        arguments["auth_repository"] = AsyncMock()
    result = await handler(**arguments)
    assert isinstance(result, AccountResponse)
    assert result.model_dump(mode="json") == {
        key: value
        for key, value in account_record.model_dump(mode="json").items()
        if key not in {"password_hash", "internal_note"}
    }


def test_account_list_and_current_account_filter_internal_fields(
    response_client, account_record
):
    client, repository = response_client
    repository.list_accounts.return_value = [account_record]
    response = client.get("/api/accounts?limit=5&offset=10")
    assert response.status_code == 200
    body = response.json()
    assert (body["limit"], body["offset"]) == (5, 10)
    assert body["accounts"] == [
        AccountResponse.model_validate(account_record).model_dump()
    ]
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json()["timezone"] is None
    assert "accounts.manage" in response.json()["permissions"]
    assert "password_hash" not in response.json()
    assert "internal_note" not in response.json()


def test_registration_filters_repository_fields(response_client, account_record):
    client, repository = response_client
    repository.register.return_value = account_record.model_copy(
        update={"membership_state": "pending"}
    )
    response = client.post(
        "/api/auth/register",
        json={
            "username": "member",
            "display_name": "Member",
            "password": "test-password",
        },
    )
    assert response.status_code == 201
    assert response.json()["membership_state"] == "pending"
    assert set(response.json()) == set(AccountResponse.model_fields)


def test_all_json_routes_document_named_response_models(response_client):
    client, _ = response_client
    schema = client.get("/api/openapi.json").json()
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            for status, response in operation["responses"].items():
                if not status.startswith("2"):
                    continue
                if status == "204":
                    assert "content" not in response
                    continue
                model = response["content"]["application/json"]["schema"]
                assert "$ref" in model, (method, path, model)
    ready_responses = schema["paths"]["/api/ready"]["get"]["responses"]
    assert ready_responses["200"]["content"] == ready_responses["503"]["content"]
    response = client.get("/api/permissions")
    assert response.status_code == 200
    assert set(response.json()["roles"]) == {"member", "officer", "guild_master"}

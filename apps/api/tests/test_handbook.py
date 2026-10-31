"""Handbook HTTP authorization and validation boundaries without PostgreSQL."""

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
import pytest

from bluddit_api.main import create_app
from bluddit_api.models.accounts import Account
from bluddit_api.utils.auth import current_account
from bluddit_api.utils.dependencies import get_handbook_repository

HEADERS = {"Origin": "http://testserver", "X-CSRF-Protection": "1"}
CONTENT = {"title": "Synthetic policy", "body": "Test content"}


@pytest.fixture
def handbook_client(monkeypatch):
    monkeypatch.delenv("PGHOST", raising=False)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", "http://testserver")
    app = create_app()
    repository = AsyncMock()
    actor = Account(
        id=1,
        username="editor",
        display_name="Editor",
        role_name="officer",
        membership_state="active",
        timezone=None,
    )
    app.dependency_overrides[current_account] = lambda: actor
    app.dependency_overrides[get_handbook_repository] = lambda: repository
    with TestClient(app) as client:
        client.headers.update(HEADERS)
        yield client, repository, actor


@pytest.mark.parametrize("role", ["member", "officer", "guild_master"])
@pytest.mark.parametrize("state", ["active", "pending", "inactive", "rejected"])
def test_read_and_editor_permission_boundaries(handbook_client, role, state):
    client, repository, actor = handbook_client
    actor.role_name = role
    actor.membership_state = state
    repository.list_sections.return_value = []
    read = client.get("/api/handbook")
    assert read.status_code == (200 if state == "active" else 403)
    if state == "active" and role != "member":
        return  # Successful persistence is covered by real-database tests.
    for method, path, body in (
        ("POST", "/api/handbook", {**CONTENT, "slug": "test"}),
        ("PUT", "/api/handbook/test", {**CONTENT, "expected_revision": 1}),
        ("GET", "/api/handbook/test/revisions", None),
    ):
        assert client.request(method, path, json=body).status_code == 403
    repository.create.assert_not_awaited()
    repository.edit.assert_not_awaited()
    repository.revisions.assert_not_awaited()


@pytest.mark.parametrize(
    "change",
    [
        {"title": " "},
        {"body": "\n"},
        {"body": "x" * 30001},
        {"title": "x" * 161},
        {"slug": "Bad slug"},
        {"slug": ""},
        {"slug": "a" * 81},
        {"author_account_id": 9},
        {"unexpected": True},
    ],
)
def test_invalid_creation_rejected_before_persistence(handbook_client, change):
    client, repository, _ = handbook_client
    response = client.post("/api/handbook", json={**CONTENT, "slug": "test", **change})
    assert response.status_code == 422
    repository.create.assert_not_awaited()


@pytest.mark.parametrize(
    "change",
    [
        {"expected_revision": 0},
        {"expected_revision": -1},
        {"expected_revision": None},
        {"slug": "renamed"},
        {"author_account_id": 9},
        {"title": " "},
    ],
)
def test_invalid_edits_rejected_before_persistence(handbook_client, change):
    client, repository, _ = handbook_client
    response = client.put(
        "/api/handbook/test", json={**CONTENT, "expected_revision": 1, **change}
    )
    assert response.status_code == 422
    repository.edit.assert_not_awaited()


def test_csrf_and_query_validation(handbook_client):
    client, repository, _ = handbook_client
    assert (
        client.post(
            "/api/handbook",
            headers={"Origin": "https://evil.invalid"},
            json={**CONTENT, "slug": "test"},
        ).status_code
        == 403
    )
    assert client.get("/api/handbook", params={"q": "x" * 201}).status_code == 422
    for query in ("limit=0", "limit=51", "offset=-1"):
        assert client.get("/api/handbook/test/revisions?" + query).status_code == 422
    repository.create.assert_not_awaited()
    repository.revisions.assert_not_awaited()

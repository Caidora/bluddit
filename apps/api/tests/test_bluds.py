"""Catalog and HTTP validation/permission boundaries without PostgreSQL."""

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
import pytest

from bluddit_api.data.bluds import REFERENCES
from bluddit_api.main import create_app
from bluddit_api.models.accounts import Account
from bluddit_api.models.bluds import BludRecord
from bluddit_api.utils.auth import current_account
from bluddit_api.utils.dependencies import get_bluds_repository

CONTENT = {"name": "River", "class_id": "mage", "character_created_on": "2026-10-28"}


@pytest.fixture
def bluds_client(monkeypatch):
    monkeypatch.delenv("PGHOST", raising=False)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", "http://testserver")
    app = create_app()
    actor = Account(
        id=1,
        username="member",
        display_name="Member",
        role_name="member",
        membership_state="active",
        timezone=None,
    )
    repository = AsyncMock()
    repository.list_bluds.return_value = []
    repository.get.return_value = BludRecord(
        **CONTENT,
        blud_id=1,
        account_id=1,
        owner_name="Member",
        spec_id=None,
        farming_zone_id=None,
        farming_zone_updated_at=None,
        archived=False,
        created_at="2026-11-01T00:00:00Z",
        updated_at="2026-11-01T00:00:00Z",
        updated_by_account_id=1,
        professions=[],
        dungeons=[],
    )
    app.dependency_overrides[current_account] = lambda: actor
    app.dependency_overrides[get_bluds_repository] = lambda: repository
    with TestClient(app) as client:
        client.headers.update({"Origin": "http://testserver", "X-CSRF-Protection": "1"})
        yield client, repository, actor


def test_reference_contract_and_permission_gate(bluds_client):
    client, _, actor = bluds_client
    response = client.get("/api/bluds/reference-data")
    assert response.status_code == 200
    data = response.json()
    assert data["version"] and len(data["dungeons"]) == 35
    assert len(data["classes"]) == 9
    assert len({d["id"] for d in data["dungeons"]}) == 35
    assert all(
        d["suggested_level_min"] <= d["suggested_level_max"] for d in data["dungeons"]
    )
    assert sum(p.category == "primary" for p in REFERENCES.professions) == 9
    assert sum(p.category == "secondary" for p in REFERENCES.professions) == 3
    for state in ("pending", "inactive", "rejected"):
        actor.membership_state = state
        assert client.get("/api/bluds/reference-data").status_code == 403
        assert client.get("/api/bluds").status_code == 403
        assert client.patch("/api/bluds/1", json={"name": "Changed"}).status_code == 403


@pytest.mark.parametrize(
    "change",
    [
        {"name": " "},
        {"class_id": "retail-class"},
        {"character_created_on": None},
        {"character_created_on": "invalid"},
        {"name": "x" * 101},
        {"account_id": 999},
        {"spec_id": "warrior-arms"},
        {"farming_zone_id": "outland"},
    ],
)
def test_invalid_create_never_writes(bluds_client, change):
    client, repository, _ = bluds_client
    assert client.post("/api/bluds", json={**CONTENT, **change}).status_code == 422
    repository.create.assert_not_awaited()


@pytest.mark.parametrize(
    "change",
    [
        {"name": None},
        {"class_id": None},
        {"archived": None},
        {"professions": None},
        {"dungeons": None},
        {"character_created_on": None},
        {"account_id": 2},
        {"expected_revision": 1},
        {"professions": [{"profession_id": "unknown"}]},
        {"professions": [{"profession_id": "mining", "level": -1}]},
        {"professions": [{"profession_id": "mining", "level": 301}]},
        {"professions": [{"profession_id": "mining", "level": 1.5}]},
        {"professions": [{"profession_id": "mining"}] * 2},
        {
            "professions": [
                {"profession_id": p} for p in ("mining", "alchemy", "tailoring")
            ]
        },
        {"dungeons": [{"dungeon_id": "unknown", "status": "completed"}]},
        {"dungeons": [{"dungeon_id": "ragefire-chasm", "status": "unknown"}]},
        {"dungeons": [{"dungeon_id": "ragefire-chasm", "status": "completed"}] * 2},
    ],
)
def test_invalid_patch_never_writes(bluds_client, change):
    client, repository, _ = bluds_client
    assert client.patch("/api/bluds/1", json=change).status_code == 422
    repository.update.assert_not_awaited()


@pytest.mark.parametrize(
    "query",
    [
        "limit=0",
        "limit=101",
        "offset=-1",
        "q=" + "x" * 201,
        "class_id=unknown",
        "dungeon_status=unknown",
        "account_id=2",
    ],
)
def test_invalid_filters(bluds_client, query):
    client, repository, _ = bluds_client
    assert client.get("/api/bluds?" + query).status_code == 422
    repository.list_bluds.assert_not_awaited()


def test_cross_owner_and_csrf_denials(bluds_client):
    client, repository, actor = bluds_client
    actor.id = 2
    assert client.patch("/api/bluds/1", json={"name": "Changed"}).status_code == 403
    repository.update.assert_not_awaited()
    assert (
        client.post(
            "/api/bluds", json=CONTENT, headers={"Origin": "https://evil.invalid"}
        ).status_code
        == 403
    )
    repository.create.assert_not_awaited()


def test_bluds_permissions_are_distinct_from_guild_read(bluds_client, monkeypatch):
    from bluddit_api.utils.permissions import Permission, RolePolicy

    client, repository, _ = bluds_client
    monkeypatch.setattr(
        RolePolicy, "mappings", {"member": frozenset({Permission.GUILD_READ})}
    )
    assert client.get("/api/bluds").status_code == 403
    assert client.get("/api/bluds/reference-data").status_code == 403
    assert client.post("/api/bluds", json=CONTENT).status_code == 403
    monkeypatch.setattr(
        RolePolicy, "mappings", {"member": frozenset({Permission.BLUDS_VIEW})}
    )
    assert client.get("/api/bluds").status_code == 200
    assert client.patch("/api/bluds/1", json={"name": "Denied"}).status_code == 403
    repository.create.assert_not_awaited()
    repository.update.assert_not_awaited()

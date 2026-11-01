"""Persisted Bluds workflows, simple updates, filters and live authorization."""

from httpx import ASGITransport, AsyncClient
import pytest

from bluddit_api.main import create_app
from bluddit_api.utils.dependencies import get_reference_data
from reference_data import REFERENCES
from bluddit_api.migrate import run_migrations
from bluddit_api.repositories.auth import AuthRepository
from bluddit_api.utils.security import new_token, token_hash

pytestmark = pytest.mark.anyio
CONTENT = {"name": "River", "class_id": "mage", "character_created_on": "2026-10-28"}


@pytest.fixture
async def bluds(database, monkeypatch):
    async with database.pool.connection() as connection:
        await run_migrations(connection, apply=True)
    tokens, ids = {}, {}
    for username, role in [
        ("member", "member"),
        ("other", "member"),
        ("officer", "officer"),
        ("gm", "guild_master"),
    ]:
        async with database.transaction() as connection:
            cursor = await connection.execute(
                """INSERT INTO accounts (username, display_name, password_hash, membership_state, role_name)
                VALUES (%(username)s, %(username)s, 'test-hash', 'active', %(role)s) RETURNING id""",
                {"username": username, "role": role},
            )
            ids[username] = (await cursor.fetchone())[0]
        token = new_token()
        assert await AuthRepository(database).create_session(
            ids[username], "test-hash", token_hash(new_token()), token_hash(token)
        )
        tokens[username] = {"Authorization": "Bearer " + token}
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", "http://test")
    app = create_app()
    app.dependency_overrides[get_reference_data] = lambda: REFERENCES
    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Origin": "http://test", "X-CSRF-Protection": "1"},
        ) as client,
    ):
        yield client, database, ids, tokens


async def create(client, tokens, **changes):
    response = await client.post(
        "/api/bluds", json={**CONTENT, **changes}, headers=tokens["member"]
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_creation_simple_partial_updates_progress_and_timestamps(bluds):
    client, _, ids, tokens = bluds
    assert (await client.get("/api/bluds")).status_code == 401
    assert (await client.get("/api/bluds/reference-data")).status_code == 401
    first = await create(client, tokens)
    second = await create(client, tokens, name="River Alt", class_id="druid")
    assert first["blud_id"] != second["blud_id"]
    assert first["account_id"] == ids["member"]
    assert first["character_created_on"] == "2026-10-28"
    assert first["professions"] == [] and first["dungeons"] == []
    assert first["spec_id"] is None and "farming_zone_id" not in first
    assert first["completed_dungeons"] == 0 and first["total_dungeons"] == 35
    path = f"/api/bluds/{first['blud_id']}"
    body = {
        "spec_id": "mage-frost",
        "professions": [
            {"profession_id": "mining", "level": 100},
            {"profession_id": "alchemy", "level": None},
            {"profession_id": "cooking", "level": 10},
            {"profession_id": "first-aid", "level": None},
            {"profession_id": "fishing", "level": 300},
        ],
        "dungeons": [{"dungeon_id": "ragefire-chasm", "status": "completed"}],
    }
    response = await client.patch(path, json=body, headers=tokens["member"])
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["completed_dungeons"] == 1
    prof_times = {p["profession_id"]: p["updated_at"] for p in saved["professions"]}
    unchanged = (await client.patch(path, json=body, headers=tokens["member"])).json()
    assert {
        p["profession_id"]: p["updated_at"] for p in unchanged["professions"]
    } == prof_times
    # Omitted fields survive ordinary, unconditional updates.
    changed = (
        await client.patch(path, json={"name": "Renamed"}, headers=tokens["member"])
    ).json()
    assert (
        changed["name"] == "Renamed" and changed["professions"] == saved["professions"]
    )
    body["professions"][0]["level"] = 101
    changed = (
        await client.patch(
            path, json={"professions": body["professions"]}, headers=tokens["member"]
        )
    ).json()
    assert (
        next(
            p["updated_at"]
            for p in changed["professions"]
            if p["profession_id"] == "mining"
        )
        > prof_times["mining"]
    )
    assert (
        next(
            p["updated_at"]
            for p in changed["professions"]
            if p["profession_id"] == "cooking"
        )
        == prof_times["cooking"]
    )
    for status, completed, reruns in [
        ("completed_rerun", 1, 1),
        ("not_completed", 0, 0),
        ("completed", 1, 0),
    ]:
        changed = (
            await client.patch(
                path,
                json={"dungeons": [{"dungeon_id": "ragefire-chasm", "status": status}]},
                headers=tokens["member"],
            )
        ).json()
        assert (changed["completed_dungeons"], changed["rerun_dungeons"]) == (
            completed,
            reruns,
        )
    changed = (
        await client.patch(
            path,
            json={
                "dungeons": [{"dungeon_id": "deadmines", "status": "completed_rerun"}]
            },
            headers=tokens["member"],
        )
    ).json()
    assert len(changed["dungeons"]) == 2 and changed["completed_dungeons"] == 2
    cleared = (
        await client.patch(
            path,
            json={"professions": [], "spec_id": None},
            headers=tokens["member"],
        )
    ).json()
    assert cleared["professions"] == [] and cleared["spec_id"] is None
    assert (await client.get(path, headers=tokens["other"])).json() == cleared


async def test_directory_filters_pagination_and_archiving(bluds):
    client, _, _, tokens = bluds
    one = await create(client, tokens, name="Alpha")
    two = await create(client, tokens, name="Beta")
    path = f"/api/bluds/{one['blud_id']}"
    await client.patch(
        path,
        headers=tokens["member"],
        json={
            "professions": [{"profession_id": "mining", "level": 100}],
            "dungeons": [{"dungeon_id": "ragefire-chasm", "status": "completed_rerun"}],
        },
    )
    for query in [
        "q=ALPHA",
        "q=member&mine=true&class_id=mage&profession_id=mining&dungeon_id=ragefire-chasm&dungeon_status=completed_rerun",
    ]:
        result = (
            await client.get("/api/bluds?" + query, headers=tokens["member"])
        ).json()
        assert [b["blud_id"] for b in result["bluds"]] == [one["blud_id"]]
    for query in [
        "q=absent",
        "q=%25",
        "q=' OR true --",
        "profession_id=tailoring",
        "mine=true",
    ]:
        result = (
            await client.get("/api/bluds?" + query, headers=tokens["other"])
        ).json()
        assert result["bluds"] == []
    result = (
        await client.get(
            "/api/bluds?dungeon_id=ragefire-chasm", headers=tokens["member"]
        )
    ).json()
    assert [b["blud_id"] for b in result["bluds"]] == [
        two["blud_id"]
    ]  # Missing progress is incomplete.
    result = (await client.get("/api/bluds?limit=1", headers=tokens["member"])).json()
    assert result["has_more"] and result["offset"] == 0
    result = (
        await client.get("/api/bluds?limit=1&offset=1", headers=tokens["member"])
    ).json()
    assert not result["has_more"] and result["bluds"][0]["blud_id"] == two["blud_id"]
    archived = (
        await client.patch(path, headers=tokens["member"], json={"archived": True})
    ).json()
    assert archived["archived"] and archived["completed_dungeons"] == 1
    result = (await client.get("/api/bluds", headers=tokens["member"])).json()
    assert [b["blud_id"] for b in result["bluds"]] == [two["blud_id"]]
    result = (
        await client.get("/api/bluds?archived=true", headers=tokens["member"])
    ).json()
    assert result["bluds"] == [archived]
    restored = (
        await client.patch(path, headers=tokens["officer"], json={"archived": False})
    ).json()
    assert not restored["archived"] and restored["dungeons"] == archived["dungeons"]


async def test_ownership_officer_corrections_and_live_membership(bluds):
    client, database, ids, tokens = bluds
    one = await create(client, tokens)
    path = f"/api/bluds/{one['blud_id']}"
    assert (
        await client.patch(path, headers=tokens["other"], json={"archived": True})
    ).status_code == 403
    for who in ("member", "officer", "gm"):
        assert (
            await client.patch(
                path, headers=tokens[who], json={"account_id": ids["other"]}
            )
        ).status_code == 422
    for who in ("officer", "gm"):
        corrected = (
            await client.patch(path, headers=tokens[who], json={"name": "Corrected"})
        ).json()
        assert corrected["updated_by_account_id"] == ids[who]
        assert corrected["account_id"] == ids["member"]
    async with database.transaction() as connection:
        await connection.execute(
            """UPDATE accounts SET role_name = 'member' WHERE id = %(account_id)s""",
            {"account_id": ids["officer"]},
        )
    assert (
        await client.patch(path, headers=tokens["officer"], json={"name": "Denied"})
    ).status_code == 403
    for state in ("inactive", "pending", "rejected"):
        async with database.transaction() as connection:
            await connection.execute(
                """UPDATE accounts SET membership_state = %(state)s WHERE id = %(account_id)s""",
                {"state": state, "account_id": ids["member"]},
            )
        assert (await client.get(path, headers=tokens["member"])).status_code == 401
        assert (
            await client.patch(path, headers=tokens["member"], json={"name": "Denied"})
        ).status_code == 401
    assert (
        await client.get("/api/bluds/99999", headers=tokens["other"])
    ).status_code == 404
    assert (
        await client.patch(
            "/api/bluds/99999", headers=tokens["other"], json={"name": "Missing"}
        )
    ).status_code == 404


async def test_changing_class_checks_existing_spec_and_simple_updates_need_no_revision(
    bluds,
):
    client, _, _, tokens = bluds
    one = await create(client, tokens, spec_id="mage-frost")
    path = f"/api/bluds/{one['blud_id']}"
    assert (
        await client.patch(path, headers=tokens["member"], json={"class_id": "warrior"})
    ).status_code == 422
    assert (
        await client.patch(
            path,
            headers=tokens["member"],
            json={"class_id": "warrior", "spec_id": None},
        )
    ).status_code == 200
    for name in ("First save", "Last save"):
        assert (
            await client.patch(path, headers=tokens["member"], json={"name": name})
        ).status_code == 200
    assert (await client.get(path, headers=tokens["member"])).json()[
        "name"
    ] == "Last save"


async def test_removed_zones_reject_input_and_preserve_stored_values(bluds):
    client, database, _, tokens = bluds
    record = await create(client, tokens)
    path = f"/api/bluds/{record['blud_id']}"
    async with database.transaction() as connection:
        await connection.execute(
            """UPDATE bluds SET farming_zone_id = 'legacy-zone',
            farming_zone_updated_at = '2026-01-01T00:00:00Z'
            WHERE blud_id = %(blud_id)s""",
            {"blud_id": record["blud_id"]},
        )
    assert (
        await client.patch(
            path, json={"farming_zone_id": None}, headers=tokens["member"]
        )
    ).status_code == 422
    assert (
        await client.get(
            "/api/bluds?farming_zone_id=legacy-zone", headers=tokens["member"]
        )
    ).status_code == 422
    assert (
        await client.post(
            "/api/bluds",
            json={**CONTENT, "farming_zone_id": "legacy-zone"},
            headers=tokens["member"],
        )
    ).status_code == 422
    updated = await client.patch(
        path, json={"name": "Renamed"}, headers=tokens["member"]
    )
    assert updated.status_code == 200
    assert "farming_zone_id" not in updated.json()
    assert (
        "zones"
        not in (
            await client.get("/api/bluds/reference-data", headers=tokens["member"])
        ).json()
    )
    async with database.transaction() as connection:
        cursor = await connection.execute(
            """SELECT farming_zone_id, farming_zone_updated_at FROM bluds
            WHERE blud_id = %(blud_id)s""",
            {"blud_id": record["blud_id"]},
        )
        zone, updated_at = await cursor.fetchone()
    assert (
        zone == "legacy-zone" and updated_at.isoformat() == "2026-01-01T00:00:00+00:00"
    )

"""Persisted event authorization, lifecycle, filters and lock behavior."""

import asyncio
from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient
import pytest

from bluddit_api.main import create_app
from bluddit_api.utils.dependencies import get_reference_data
from reference_data import REFERENCES
from bluddit_api.migrate import run_migrations
from bluddit_api.repositories.auth import AuthRepository
from bluddit_api.repositories.events import EventsRepository, EventForbidden
from bluddit_api.models.events import EventPatch
from bluddit_api.utils.security import new_token, token_hash

pytestmark = pytest.mark.anyio
CONTENT = {
    "title": "Guild run",
    "activity_type": "dungeon",
    "local_start": "2090-11-01T19:00:00",
    "scheduling_timezone": "Pacific/Auckland",
}


@pytest.fixture
async def events(database, monkeypatch):
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
        "/api/events", json={**CONTENT, **changes}, headers=tokens["member"]
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_creation_editing_permissions_and_cancellation(events):
    client, database, ids, tokens = events
    assert (await client.get("/api/events")).status_code == 401
    event = await create(client, tokens, dungeon_id="ragefire-chasm")
    path = f"/api/events/{event['event_id']}"
    assert event["organizers"] == [
        {"account_id": ids["member"], "display_name": "member", "active": True}
    ]
    assert event["created_by_account_id"] == ids["member"]
    assert event["capacity"] is None and event["duration_minutes"] is None
    assert (await client.get(path, headers=tokens["other"])).status_code == 200
    assert (
        await client.patch(path, json={"title": "Stolen"}, headers=tokens["other"])
    ).status_code == 403
    changed = await client.patch(
        path, json={"title": "Renamed", "capacity": 5}, headers=tokens["member"]
    )
    assert changed.status_code == 200
    assert changed.json()["starts_at"] == event["starts_at"]
    changed = await client.patch(
        path, json={"duration_minutes": 90}, headers=tokens["officer"]
    )
    assert changed.json()["updated_by_account_id"] == ids["officer"]
    assert (
        await client.patch(path, json={"capacity": None}, headers=tokens["gm"])
    ).json()["capacity"] is None
    # An organizer on a different event has no rights here.
    other = await client.post("/api/events", json=CONTENT, headers=tokens["other"])
    assert other.status_code == 201
    assert (
        await client.post(path + "/cancel", headers=tokens["other"])
    ).status_code == 403
    response = await client.post(path + "/cancel", headers=tokens["member"])
    assert response.json()["state"] == "cancelled"
    assert (await client.post(path + "/cancel", headers=tokens["officer"])).json()[
        "updated_at"
    ] == response.json()["updated_at"]
    assert (
        await client.patch(path, json={"title": "Reopen"}, headers=tokens["gm"])
    ).status_code == 409
    assert (
        await client.put(
            path + "/organizers",
            json={"account_ids": [ids["other"]]},
            headers=tokens["officer"],
        )
    ).status_code == 409
    assert (await client.get(path, headers=tokens["member"])).json()[
        "title"
    ] == "Renamed"
    assert (
        await client.get("/api/events/999999", headers=tokens["member"])
    ).status_code == 404


async def test_officer_assignments_and_live_account_state(events):
    client, database, ids, tokens = events
    event = await create(client, tokens)
    path = f"/api/events/{event['event_id']}"
    body = {"account_ids": [ids["other"]]}
    assert (
        await client.put(path + "/organizers", json=body, headers=tokens["member"])
    ).status_code == 403
    for bad in [[], [ids["other"], ids["other"]], [999999]]:
        assert (
            await client.put(
                path + "/organizers",
                json={"account_ids": bad},
                headers=tokens["officer"],
            )
        ).status_code == 422
    assert (
        await client.put(path + "/organizers", json=body, headers=tokens["officer"])
    ).status_code == 200
    assert (
        await client.patch(path, json={"title": "Removed"}, headers=tokens["member"])
    ).status_code == 403
    assert (
        await client.patch(path, json={"title": "Assigned"}, headers=tokens["other"])
    ).status_code == 200
    async with database.transaction() as connection:
        await connection.execute(
            """UPDATE accounts SET membership_state = 'inactive' WHERE id = %(id)s""",
            {"id": ids["other"]},
        )
    assert (
        await client.patch(path, json={"title": "Inactive"}, headers=tokens["other"])
    ).status_code == 401
    assert (
        await client.put(path + "/organizers", json=body, headers=tokens["gm"])
    ).status_code == 422
    assert (
        await client.put(
            path + "/organizers",
            json={"account_ids": [ids["member"]]},
            headers=tokens["gm"],
        )
    ).status_code == 200


async def test_filters_pagination_and_validation(events):
    client, _, ids, tokens = events
    first = await create(client, tokens)
    second = await create(client, tokens)
    past = await create(
        client, tokens, local_start="2000-01-01T00:00:00", scheduling_timezone="UTC"
    )
    await client.post(
        f"/api/events/{second['event_id']}/cancel", headers=tokens["member"]
    )
    listing = (await client.get("/api/events", headers=tokens["member"])).json()
    assert [e["event_id"] for e in listing["events"]] == [first["event_id"]]
    listing = (
        await client.get(
            "/api/events?period=all&state=all&limit=1", headers=tokens["member"]
        )
    ).json()
    assert listing["events"][0]["event_id"] == past["event_id"] and listing["has_more"]
    listing = (
        await client.get(
            "/api/events?period=all&state=all&limit=1&offset=1",
            headers=tokens["member"],
        )
    ).json()
    assert listing["events"][0]["event_id"] == first["event_id"]
    assert (await client.get("/api/events?mine=true", headers=tokens["other"])).json()[
        "events"
    ] == []
    for changes in [
        {"title": " "},
        {"dungeon_id": "fake"},
        {"capacity": 0},
        {"duration_minutes": -1},
        {"activity_type": "raid"},
        {"state": "cancelled"},
        {"scheduling_timezone": "Fake/Zone"},
        {"local_start": "2026-09-27T02:30:00"},
    ]:
        assert (
            await client.post(
                "/api/events", json={**CONTENT, **changes}, headers=tokens["member"]
            )
        ).status_code == 422
    path = f"/api/events/{first['event_id']}"
    for changes in [
        {"local_start": "2026-01-01T00:00:00"},
        {"starts_at": "2026-01-01T00:00:00Z"},
        {"organizer_ids": [ids["other"]]},
    ]:
        assert (
            await client.patch(path, json=changes, headers=tokens["member"])
        ).status_code == 422


async def test_preview_and_persisted_dst_choices(events):
    client, _, _, tokens = events
    schedule = {
        "local_start": "2026-04-05T02:30:00",
        "scheduling_timezone": "Pacific/Auckland",
    }
    preview = await client.post(
        "/api/events/preview-start", json=schedule, headers=tokens["member"]
    )
    assert preview.json()["status"] == "ambiguous"
    assert (
        await client.post(
            "/api/events", json={**CONTENT, **schedule}, headers=tokens["member"]
        )
    ).status_code == 422
    earlier = await create(client, tokens, **schedule, occurrence="earlier")
    later = await create(client, tokens, **schedule, occurrence="later")
    assert datetime.fromisoformat(later["starts_at"]) - datetime.fromisoformat(
        earlier["starts_at"]
    ) == timedelta(hours=1)
    path = f"/api/events/{earlier['event_id']}"
    updated = await client.patch(
        path,
        json={
            "local_start": "2026-10-04T02:30:00",
            "scheduling_timezone": "Australia/Perth",
        },
        headers=tokens["member"],
    )
    assert datetime.fromisoformat(updated.json()["starts_at"]) == datetime(
        2026, 10, 3, 18, 30, tzinfo=UTC
    )
    assert (
        await client.get("/api/events/reference-data", headers=tokens["member"])
    ).json()["dungeons"]


async def test_waiting_edit_rechecks_removed_assignment(events):
    _, database, ids, _ = events
    # Hold the event lock while removing its organizer, then let a queued edit run.
    repo = EventsRepository(database)
    from bluddit_api.models.events import EventCreate

    event = await repo.create(
        EventCreate(**CONTENT), datetime(2090, 1, 1, tzinfo=UTC), ids["member"]
    )
    task = None
    try:
        async with database.transaction() as connection:
            await connection.execute(
                """SELECT event_id FROM events WHERE event_id = %(event_id)s FOR UPDATE""",
                {"event_id": event.event_id},
            )
            task = asyncio.create_task(
                repo.manage(
                    event.event_id,
                    ids["member"],
                    False,
                    patch=EventPatch(title="Stale authorization"),
                )
            )
            for _ in range(100):
                await connection.execute("""SELECT pg_stat_clear_snapshot()""")
                cursor = await connection.execute(
                    """SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() AND wait_event_type = 'Lock' AND query LIKE '%%SELECT event_id FROM events%%' """
                )
                if (await cursor.fetchone())[0]:
                    break
                await asyncio.sleep(0.01)
            else:
                pytest.fail("Edit did not wait for the event lock")
            await connection.execute(
                """DELETE FROM event_organizers WHERE event_id = %(event_id)s""",
                {"event_id": event.event_id},
            )
            await connection.execute(
                """INSERT INTO event_organizers (event_id, account_id) VALUES (%(event_id)s, %(account_id)s)""",
                {"event_id": event.event_id, "account_id": ids["other"]},
            )
        with pytest.raises(EventForbidden):
            await asyncio.wait_for(task, timeout=5)
        assert (await repo.get(event.event_id)).title == CONTENT["title"]
    finally:
        if task and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

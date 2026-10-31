"""Persisted handbook flows, concurrent writes, and immutable audit records."""

import asyncio

from httpx import ASGITransport, AsyncClient
import psycopg
import pytest

from bluddit_api.main import create_app
from bluddit_api.migrate import run_migrations
from bluddit_api.repositories.auth import AuthRepository
from bluddit_api.utils.security import new_token, token_hash

pytestmark = pytest.mark.anyio
CONTENT = {
    "slug": "test-rules",
    "title": "Synthetic rules",
    "body": "Synthetic test prose",
}


@pytest.fixture
async def handbook(database, monkeypatch):
    async with database.pool.connection() as connection:
        await run_migrations(connection, apply=True)
    tokens, ids = {}, {}
    for role in ("member", "officer", "guild_master"):
        async with database.transaction() as connection:
            cursor = await connection.execute(
                """
                INSERT INTO accounts (username, display_name, password_hash, membership_state, role_name)
                VALUES (%(role)s, %(role)s, 'unused-test-hash', 'active', %(role)s) RETURNING id
                """,
                {"role": role},
            )
            ids[role] = (await cursor.fetchone())[0]
        token = new_token()
        assert await AuthRepository(database).create_session(
            ids[role], "unused-test-hash", token_hash(new_token()), token_hash(token)
        )
        tokens[role] = {"Authorization": "Bearer " + token}
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", "http://test")
    app = create_app()
    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Origin": "http://test", "X-CSRF-Protection": "1"},
        ) as client,
    ):
        yield client, database, ids, tokens


async def test_empty_handbook_creation_read_search_and_revision_attribution(handbook):
    client, _, ids, tokens = handbook
    assert (await client.get("/api/handbook")).status_code == 401
    assert (await client.get("/api/handbook", headers=tokens["member"])).json()[
        "sections"
    ] == []
    response = await client.post(
        "/api/handbook", headers=tokens["officer"], json=CONTENT
    )
    assert response.status_code == 201
    first = response.json()
    assert first == {
        **CONTENT,
        "revision": 1,
        "updated_at": first["updated_at"],
        "author_account_id": ids["officer"],
        "author_name": "officer",
    }
    assert (
        await client.get("/api/handbook/test-rules", headers=tokens["member"])
    ).json() == first
    for q in ("SYNTHETIC", "test prose", "rules"):
        assert (
            await client.get("/api/handbook", params={"q": q}, headers=tokens["member"])
        ).json()["sections"] == [first]
    for q in ("absent", "%", "' OR true --"):
        assert (
            await client.get("/api/handbook", params={"q": q}, headers=tokens["member"])
        ).json()["sections"] == []
    # Markup is stored and returned as JSON/plain text, never rendered as HTML by the API.
    body = '<script>alert("test")</script>\n<img src=x onerror=alert(1)>'
    response = await client.put(
        "/api/handbook/test-rules",
        headers=tokens["guild_master"],
        json={"title": " Revised title ", "body": body, "expected_revision": 1},
    )
    assert response.status_code == 200
    second = response.json()
    assert second["slug"] == CONTENT["slug"] and second["revision"] == 2
    assert second["author_account_id"] == ids["guild_master"]
    assert second["title"] == "Revised title" and second["body"] == body
    assert response.headers["content-type"] == "application/json"
    assert (
        await client.get("/api/handbook/test-rules", headers=tokens["member"])
    ).json() == second
    history = await client.get(
        "/api/handbook/test-rules/revisions", headers=tokens["officer"]
    )
    assert history.json()["revisions"] == [second, first]
    assert (
        await client.get(
            "/api/handbook/test-rules/revisions?limit=1&offset=1",
            headers=tokens["officer"],
        )
    ).json()["revisions"] == [first]
    assert (
        await client.get(
            "/api/handbook/test-rules/revisions?offset=2", headers=tokens["officer"]
        )
    ).json()["revisions"] == []
    # Search only current content, not superseded policy text.
    assert (
        await client.get("/api/handbook?q=test%20prose", headers=tokens["member"])
    ).json()["sections"] == []


async def test_denials_missing_and_duplicate_sections(handbook):
    client, database, ids, tokens = handbook
    assert (
        await client.post("/api/handbook", json=CONTENT, headers=tokens["member"])
    ).status_code == 403
    assert (
        await client.put(
            "/api/handbook/test-rules",
            json={"title": "x", "body": "y", "expected_revision": 1},
            headers=tokens["member"],
        )
    ).status_code == 403
    assert (
        await client.get("/api/handbook/test-rules/revisions", headers=tokens["member"])
    ).status_code == 403
    assert (
        await client.get("/api/handbook/missing", headers=tokens["member"])
    ).status_code == 404
    assert (
        await client.get("/api/handbook/missing/revisions", headers=tokens["officer"])
    ).status_code == 404
    assert (
        await client.put(
            "/api/handbook/missing",
            json={"title": "x", "body": "y", "expected_revision": 1},
            headers=tokens["officer"],
        )
    ).status_code == 404
    responses = await asyncio.gather(
        *[
            client.post("/api/handbook", json=CONTENT, headers=tokens["officer"])
            for _ in range(2)
        ]
    )
    assert sorted(r.status_code for r in responses) == [201, 409]
    assert (
        len(
            (
                await client.get(
                    "/api/handbook/test-rules/revisions", headers=tokens["officer"]
                )
            ).json()["revisions"]
        )
        == 1
    )
    async with database.transaction() as connection:
        await connection.execute(
            """UPDATE accounts SET membership_state = 'inactive' WHERE id = %(id)s""",
            {"id": ids["officer"]},
        )
    assert (
        await client.post(
            "/api/handbook",
            json={**CONTENT, "slug": "another"},
            headers=tokens["officer"],
        )
    ).status_code == 401


async def test_concurrent_edits_stale_saves_and_immutable_revisions(handbook):
    client, database, _, tokens = handbook
    await client.post("/api/handbook", json=CONTENT, headers=tokens["officer"])
    edit = {"title": "Updated", "body": "New test content", "expected_revision": 1}
    results = await asyncio.gather(
        *[
            client.put("/api/handbook/test-rules", json=edit, headers=tokens[role])
            for role in ("officer", "guild_master")
        ]
    )
    assert sorted(r.status_code for r in results) == [200, 409]
    assert (
        await client.put(
            "/api/handbook/test-rules", json=edit, headers=tokens["officer"]
        )
    ).status_code == 409
    history = (
        await client.get(
            "/api/handbook/test-rules/revisions", headers=tokens["officer"]
        )
    ).json()["revisions"]
    assert [r["revision"] for r in history] == [2, 1]
    assert history[1]["body"] == CONTENT["body"]
    for query in (
        "UPDATE handbook_revisions SET body = 'tampered'",
        "DELETE FROM handbook_revisions",
    ):
        with pytest.raises(psycopg.errors.RaiseException, match="immutable"):
            async with database.transaction() as connection:
                await connection.execute(query)
    assert (
        await client.get(
            "/api/handbook/test-rules/revisions", headers=tokens["officer"]
        )
    ).json()["revisions"] == history


async def test_failed_revision_write_rolls_back_current_version(handbook, monkeypatch):
    client, database, _, tokens = handbook
    await client.post("/api/handbook", json=CONTENT, headers=tokens["officer"])
    original = psycopg.AsyncConnection.execute

    async def fail_update(self, query, *args, **kwargs):
        if "UPDATE handbook_sections" in str(query):
            raise psycopg.OperationalError("synthetic failure")
        return await original(self, query, *args, **kwargs)

    monkeypatch.setattr(psycopg.AsyncConnection, "execute", fail_update)
    response = await client.put(
        "/api/handbook/test-rules",
        headers=tokens["officer"],
        json={"title": "x", "body": "y", "expected_revision": 1},
    )
    assert response.status_code == 503
    assert "synthetic failure" not in response.text
    assert (
        await client.get("/api/handbook/test-rules", headers=tokens["member"])
    ).json()["revision"] == 1
    assert (
        len(
            (
                await client.get(
                    "/api/handbook/test-rules/revisions", headers=tokens["officer"]
                )
            ).json()["revisions"]
        )
        == 1
    )

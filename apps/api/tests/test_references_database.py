"""Real PostgreSQL lease fencing, restart persistence and atomic publication."""

from datetime import timedelta

import pytest

from bluddit_api.migrate import run_migrations
from bluddit_api.models.references import ReferenceEntity
from bluddit_api.repositories.references import ReferencesRepository
from bluddit_api.services.blizzard import utcnow

pytestmark = pytest.mark.anyio


@pytest.fixture
async def references(database):
    async with database.pool.connection() as connection:
        await run_migrations(connection, apply=True)
    return ReferencesRepository(database)


async def test_lease_exclusivity_cache_persistence_and_exact_expiry(references):
    repository = references
    token = await repository.claim("synthetic")
    assert token is not None
    assert await repository.claim("synthetic") is None
    await repository.finish("synthetic", token, {"classes": []})
    restarted = ReferencesRepository(repository.database)
    cached = await restarted.cached("synthetic")
    assert cached.document == {"classes": []}
    assert cached.expires_at - cached.fetched_at == timedelta(hours=1)
    assert await restarted.claim("synthetic") is None
    async with repository.database.transaction() as connection:
        await connection.execute(
            """UPDATE reference_cache SET expires_at = now() WHERE cache_key = %(key)s""",
            {"key": "synthetic"},
        )
    token = await restarted.claim("synthetic")
    assert token is not None
    await restarted.fail("synthetic", token, 180)
    cached = await restarted.cached("synthetic")
    assert cached.document == {"classes": []}
    assert cached.retry_at > utcnow() + timedelta(seconds=170)
    assert await restarted.claim("synthetic") is None


async def test_expired_lease_is_recovered_and_previous_owner_cannot_publish(references):
    first = await references.claim("synthetic")
    async with references.database.transaction() as connection:
        await connection.execute(
            """UPDATE reference_cache SET lease_until = now() - interval '1 second'
            WHERE cache_key = %(key)s""",
            {"key": "synthetic"},
        )
    second = await references.claim("synthetic")
    assert second is not None and second != first
    await references.finish("synthetic", first, {"stale-owner": True})
    await references.publish("synthetic", first, ["class"], [])
    assert (await references.cached("synthetic")).document is None
    await references.finish("synthetic", second, {"new-owner": True})
    assert (await references.cached("synthetic")).document == {"new-owner": True}


async def test_publication_reuses_legacy_ids_and_empty_catalog_preserves_history(
    references,
):
    initial = await references.entities()
    assert len(initial) == 83  # 9 classes, 27 specs, 12 professions, 35 dungeons.
    assert not any(e.active for e in initial)
    assert all(set(e.payload) <= {"name", "class_id"} for e in initial)
    token = await references.claim("classes")
    await references.publish(
        "classes",
        token,
        ["class", "spec"],
        [
            ReferenceEntity(
                entity_kind="class",
                reference_id="mage",
                blizzard_id=8,
                payload={"name": "Synthetic mage"},
                active=True,
            ),
            ReferenceEntity(
                entity_kind="class",
                reference_id="blizzard-class-123",
                blizzard_id=123,
                payload={"name": "Synthetic new class"},
                active=True,
            ),
        ],
    )
    rows = await references.entities()
    assert {e.reference_id for e in rows if e.active} == {"mage", "blizzard-class-123"}
    assert next(e for e in rows if e.reference_id == "mage").blizzard_id == 8
    async with references.database.transaction() as connection:
        await connection.execute(
            """UPDATE reference_cache SET expires_at = now() WHERE cache_key = %(key)s""",
            {"key": "classes"},
        )
    token = await references.claim("classes")
    await references.publish("classes", token, ["class", "spec"], [])
    assert not any(e.active for e in await references.entities())
    assert len(await references.entities()) == 84


async def test_publication_rolls_back_on_identity_conflict(references):
    token = await references.claim("classes")
    with pytest.raises(Exception):
        await references.publish(
            "classes",
            token,
            ["class"],
            [
                ReferenceEntity(
                    entity_kind="class",
                    reference_id="mage",
                    blizzard_id=8,
                    payload={"name": "Mage"},
                ),
                ReferenceEntity(
                    entity_kind="class",
                    reference_id="warrior",
                    blizzard_id=8,
                    payload={"name": "Bad duplicate"},
                ),
            ],
        )
    assert not any(e.active for e in await references.entities())
    assert (await references.cached("classes")).document is None
    # The same valid lease remains usable after rollback.
    await references.finish("classes", token, {"recovered": True})


async def test_mocked_provider_publishes_shared_catalog_and_preserves_it_on_outage(
    references,
):
    import httpx
    from bluddit_api.services.blizzard import BlizzardClient, BlizzardSettings
    from bluddit_api.services.references import ReferencesService

    calls = []
    unavailable = False
    documents = {
        "/data/wow/playable-class/index": {"classes": [{"id": 8, "name": "Mage"}]},
        "/data/wow/playable-class/8": {"id": 8, "name": "Mage"},
        "/data/wow/playable-specialization/index": {
            "character_specializations": [{"id": 64, "name": "Frost"}]
        },
        "/data/wow/playable-specialization/64": {
            "id": 64,
            "name": "Frost",
            "playable_class": {"id": 8},
        },
        "/data/wow/profession/index": {"professions": [{"id": 186, "name": "Mining"}]},
        "/data/wow/profession/186": {
            "id": 186,
            "name": "Mining",
            "type": {"type": "PRIMARY"},
        },
        "/data/wow/journal-instance/index": {"instances": []},
    }

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/token":
            return httpx.Response(
                200, json={"access_token": "synthetic", "expires_in": 3600}
            )
        if unavailable:
            return httpx.Response(503)
        return httpx.Response(200, json=documents[request.url.path])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        service = ReferencesService(
            BlizzardClient(BlizzardSettings("test", "test"), references, http)
        )
        for category in ("classes", "professions", "dungeons"):
            await service.refresh(category)
        snapshot = await service.snapshot()
        assert [c.id for c in snapshot.classes if c.active] == ["mage"]
        mage = next(c for c in snapshot.classes if c.id == "mage")
        assert [s.id for s in mage.specs if s.active] == ["mage-frost"]
        assert [p.id for p in snapshot.professions if p.active] == ["mining"]
        assert not any(d.active for d in snapshot.dungeons)
        assert all(snapshot.fetched_at.values())
        assert not snapshot.refreshing
        count = len(calls)
        restarted = ReferencesService(
            BlizzardClient(BlizzardSettings("test", "test"), references, http)
        )
        await restarted.refresh("classes")
        assert len(calls) == count
        async with references.database.transaction() as connection:
            await connection.execute(
                """UPDATE reference_cache SET expires_at = now() - interval '1 second'"""
            )
        unavailable = True
        await restarted.refresh("classes")
        after = await restarted.snapshot()
        assert [c.id for c in after.classes if c.active] == ["mage"]
        assert after.fetched_at["classes"] == snapshot.fetched_at["classes"]
        await restarted.close()
        await service.close()

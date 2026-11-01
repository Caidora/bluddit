"""Provider and catalog behavior with synthetic HTTP; no credentials/network required."""

import asyncio
from datetime import timedelta
import logging
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

from bluddit_api.models.references import CachedDocument, ReferenceEntity
from bluddit_api.models.bluds import BludPatch
from bluddit_api.routes.bluds import present, validate_values
from bluddit_api.services.blizzard import (
    BlizzardClient,
    BlizzardSettings,
    ProviderUnavailable,
    utcnow,
)
from bluddit_api.services.references import ReferencesService

pytestmark = pytest.mark.anyio


class MemoryRepository:
    """Isolated persistence fake; SQL leases/publication are tested against PostgreSQL."""

    def __init__(self):
        self.documents = {}
        self.leases = {}
        self.rows = []

    async def cached(self, key):
        return self.documents.get(key)

    async def claim(self, key):
        document = self.documents.get(key)
        if (
            key in self.leases
            or document
            and (
                document.retry_at
                and document.retry_at > utcnow()
                or document.expires_at
                and document.expires_at > utcnow()
            )
        ):
            return None
        self.leases[key] = uuid4()
        return self.leases[key]

    async def finish(self, key, token, document):
        assert self.leases.pop(key) == token
        self.documents[key] = CachedDocument(
            document=document,
            fetched_at=utcnow(),
            expires_at=utcnow() + timedelta(hours=1),
            retry_at=None,
        )

    async def fail(self, key, token, retry_seconds):
        assert self.leases.pop(key) == token
        previous = self.documents.get(key)
        self.documents[key] = CachedDocument(
            document=previous.document if previous else None,
            fetched_at=previous.fetched_at if previous else None,
            expires_at=previous.expires_at if previous else None,
            retry_at=utcnow() + timedelta(seconds=retry_seconds),
        )

    async def entities(self):
        return self.rows

    async def publish(self, key, token, kinds, entities):
        for row in self.rows:
            if row.entity_kind in kinds:
                row.active = False
        self.rows = [
            row
            for row in self.rows
            if (row.entity_kind, row.reference_id)
            not in {(e.entity_kind, e.reference_id) for e in entities}
        ] + entities
        await self.finish(key, token, {"published": True})


def make_client(handler, repository=None):
    return BlizzardClient(
        BlizzardSettings("synthetic-id", "synthetic-secret"),
        repository or MemoryRepository(),
        httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


def respond(request, body):
    if request.url.path == "/token":
        assert request.headers["authorization"].startswith("Basic ")
        return httpx.Response(
            200, json={"access_token": "synthetic-token", "expires_in": 3600}
        )
    assert request.url.host == "us.api.blizzard.com"
    assert request.url.params["namespace"] == "static-1.60.1_70399-forever-us"
    assert request.url.params["locale"] == "en_US"
    return httpx.Response(200, json=body)


async def test_document_cache_is_one_hour_and_survives_client_restart():
    requests = []

    def handler(request):
        requests.append(request.url.path)
        return respond(request, {"id": 8, "name": "Synthetic mage"})

    repo = MemoryRepository()
    client = make_client(handler, repo)
    await client.document("/data/wow/playable-class/8")
    await client.document("/data/wow/playable-class/8")
    other = make_client(handler, repo)
    await other.document("/data/wow/playable-class/8")
    assert requests == ["/token", "/data/wow/playable-class/8"]
    key = client.key("document", "/data/wow/playable-class/8", page=1)
    cached = repo.documents[key]
    assert 3599 < (cached.expires_at - cached.fetched_at).total_seconds() <= 3601
    cached.expires_at = utcnow()
    await other.document("/data/wow/playable-class/8")
    assert requests.count("/data/wow/playable-class/8") == 2
    assert client.key("document", "/data/wow/playable-class/8", page=2) != key
    await client.http.aclose()
    await other.http.aclose()


async def test_oauth_renewal_retries_401_once():
    tokens, gets = 0, 0

    def handler(request):
        nonlocal tokens, gets
        if request.url.path == "/token":
            tokens += 1
            return respond(request, {})
        gets += 1
        if gets == 1:
            return httpx.Response(401)
        return respond(request, {"id": 8, "name": "Synthetic mage"})

    client = make_client(handler)
    await client.document("/data/wow/playable-class/8")
    assert (tokens, gets) == (2, 2)
    client._expires = 0
    await client.document("/data/wow/playable-class/9")
    assert tokens == 3
    await client.http.aclose()


@pytest.mark.parametrize(
    "failure",
    ["429", "403", "404", "500", "timeout", "malformed", "bad-parent", "bad-level"],
)
async def test_failed_get_never_replaces_cached_document(failure):
    def handler(request):
        if request.url.path == "/token":
            return respond(request, {})
        if failure.isdigit():
            return httpx.Response(int(failure), headers={"Retry-After": "180"})
        if failure == "timeout":
            raise httpx.ReadTimeout("synthetic")
        body = {"id": 1, "name": "Synthetic", "playable_class": {"id": 8}}
        if failure == "malformed":
            body = {"error": "missing identity"}
        if failure == "bad-parent":
            body["playable_class"] = "invalid"
        if failure == "bad-level":
            body["minimum_level"] = "invalid"
        return respond(request, body)

    client = make_client(handler)
    key = client.key("document", "/data/wow/playable-specialization/1", page=1)
    old = CachedDocument(
        document={"id": 1, "name": "Old"},
        fetched_at=utcnow() - timedelta(hours=2),
        expires_at=utcnow() - timedelta(hours=1),
        retry_at=None,
    )
    client.repository.documents[key] = old
    with pytest.raises((ProviderUnavailable, httpx.ReadTimeout, ValueError)):
        await client.document("/data/wow/playable-specialization/1")
    assert client.repository.documents[key].document == old.document
    assert client.repository.documents[key].fetched_at == old.fetched_at
    if failure == "429":
        assert (
            client.repository.documents[key].retry_at - utcnow()
        ).total_seconds() > 179
    await client.http.aclose()


async def test_pagination_and_duplicate_identity_rejection():
    duplicate = False

    def handler(request):
        page = int(request.url.params.get("_page", "1"))
        return respond(
            request,
            {
                "classes": [{"id": 1 if duplicate else page, "name": "Synthetic"}],
                "pageCount": 2,
            },
        )

    client = make_client(handler)
    assert len(await client.index("/data/wow/playable-class/index", "classes")) == 2
    client.repository.documents.clear()
    duplicate = True
    with pytest.raises(ValueError, match="Duplicate"):
        await client.index("/data/wow/playable-class/index", "classes")
    await client.http.aclose()


async def test_atomic_catalog_add_rename_retire_and_ambiguous_wings():
    documents = {
        "/data/wow/journal-instance/index": {
            "instances": [
                {"id": 10, "name": "Synthetic dungeon"},
                {"id": 11, "name": "Synthetic raid"},
            ]
        },
        "/data/wow/journal-instance/10": {
            "id": 10,
            "name": "Synthetic dungeon",
            "category": {"type": "DUNGEON"},
        },
        "/data/wow/journal-instance/11": {
            "id": 11,
            "name": "Synthetic raid",
            "category": {"type": "RAID"},
        },
    }
    client = make_client(
        lambda request: respond(request, documents.get(request.url.path, {}))
    )
    client.repository.rows = [
        ReferenceEntity(
            entity_kind="dungeon",
            reference_id="old-wing",
            blizzard_id=None,
            payload={"name": "Synthetic dungeon - wing"},
        )
    ]
    service = ReferencesService(client)
    await service.refresh("dungeons")
    snapshot = await service.snapshot()
    active = [d for d in snapshot.dungeons if d.active]
    assert [d.id for d in active] == ["blizzard-dungeon-10"]
    assert active[0].suggested_level_min is None and active[0].location is None
    assert not snapshot.dungeons[0].active
    await service.close()
    client.repository.documents.clear()
    documents["/data/wow/journal-instance/10"]["name"] = "Renamed"
    await service.refresh("dungeons")
    assert (
        next(e for e in client.repository.rows if e.blizzard_id == 10).reference_id
        == "blizzard-dungeon-10"
    )
    client.repository.documents.clear()
    documents["/data/wow/journal-instance/index"] = {"instances": []}
    await service.refresh("dungeons")
    assert not any(e.active for e in client.repository.rows)
    await client.http.aclose()


async def test_failure_and_malformed_category_preserve_last_snapshot(caplog):
    client = make_client(lambda request: httpx.Response(403))
    client.repository.rows = [
        ReferenceEntity(
            entity_kind="dungeon",
            reference_id="known",
            blizzard_id=1,
            active=True,
            payload={"name": "Known"},
        )
    ]
    service = ReferencesService(client)
    with caplog.at_level(logging.WARNING):
        await service.refresh("dungeons")
    assert client.repository.rows[0].active
    assert "synthetic-secret" not in caplog.text
    assert "synthetic-token" not in caplog.text
    assert (
        client.repository.documents[client.key("catalog", "dungeons")].retry_at
        > utcnow()
    )
    await client.http.aclose()


async def test_concurrent_requests_schedule_one_refresh_and_shutdown_cancels():
    client = make_client(lambda request: respond(request, {}))
    service = ReferencesService(client)
    started = asyncio.Event()

    async def slow(category):
        started.set()
        await asyncio.Event().wait()

    service.refresh = AsyncMock(side_effect=slow)
    first, second = await asyncio.gather(service.snapshot(), service.snapshot())
    assert first.classes == second.classes == []
    await started.wait()
    assert len(service.tasks) == 3
    assert service.refresh.await_count == 3
    await service.close()
    await client.http.aclose()


async def test_unknown_profession_type_and_missing_cap_are_not_fabricated():
    client = make_client(
        lambda request: respond(
            request,
            {"professions": [{"id": 1, "name": "Synthetic profession"}]}
            if request.url.path.endswith("index")
            else {"id": 1, "name": "Synthetic profession"},
        )
    )
    service = ReferencesService(client)
    entries = await service.fetch("professions", [])
    assert entries[0].payload == {
        "name": "Synthetic profession",
        "category": None,
        "max_level": None,
    }
    await client.http.aclose()


def test_retired_assignments_and_progress_are_preserved_but_not_reassigned():
    from test_bluds import CONTENT
    from reference_data import REFERENCES
    from bluddit_api.models.bluds import BludRecord

    refs = REFERENCES.model_copy(deep=True)
    for group in [refs.classes, refs.professions, refs.dungeons]:
        for entry in group:
            entry.active = False
    record = BludRecord(
        **CONTENT,
        blud_id=1,
        account_id=1,
        owner_name="Synthetic",
        spec_id=None,
        archived=False,
        created_at=utcnow(),
        updated_at=utcnow(),
        updated_by_account_id=1,
        professions=[{"profession_id": "mining", "level": 400, "updated_at": utcnow()}],
        dungeons=[
            {
                "dungeon_id": "ragefire-chasm",
                "status": "completed",
                "updated_at": utcnow(),
            }
        ],
    )
    validate_values(BludPatch(name="Changed"), refs, record)
    validate_values(
        BludPatch(professions=[{"profession_id": "mining", "level": 400}]), refs, record
    )
    validate_values(BludPatch(professions=[]), refs, record)
    with pytest.raises(Exception) as denied:
        validate_values(
            BludPatch(professions=[{"profession_id": "mining", "level": 100}]),
            refs,
            record,
        )
    assert denied.value.status_code == 422
    assert present(record, refs).total_dungeons == 0
    assert len(present(record, refs).dungeons) == 1
    # A changed provider relationship must not prevent unrelated member edits.
    record.spec_id = "mage-frost"
    next(c for c in refs.classes if c.id == "mage").specs = []
    validate_values(BludPatch(archived=True), refs, record)


@pytest.fixture
def clean_provider_env(monkeypatch):
    import os

    for key in os.environ:
        if key.startswith(("BATTLE_NET_", "BLIZZARD_")):
            monkeypatch.delenv(key)
    return monkeypatch


def test_catalog_uses_existing_battlenet_app_credentials(clean_provider_env):
    clean_provider_env.setenv("BATTLE_NET_CLIENT_ID", "existing-app")
    clean_provider_env.setenv("BATTLE_NET_CLIENT_SECRET", "existing-secret")
    settings = BlizzardSettings.from_env()
    assert settings.enabled
    assert (settings.client_id, settings.client_secret) == (
        "existing-app",
        "existing-secret",
    )


def test_catalog_uses_production_secret_files_even_with_empty_override_file(
    clean_provider_env, tmp_path
):
    for name, value in [
        ("BATTLE_NET_CLIENT_ID", "existing-app"),
        ("BATTLE_NET_CLIENT_SECRET", "existing-secret"),
        ("BLIZZARD_CLIENT_SECRET", ""),
    ]:
        path = tmp_path / name
        path.write_text(value)
        clean_provider_env.setenv(name + "_FILE", str(path))
    settings = BlizzardSettings.from_env()
    assert settings.enabled and settings.client_id == "existing-app"
    assert settings.client_secret == "existing-secret"


def test_explicit_catalog_pair_overrides_signin_credentials(clean_provider_env):
    clean_provider_env.setenv("BLIZZARD_CLIENT_ID", "catalog-app")
    clean_provider_env.setenv("BLIZZARD_CLIENT_SECRET", "catalog-secret")
    clean_provider_env.setenv("BATTLE_NET_CLIENT_SECRET_FILE", "/must-not-be-read")
    settings = BlizzardSettings.from_env()
    assert (settings.client_id, settings.client_secret) == (
        "catalog-app",
        "catalog-secret",
    )


def test_catalog_is_disabled_without_any_credentials(clean_provider_env):
    assert not BlizzardSettings.from_env().enabled


@pytest.mark.parametrize("name", ["BLIZZARD_CLIENT_ID", "BLIZZARD_CLIENT_SECRET"])
def test_partial_catalog_override_does_not_mix_credential_pairs(
    clean_provider_env, name
):
    clean_provider_env.setenv("BATTLE_NET_CLIENT_ID", "existing-app")
    clean_provider_env.setenv("BATTLE_NET_CLIENT_SECRET", "existing-secret")
    clean_provider_env.setenv(name, "partial-override")
    with pytest.raises(RuntimeError, match="complete"):
        BlizzardSettings.from_env()


async def test_live_forever_empty_journal_shape_is_normalized_and_cached():
    body = {
        "_links": {
            "self": {
                "href": "https://us.api.blizzard.com/data/wow/journal-instance/?namespace=static-1.60.1_70399-forever-us"
            }
        }
    }
    client = make_client(lambda request: respond(request, body))
    service = ReferencesService(client)
    await service.refresh("dungeons")
    cached = await client.repository.cached(client.key("catalog", "dungeons"))
    assert cached.document == {"published": True}
    assert cached.fetched_at is not None
    await client.http.aclose()


@pytest.mark.parametrize(
    "body",
    [{}, {"_links": {}}, {"_links": {"self": {"href": "https://example.com/wrong"}}}],
)
async def test_missing_journal_collection_still_rejects_malformed_responses(body):
    client = make_client(lambda request: respond(request, body))
    with pytest.raises(ValueError, match="Missing provider collection"):
        await client.index("/data/wow/journal-instance/index", "instances")
    await client.http.aclose()


async def test_blizzard_internal_test_profession_is_not_selectable():
    client = make_client(
        lambda request: respond(
            request,
            {"professions": [{"id": 1, "name": "Test Profession [DNT]"}]}
            if request.url.path.endswith("index")
            else {
                "id": 1,
                "name": "Test Profession [DNT]",
                "type": {"type": "PRIMARY"},
            },
        )
    )
    assert await ReferencesService(client).fetch("professions", []) == []
    await client.http.aclose()

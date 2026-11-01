"""One catalog for selectors, validation and historical labels across features."""

import asyncio
import hashlib
import json
import logging

from bluddit_api.models.bluds import (
    BludReferenceData,
    Choice,
    ClassReference,
    DungeonReference,
    ProfessionReference,
    ReferenceSource,
)
from bluddit_api.models.references import ReferenceEntity
from bluddit_api.services.blizzard import BlizzardClient, utcnow

logger = logging.getLogger(__name__)
CATEGORIES = {
    "classes": ["class", "spec"],
    "professions": ["profession"],
    "dungeons": ["dungeon"],
}


def identity(kind, detail, existing, parent_id=None):
    matched = next(
        (
            e
            for e in existing
            if e.entity_kind == kind and e.blizzard_id == detail["id"]
        ),
        None,
    )
    if matched:
        return matched.reference_id
    # A one-time exact English-name match preserves legacy IDs. Never fuzzy-match
    # wings, generate IDs from labels, or remap an established Blizzard identity.
    candidates = [
        e
        for e in existing
        if e.entity_kind == kind
        and e.blizzard_id is None
        and e.payload["name"] == detail["name"]
        and (kind != "spec" or e.payload.get("class_id") == parent_id)
    ]
    return (
        candidates[0].reference_id
        if len(candidates) == 1
        else f"blizzard-{kind}-{detail['id']}"
    )


def positive_number(value):
    if value is None:
        return None
    if type(value) is not int or value < 0:
        raise ValueError("Invalid provider level")
    return value


class ReferencesService:
    def __init__(self, client: BlizzardClient):
        self.client = client
        self.repository = client.repository
        self.tasks: dict[str, asyncio.Task] = {}
        self.failures: dict[str, int] = {}

    async def close(self):
        for task in self.tasks.values():
            task.cancel()
        await asyncio.gather(*self.tasks.values(), return_exceptions=True)

    async def snapshot(self) -> BludReferenceData:
        entries = await self.repository.entities()
        fetched = {}
        for category in CATEGORIES:
            cached = await self.repository.cached(self.client.key("catalog", category))
            fetched[category] = cached.fetched_at if cached else None
            due = (
                cached is None
                or cached.expires_at is None
                or cached.expires_at <= utcnow()
            )
            waiting = cached and cached.retry_at and cached.retry_at > utcnow()
            if (
                self.client.settings.enabled
                and due
                and not waiting
                and category not in self.tasks
            ):
                task = asyncio.create_task(self.refresh(category))
                self.tasks[category] = task
                task.add_done_callback(
                    lambda _, category=category: self.tasks.pop(category, None)
                )
        specs = [
            Choice(id=e.reference_id, name=e.payload["name"], active=e.active)
            for e in entries
            if e.entity_kind == "spec"
        ]
        classes = []
        for entity in entries:
            if entity.entity_kind == "class":
                child_ids = {
                    e.reference_id
                    for e in entries
                    if e.entity_kind == "spec"
                    and e.payload.get("class_id") == entity.reference_id
                }
                classes.append(
                    ClassReference(
                        id=entity.reference_id,
                        name=entity.payload["name"],
                        active=entity.active,
                        specs=[s for s in specs if s.id in child_ids],
                    )
                )
        professions = [
            ProfessionReference(id=e.reference_id, active=e.active, **e.payload)
            for e in entries
            if e.entity_kind == "profession"
        ]
        dungeons = [
            DungeonReference(id=e.reference_id, active=e.active, **e.payload)
            for e in entries
            if e.entity_kind == "dungeon"
        ]
        content = {"classes": classes, "professions": professions, "dungeons": dungeons}
        digest = hashlib.sha256(
            json.dumps(
                {
                    k: [v.model_dump(mode="json") for v in values]
                    for k, values in content.items()
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()[:16]
        return BludReferenceData(
            version=digest,
            refreshing=bool(self.tasks),
            fetched_at=fetched,
            sources=[
                ReferenceSource(
                    label="Blizzard Game Data API",
                    url="https://develop.battle.net/documentation/world-of-warcraft/game-data-apis",
                )
            ],
            **content,
            max_primary_professions=2,
            dungeon_statuses=[
                Choice(id="not_completed", name="Not completed"),
                Choice(id="completed", name="Completed"),
                Choice(id="completed_rerun", name="Completed — looking to rerun"),
            ],
        )

    async def refresh(self, category: str):
        key = self.client.key("catalog", category)
        token = None
        try:
            token = await self.repository.claim(key)
            if token is None:
                return
            async with asyncio.timeout(90):
                entities = await self.fetch(category, await self.repository.entities())
            await self.repository.publish(key, token, CATEGORIES[category], entities)
            self.failures[category] = 0
        except asyncio.CancelledError:
            if token:
                await self.repository.fail(key, token, 5)
            raise
        except Exception as error:
            # Exception messages may include URLs or headers: log only the safe category/type.
            logger.warning(
                "Blizzard catalog refresh failed: %s (%s)",
                category,
                type(error).__name__,
            )
            count = self.failures.get(category, 0) + 1
            self.failures[category] = count
            if token:
                try:
                    await self.repository.fail(
                        key,
                        token,
                        max(
                            getattr(error, "retry_seconds", 0),
                            min(3600, 30 * 2 ** min(count, 7)),
                        ),
                    )
                except Exception:
                    logger.warning(
                        "Could not release Blizzard catalog lease: %s", category
                    )

    async def fetch(
        self, category: str, existing: list[ReferenceEntity]
    ) -> list[ReferenceEntity]:
        result = []

        def add(kind, detail, **payload):
            ref_id = identity(kind, detail, existing, payload.get("class_id"))
            result.append(
                ReferenceEntity(
                    entity_kind=kind,
                    reference_id=ref_id,
                    blizzard_id=detail["id"],
                    active=True,
                    payload={"name": detail["name"], **payload},
                )
            )
            return ref_id

        if category == "classes":
            classes = await self.client.details("/data/wow/playable-class", "classes")
            class_ids = {d["id"]: add("class", d) for d in classes}
            specs = await self.client.details(
                "/data/wow/playable-specialization", "character_specializations"
            )
            for detail in specs:
                parent = detail.get("playable_class", {}).get("id")
                if parent not in class_ids:
                    raise ValueError("Specialization has no class")
                add("spec", detail, class_id=class_ids[parent])
        elif category == "professions":
            for detail in await self.client.details(
                "/data/wow/profession", "professions"
            ):
                if detail["name"] == "Test Profession [DNT]":
                    continue
                category_type = (detail.get("type") or {}).get("type")
                profession_type = {"PRIMARY": "primary", "SECONDARY": "secondary"}.get(
                    category_type
                )
                add(
                    "profession",
                    detail,
                    category=profession_type,
                    max_level=positive_number(detail.get("maximum_skill_level")),
                )
        elif category == "dungeons":
            for detail in await self.client.details(
                "/data/wow/journal-instance", "instances"
            ):
                kind = detail.get("category", {}).get("type")
                if kind == "RAID":
                    continue
                if kind != "DUNGEON":
                    raise ValueError("Unclassified journal instance")
                minimum = positive_number(detail.get("minimum_level"))
                maximum = positive_number(detail.get("maximum_level"))
                if minimum is not None and maximum is not None and minimum > maximum:
                    raise ValueError("Invalid dungeon range")
                add(
                    "dungeon",
                    detail,
                    location=None,
                    suggested_level_min=minimum,
                    suggested_level_max=maximum,
                    source_urls=[
                        f"https://{self.client.settings.region}.api.blizzard.com/data/wow/journal-instance/{detail['id']}?namespace={self.client.settings.namespace}&locale={self.client.settings.locale}"
                    ],
                )
        return result

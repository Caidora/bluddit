"""Durable cache leases and atomic publication of complete catalog categories."""

from uuid import UUID, uuid4

from psycopg.rows import class_row
from psycopg.types.json import Jsonb

from bluddit_api.database import Database
from bluddit_api.models.references import CachedDocument, CacheLease, ReferenceEntity


class ReferencesRepository:
    def __init__(self, database: Database):
        self.database = database

    async def cached(self, key: str) -> CachedDocument | None:
        async with self.database.transaction() as connection:
            cursor = await connection.execute(
                """
                SELECT document, fetched_at, expires_at, retry_at
                FROM reference_cache WHERE cache_key = %(key)s
                """,
                {"key": key},
            )
            cursor.row_factory = class_row(CachedDocument)
            return await cursor.fetchone()

    async def claim(self, key: str) -> UUID | None:
        async with self.database.transaction() as connection:
            cursor = await connection.execute(
                """
                INSERT INTO reference_cache (cache_key, lease_token, lease_until)
                VALUES (%(key)s, %(token)s, now() + interval '120 seconds')
                ON CONFLICT (cache_key) DO UPDATE SET
                    lease_token = EXCLUDED.lease_token, lease_until = EXCLUDED.lease_until
                WHERE (reference_cache.lease_until IS NULL OR reference_cache.lease_until < now())
                  AND (reference_cache.retry_at IS NULL OR reference_cache.retry_at <= now())
                  AND (reference_cache.expires_at IS NULL OR reference_cache.expires_at <= now())
                RETURNING lease_token
                """,
                {"key": key, "token": uuid4()},
            )
            cursor.row_factory = class_row(CacheLease)
            row = await cursor.fetchone()
            return row.lease_token if row else None

    async def finish(self, key: str, token: UUID, document: dict) -> None:
        async with self.database.transaction() as connection:
            await connection.execute(
                """
                UPDATE reference_cache SET document = %(document)s, fetched_at = now(),
                    expires_at = now() + interval '1 hour', retry_at = NULL,
                    lease_token = NULL, lease_until = NULL
                WHERE cache_key = %(key)s AND lease_token = %(token)s
                """,
                {"key": key, "token": token, "document": Jsonb(document)},
            )

    async def fail(self, key: str, token: UUID, retry_seconds: int) -> None:
        async with self.database.transaction() as connection:
            await connection.execute(
                """
                UPDATE reference_cache SET lease_token = NULL, lease_until = NULL,
                    retry_at = now() + make_interval(secs => %(seconds)s)
                WHERE cache_key = %(key)s AND lease_token = %(token)s
                """,
                {"key": key, "token": token, "seconds": retry_seconds},
            )

    async def entities(self) -> list[ReferenceEntity]:
        async with self.database.transaction() as connection:
            cursor = await connection.execute(
                """
                SELECT entity_kind, reference_id, blizzard_id, payload, active
                FROM reference_entities ORDER BY entity_kind, reference_id
                """
            )
            cursor.row_factory = class_row(ReferenceEntity)
            return await cursor.fetchall()

    async def publish(
        self, key: str, token: UUID, kinds: list[str], entities: list[ReferenceEntity]
    ) -> None:
        async with self.database.transaction() as connection:
            cursor = await connection.execute(
                """
                SELECT lease_token FROM reference_cache
                WHERE cache_key = %(key)s AND lease_token = %(token)s
                FOR UPDATE
                """,
                {"key": key, "token": token},
            )
            if await cursor.fetchone() is None:
                return
            await connection.execute(
                """
                UPDATE reference_entities SET active = false
                WHERE entity_kind = ANY(%(kinds)s)
                """,
                {"kinds": kinds},
            )
            for entity in entities:
                await connection.execute(
                    """
                    INSERT INTO reference_entities
                        (entity_kind, reference_id, blizzard_id, payload, active)
                    VALUES (%(kind)s, %(id)s, %(blizzard_id)s, %(payload)s, true)
                    ON CONFLICT (entity_kind, reference_id) DO UPDATE SET
                        blizzard_id = EXCLUDED.blizzard_id, payload = EXCLUDED.payload, active = true
                    """,
                    {
                        "kind": entity.entity_kind,
                        "id": entity.reference_id,
                        "blizzard_id": entity.blizzard_id,
                        "payload": Jsonb(entity.payload),
                    },
                )
            await connection.execute(
                """
                UPDATE reference_cache SET document = '{"published": true}'::jsonb,
                    fetched_at = now(), expires_at = now() + interval '1 hour',
                    retry_at = NULL, lease_token = NULL, lease_until = NULL
                WHERE cache_key = %(key)s AND lease_token = %(token)s
                """,
                {"key": key, "token": token},
            )

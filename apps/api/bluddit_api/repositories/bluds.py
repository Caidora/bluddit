"""Simple last-write-wins Bluds persistence; no revisions or row locks."""

from psycopg.rows import class_row

from bluddit_api.database import Database
from bluddit_api.models.bluds import BludCreate, BludFilter, BludPatch, BludRecord


class BludsRepository:
    def __init__(self, database: Database):
        self.database = database

    async def list_bluds(self, filters: BludFilter, actor_id: int) -> list[BludRecord]:
        async with self.database.transaction() as connection:
            cursor = await connection.execute(
                """
                SELECT b.blud_id, b.account_id, b.owner_name, b.name, b.class_id,
                    b.spec_id, b.character_created_on, b.archived, b.created_at, b.updated_at,
                    b.updated_by_account_id, b.professions, b.dungeons
                FROM blud_records b
                WHERE b.archived = %(archived)s
                  AND (NOT %(mine)s OR b.account_id = %(actor_id)s)
                  AND strpos(lower(b.name || ' ' || b.owner_name), lower(%(q)s)) > 0
                  AND (%(class_id)s::text IS NULL OR b.class_id = %(class_id)s)
                  AND (%(profession_id)s::text IS NULL OR EXISTS (
                      SELECT 1 FROM blud_professions p
                      WHERE p.blud_id = b.blud_id AND p.profession_id = %(profession_id)s))
                  AND (%(dungeon_id)s::text IS NULL OR COALESCE((
                      SELECT d.status FROM blud_dungeons d
                      WHERE d.blud_id = b.blud_id AND d.dungeon_id = %(dungeon_id)s
                  ), 'not_completed') = %(dungeon_status)s)
                ORDER BY lower(b.name), b.blud_id
                LIMIT %(fetch_limit)s OFFSET %(offset)s
                """,
                {
                    "archived": filters.archived,
                    "mine": filters.mine,
                    "q": filters.q.strip(),
                    "class_id": filters.class_id,
                    "profession_id": filters.profession_id,
                    "dungeon_id": filters.dungeon_id,
                    "dungeon_status": filters.dungeon_status,
                    "actor_id": actor_id,
                    "fetch_limit": filters.limit + 1,
                    "offset": filters.offset,
                },
            )
            cursor.row_factory = class_row(BludRecord)
            return await cursor.fetchall()

    async def get(self, blud_id: int) -> BludRecord | None:
        async with self.database.transaction() as connection:
            cursor = await connection.execute(
                """
                SELECT blud_id, account_id, owner_name, name, class_id, spec_id,
                    character_created_on,
                    archived, created_at, updated_at, updated_by_account_id,
                    professions, dungeons
                FROM blud_records WHERE blud_id = %(blud_id)s
                """,
                {"blud_id": blud_id},
            )
            cursor.row_factory = class_row(BludRecord)
            return await cursor.fetchone()

    async def create(self, body: BludCreate, actor_id: int) -> BludRecord:
        async with self.database.transaction() as connection:
            cursor = await connection.execute(
                """
                INSERT INTO bluds (account_id, name, class_id, spec_id,
                    character_created_on,
                    updated_by_account_id)
                VALUES (%(actor_id)s, %(name)s, %(class_id)s, %(spec_id)s,
                    %(character_created_on)s,
                    %(actor_id)s)
                RETURNING blud_id
                """,
                {
                    "name": body.name,
                    "class_id": body.class_id,
                    "spec_id": body.spec_id,
                    "character_created_on": body.character_created_on,
                    "actor_id": actor_id,
                },
            )
            row = await cursor.fetchone()
            assert row is not None
            cursor = await connection.execute(
                """
                SELECT blud_id, account_id, owner_name, name, class_id, spec_id,
                    character_created_on,
                    archived, created_at, updated_at, updated_by_account_id,
                    professions, dungeons
                FROM blud_records WHERE blud_id = %(blud_id)s
                """,
                {"blud_id": row[0]},
            )
            cursor.row_factory = class_row(BludRecord)
            result = await cursor.fetchone()
            assert result is not None
            return result

    async def update(
        self, blud_id: int, body: BludPatch, actor_id: int, can_correct: bool
    ) -> BludRecord | None:
        parameters = {
            "name": body.name,
            "class_id": body.class_id,
            "spec_id": body.spec_id,
            "character_created_on": body.character_created_on,
            "archived": body.archived,
            "set_name": "name" in body.model_fields_set,
            "set_class_id": "class_id" in body.model_fields_set,
            "set_spec_id": "spec_id" in body.model_fields_set,
            "set_character_created_on": "character_created_on" in body.model_fields_set,
            "set_archived": "archived" in body.model_fields_set,
            "blud_id": blud_id,
            "actor_id": actor_id,
            "can_correct": can_correct,
        }
        async with self.database.transaction() as connection:
            cursor = await connection.execute(
                """
                UPDATE bluds SET
                    name = CASE WHEN %(set_name)s THEN %(name)s ELSE name END,
                    class_id = CASE WHEN %(set_class_id)s THEN %(class_id)s ELSE class_id END,
                    spec_id = CASE WHEN %(set_spec_id)s THEN %(spec_id)s ELSE spec_id END,
                    character_created_on = CASE WHEN %(set_character_created_on)s
                        THEN %(character_created_on)s::date ELSE character_created_on END,
                    archived = CASE WHEN %(set_archived)s THEN %(archived)s ELSE archived END,
                    updated_at = now(), updated_by_account_id = %(actor_id)s
                WHERE blud_id = %(blud_id)s AND (account_id = %(actor_id)s OR %(can_correct)s)
                RETURNING blud_id
                """,
                parameters,
            )
            if await cursor.fetchone() is None:
                return None
            if body.professions is not None:
                await connection.execute(
                    """
                    DELETE FROM blud_professions
                    WHERE blud_id = %(blud_id)s AND NOT (profession_id = ANY(%(ids)s))
                    """,
                    {
                        "blud_id": blud_id,
                        "ids": [p.profession_id for p in body.professions],
                    },
                )
                for profession in body.professions:
                    await connection.execute(
                        """
                        INSERT INTO blud_professions (blud_id, profession_id, level)
                        VALUES (%(blud_id)s, %(profession_id)s, %(level)s)
                        ON CONFLICT (blud_id, profession_id) DO UPDATE SET
                            level = EXCLUDED.level, updated_at = now()
                        WHERE blud_professions.level IS DISTINCT FROM EXCLUDED.level
                        """,
                        {
                            "blud_id": blud_id,
                            "profession_id": profession.profession_id,
                            "level": profession.level,
                        },
                    )
            if body.dungeons is not None:
                for dungeon in body.dungeons:
                    await connection.execute(
                        """
                        INSERT INTO blud_dungeons (blud_id, dungeon_id, status)
                        VALUES (%(blud_id)s, %(dungeon_id)s, %(status)s)
                        ON CONFLICT (blud_id, dungeon_id) DO UPDATE SET
                            status = EXCLUDED.status, updated_at = now()
                        WHERE blud_dungeons.status IS DISTINCT FROM EXCLUDED.status
                        """,
                        {
                            "blud_id": blud_id,
                            "dungeon_id": dungeon.dungeon_id,
                            "status": dungeon.status,
                        },
                    )
            cursor = await connection.execute(
                """
                SELECT blud_id, account_id, owner_name, name, class_id, spec_id,
                    character_created_on,
                    archived, created_at, updated_at, updated_by_account_id,
                    professions, dungeons
                FROM blud_records WHERE blud_id = %(blud_id)s
                """,
                {"blud_id": blud_id},
            )
            cursor.row_factory = class_row(BludRecord)
            return await cursor.fetchone()

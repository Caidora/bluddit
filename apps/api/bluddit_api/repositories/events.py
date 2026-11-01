"""Atomic event operations. Every management write locks the event first.

Section 12 roster writes must take the same lock before checking capacity.
"""

from datetime import datetime

from psycopg.rows import class_row

from bluddit_api.database import Database
from bluddit_api.models.events import EventCreate, EventFilter, EventPatch, EventRecord


class EventForbidden(Exception):
    pass


class EventCancelled(Exception):
    pass


class InvalidOrganizers(Exception):
    pass


class EventsRepository:
    def __init__(self, database: Database):
        self.database = database

    async def list_events(
        self, filters: EventFilter, actor_id: int
    ) -> list[EventRecord]:
        async with self.database.transaction() as connection:
            cursor = await connection.execute(
                """
                SELECT e.event_id, e.title, e.activity_type, e.dungeon_id, e.starts_at,
                       e.scheduling_timezone, e.duration_minutes, e.capacity, e.requirements,
                       e.state, e.created_by_account_id, e.updated_by_account_id,
                       e.created_at, e.updated_at, e.organizers
                FROM event_records e
                WHERE (%(state)s = 'all' OR e.state = %(state)s)
                  AND (%(period)s = 'all'
                    OR (%(period)s = 'upcoming' AND e.starts_at >= now())
                    OR (%(period)s = 'past' AND e.starts_at < now()))
                  AND (NOT %(mine)s OR EXISTS (SELECT 1 FROM event_organizers o
                       WHERE o.event_id = e.event_id AND o.account_id = %(actor_id)s))
                ORDER BY e.starts_at, e.event_id LIMIT %(limit)s OFFSET %(offset)s
                """,
                {
                    "state": filters.state,
                    "period": filters.period,
                    "mine": filters.mine,
                    "actor_id": actor_id,
                    "limit": filters.limit + 1,
                    "offset": filters.offset,
                },
            )
            cursor.row_factory = class_row(EventRecord)
            return await cursor.fetchall()

    async def get(self, event_id: int) -> EventRecord | None:
        async with self.database.transaction() as connection:
            cursor = await connection.execute(
                """
                SELECT e.event_id, e.title, e.activity_type, e.dungeon_id, e.starts_at,
                       e.scheduling_timezone, e.duration_minutes, e.capacity, e.requirements,
                       e.state, e.created_by_account_id, e.updated_by_account_id,
                       e.created_at, e.updated_at, e.organizers
                FROM event_records e WHERE e.event_id = %(event_id)s """,
                {"event_id": event_id},
            )
            cursor.row_factory = class_row(EventRecord)
            return await cursor.fetchone()

    async def create(
        self, body: EventCreate, starts_at: datetime, actor_id: int
    ) -> EventRecord:
        async with self.database.transaction() as connection:
            cursor = await connection.execute(
                """
                INSERT INTO events (title, activity_type, dungeon_id, starts_at,
                    scheduling_timezone, duration_minutes, capacity, requirements,
                    created_by_account_id, updated_by_account_id)
                VALUES (%(title)s, %(activity_type)s, %(dungeon_id)s, %(starts_at)s,
                    %(scheduling_timezone)s, %(duration_minutes)s, %(capacity)s,
                    %(requirements)s, %(actor_id)s, %(actor_id)s)
                RETURNING event_id
                """,
                {
                    "title": body.title,
                    "activity_type": body.activity_type,
                    "dungeon_id": body.dungeon_id,
                    "starts_at": starts_at,
                    "scheduling_timezone": body.scheduling_timezone,
                    "duration_minutes": body.duration_minutes,
                    "capacity": body.capacity,
                    "requirements": body.requirements,
                    "actor_id": actor_id,
                },
            )
            event_id = (await cursor.fetchone())[0]
            await connection.execute(
                """ INSERT INTO event_organizers (event_id, account_id)
                VALUES (%(event_id)s, %(actor_id)s) """,
                {"event_id": event_id, "actor_id": actor_id},
            )
            cursor = await connection.execute(
                """
                SELECT e.event_id, e.title, e.activity_type, e.dungeon_id, e.starts_at,
                       e.scheduling_timezone, e.duration_minutes, e.capacity, e.requirements,
                       e.state, e.created_by_account_id, e.updated_by_account_id,
                       e.created_at, e.updated_at, e.organizers
                FROM event_records e WHERE e.event_id = %(event_id)s """,
                {"event_id": event_id},
            )
            cursor.row_factory = class_row(EventRecord)
            return await cursor.fetchone()

    async def manage(
        self,
        event_id: int,
        actor_id: int,
        officer: bool,
        *,
        patch: EventPatch | None = None,
        starts_at: datetime | None = None,
        cancel: bool = False,
        organizer_ids: list[int] | None = None,
    ) -> EventRecord | None:
        async with self.database.transaction() as connection:
            # Separate lock statement ensures subsequent assignment reads see changes
            # committed by an assignment writer we waited for.
            cursor = await connection.execute(
                """ SELECT event_id FROM events WHERE event_id = %(event_id)s FOR UPDATE """,
                {"event_id": event_id},
            )
            if await cursor.fetchone() is None:
                return None
            cursor = await connection.execute(
                """
                SELECT e.event_id, e.title, e.activity_type, e.dungeon_id, e.starts_at,
                       e.scheduling_timezone, e.duration_minutes, e.capacity, e.requirements,
                       e.state, e.created_by_account_id, e.updated_by_account_id,
                       e.created_at, e.updated_at, e.organizers
                FROM event_records e WHERE e.event_id = %(event_id)s """,
                {"event_id": event_id},
            )
            cursor.row_factory = class_row(EventRecord)
            current = await cursor.fetchone()
            if not officer and not any(
                o.account_id == actor_id and o.active for o in current.organizers
            ):
                raise EventForbidden
            if organizer_ids is not None and not officer:
                raise EventForbidden
            if current.state == "cancelled":
                if cancel:
                    return current
                raise EventCancelled
            if organizer_ids is not None:
                cursor = await connection.execute(
                    """ SELECT id FROM accounts WHERE id = ANY(%(account_ids)s)
                    AND membership_state = 'active' ORDER BY id FOR SHARE """,
                    {"account_ids": organizer_ids},
                )
                if (
                    len(await cursor.fetchall()) != len(organizer_ids)
                    or not organizer_ids
                ):
                    raise InvalidOrganizers
                await connection.execute(
                    """ DELETE FROM event_organizers WHERE event_id = %(event_id)s """,
                    {"event_id": event_id},
                )
                for account_id in organizer_ids:
                    await connection.execute(
                        """ INSERT INTO event_organizers (event_id, account_id)
                        VALUES (%(event_id)s, %(account_id)s) """,
                        {"event_id": event_id, "account_id": account_id},
                    )
            if patch is not None:
                fields = patch.model_fields_set
                await connection.execute(
                    """ UPDATE events SET title = %(title)s, activity_type = %(activity_type)s,
                        dungeon_id = %(dungeon_id)s, starts_at = %(starts_at)s,
                        scheduling_timezone = %(scheduling_timezone)s,
                        duration_minutes = %(duration_minutes)s, capacity = %(capacity)s,
                        requirements = %(requirements)s
                    WHERE event_id = %(event_id)s """,
                    {
                        "title": patch.title if "title" in fields else current.title,
                        "activity_type": patch.activity_type
                        if "activity_type" in fields
                        else current.activity_type,
                        "dungeon_id": patch.dungeon_id
                        if "dungeon_id" in fields
                        else current.dungeon_id,
                        "starts_at": starts_at
                        if starts_at is not None
                        else current.starts_at,
                        "scheduling_timezone": patch.scheduling_timezone
                        if "scheduling_timezone" in fields
                        else current.scheduling_timezone,
                        "duration_minutes": patch.duration_minutes
                        if "duration_minutes" in fields
                        else current.duration_minutes,
                        "capacity": patch.capacity
                        if "capacity" in fields
                        else current.capacity,
                        "requirements": patch.requirements
                        if "requirements" in fields
                        else current.requirements,
                        "event_id": event_id,
                    },
                )
            await connection.execute(
                """ UPDATE events SET state = %(state)s, updated_at = now(),
                updated_by_account_id = %(actor_id)s WHERE event_id = %(event_id)s """,
                {
                    "state": "cancelled" if cancel else current.state,
                    "actor_id": actor_id,
                    "event_id": event_id,
                },
            )
            cursor = await connection.execute(
                """
                SELECT e.event_id, e.title, e.activity_type, e.dungeon_id, e.starts_at,
                       e.scheduling_timezone, e.duration_minutes, e.capacity, e.requirements,
                       e.state, e.created_by_account_id, e.updated_by_account_id,
                       e.created_at, e.updated_at, e.organizers
                FROM event_records e WHERE e.event_id = %(event_id)s """,
                {"event_id": event_id},
            )
            cursor.row_factory = class_row(EventRecord)
            return await cursor.fetchone()

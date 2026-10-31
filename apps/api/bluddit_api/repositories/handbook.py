"""Handbook persistence, atomic optimistic edits, and append-only history."""

from psycopg.errors import UniqueViolation
from psycopg.rows import class_row

from bluddit_api.database import Database
from bluddit_api.models.handbook import HandbookCreate, HandbookEdit, HandbookSection


class HandbookSlugExists(Exception):
    """A section already uses this stable slug."""


class StaleHandbookEdit(Exception):
    """Another officer saved a newer revision."""


class HandbookRepository:
    def __init__(self, database: Database):
        self.database = database

    async def create(
        self, section: HandbookCreate, author_account_id: int
    ) -> HandbookSection:
        try:
            async with self.database.transaction() as connection:
                await connection.execute(
                    """
                    INSERT INTO handbook_sections (slug, current_revision)
                    VALUES (%(slug)s, 1)
                    """,
                    {"slug": section.slug},
                )
                cursor = await connection.execute(
                    """
                    INSERT INTO handbook_revisions
                        (slug, revision, title, body, author_account_id)
                    VALUES (%(slug)s, 1, %(title)s, %(body)s, %(author_account_id)s)
                    RETURNING slug, revision, title, body, updated_at, author_account_id,
                        (SELECT display_name FROM accounts WHERE id = %(author_account_id)s) AS author_name
                    """,
                    {**section.model_dump(), "author_account_id": author_account_id},
                )
                cursor.row_factory = class_row(HandbookSection)
                result = await cursor.fetchone()
                assert result is not None
            return result
        except UniqueViolation as error:
            if error.diag.constraint_name == "handbook_sections_pkey":
                raise HandbookSlugExists from error
            raise

    async def list_sections(self, query: str) -> list[HandbookSection]:
        async with self.database.transaction() as connection:
            cursor = await connection.execute(
                """
                SELECT r.slug, r.revision, r.title, r.body, r.updated_at,
                       r.author_account_id, a.display_name AS author_name
                FROM handbook_sections s
                JOIN handbook_revisions r ON r.slug = s.slug AND r.revision = s.current_revision
                LEFT JOIN accounts a ON a.id = r.author_account_id
                WHERE strpos(lower(r.title || ' ' || r.body), lower(%(query)s)) > 0
                ORDER BY lower(r.title), s.slug
                """,
                {"query": query},
            )
            cursor.row_factory = class_row(HandbookSection)
            return await cursor.fetchall()

    async def get_section(self, slug: str) -> HandbookSection | None:
        async with self.database.transaction() as connection:
            cursor = await connection.execute(
                """
                SELECT r.slug, r.revision, r.title, r.body, r.updated_at,
                       r.author_account_id, a.display_name AS author_name
                FROM handbook_sections s
                JOIN handbook_revisions r ON r.slug = s.slug AND r.revision = s.current_revision
                LEFT JOIN accounts a ON a.id = r.author_account_id
                WHERE s.slug = %(slug)s
                """,
                {"slug": slug},
            )
            cursor.row_factory = class_row(HandbookSection)
            return await cursor.fetchone()

    async def revisions(
        self, slug: str, limit: int, offset: int
    ) -> list[HandbookSection]:
        async with self.database.transaction() as connection:
            cursor = await connection.execute(
                """
                SELECT r.slug, r.revision, r.title, r.body, r.updated_at,
                       r.author_account_id, a.display_name AS author_name
                FROM handbook_revisions r
                LEFT JOIN accounts a ON a.id = r.author_account_id
                WHERE r.slug = %(slug)s
                ORDER BY r.revision DESC LIMIT %(limit)s OFFSET %(offset)s
                """,
                {"slug": slug, "limit": limit, "offset": offset},
            )
            cursor.row_factory = class_row(HandbookSection)
            return await cursor.fetchall()

    async def edit(
        self, slug: str, edit: HandbookEdit, author_account_id: int
    ) -> HandbookSection | None:
        async with self.database.transaction() as connection:
            cursor = await connection.execute(
                """
                SELECT current_revision FROM handbook_sections
                WHERE slug = %(slug)s FOR UPDATE
                """,
                {"slug": slug},
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            if row[0] != edit.expected_revision:
                raise StaleHandbookEdit
            revision = row[0] + 1
            cursor = await connection.execute(
                """
                INSERT INTO handbook_revisions
                    (slug, revision, title, body, author_account_id)
                VALUES (%(slug)s, %(revision)s, %(title)s, %(body)s, %(author_account_id)s)
                RETURNING slug, revision, title, body, updated_at, author_account_id,
                    (SELECT display_name FROM accounts WHERE id = %(author_account_id)s) AS author_name
                """,
                {
                    "slug": slug,
                    "revision": revision,
                    "title": edit.title,
                    "body": edit.body,
                    "author_account_id": author_account_id,
                },
            )
            cursor.row_factory = class_row(HandbookSection)
            result = await cursor.fetchone()
            await connection.execute(
                """
                UPDATE handbook_sections SET current_revision = %(revision)s
                WHERE slug = %(slug)s
                """,
                {"slug": slug, "revision": revision},
            )
        return result

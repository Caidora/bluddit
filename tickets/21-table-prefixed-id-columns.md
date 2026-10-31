# 21: Table-prefixed ID columns

Status: Not started — deferred; do not implement with the documentation change

Dependencies: Ticket 03.

## Outcome

Bring existing bare `id` columns into the documented SQL naming convention:
singular table/entity name in snake_case followed by `_id`.

## Implementation

- Inspect the schema at implementation time for all remaining bare `id` columns.
  Currently known renames are:

  | Existing column | Target column |
  | --- | --- |
  | `accounts.id` | `accounts.account_id` |
  | `sessions.id` | `sessions.session_id` |
  | `refresh_sessions.id` | `refresh_sessions.refresh_session_id` |

- Rename columns without recreating tables, replacing identity values, or losing
  account/session data. Preserve primary keys, foreign keys, identity generation,
  indexes, and existing relationships. Foreign-key columns already named
  `account_id` or `refresh_session_id` retain those names.
- Use a forward numbered migration for deployed schema; do not edit production
  migration history or its checksums. Follow the repository migration rules for
  any migration that has not yet run in production.
- Update repository queries, joins, `RETURNING` clauses, internal field access,
  fixtures, and operational scripts to use the renamed columns. Keep application
  SQL in repositories, using one triple-quoted string per query.
- Preserve existing public API field names, including `/api/auth/me`'s `id`, with
  explicit boundary mappings where needed. This is a database naming change, not
  a public API redesign. Keep natural/composite keys unchanged.
- Document rollout ordering and rollback compatibility: older API images reference
  the old column names and cannot be assumed compatible after a rename. Use the
  existing migration backup/deployment workflow and record any maintenance window.

## Acceptance and verification

Apply the migration to a disposable database populated with synthetic accounts,
access sessions, and refresh sessions. Verify that identifiers and relationships
are preserved and newly created records still receive identity values. Migration
rerun must be safe.

Run authentication, rotation/concurrency, logout, password-reset, bootstrap, and
readiness checks against the renamed schema. Confirm the public account response
is unchanged. Check the schema for remaining bare `id` columns without introducing
per-column schema snapshot tests. Run the normal required checks, then record
review, deployment, and production acceptance evidence before marking Complete.

## Completion notes

To be filled in during implementation. This ticket records deferred work only;
no columns or migrations have been changed by its creation.

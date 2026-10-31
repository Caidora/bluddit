# 02: SQL migrations and database access

Status: In progress — implementation and CI verification complete; maintainer review and production acceptance pending

Dependencies: Ticket 01.

## Outcome

Establish explicit SQL migrations and a shared database access pattern.

## Implementation

- Add a PostgreSQL connection pool and parameterized SQL execution with explicit transaction boundaries; use no ORM.
- Resolve the high-level plan’s `ngpsql` ambiguity: this plan assumes a Python-compatible PostgreSQL driver for FastAPI. Record the selected driver.
- Add numbered SQL migrations and a migration ledger. Initial tables cover accounts, permission grants, and sessions; feature tickets add their own tables.
- Accounts need a unique login identifier, display name, password hash, membership state, timestamps, and optional timezone.
- Sessions store a hash of the session token, account reference, creation time, expiry, and revocation state. Permission grants support multiple capabilities per account.
- Add a separate test database configuration and fixtures for API/database integration tests. Add a database readiness check distinct from process health.
- Extend the CI workflow with PostgreSQL integration tests and migration checks. Wire migrations into the existing Hetzner deployment so they run once before the new application version becomes healthy, with a backup before changes to an existing database.

## Acceptance and verification

Migrations run against an empty database and rerunning the migration command is safe. Failed migrations roll back. Integration tests prove transactions roll back on failure and user input is passed as SQL parameters.

Keep verification focused on migration/readiness behavior, rollback on failures, and
deployment ordering. Do not add per-column assertions or schema snapshot tests.
Record commands run and results; do not claim external verification that has not happened.

## Completion notes

Implemented Psycopg 3.3.6 (binary) with psycopg-pool 3.3.3, a lifespan-managed
synchronous pool, explicit transaction contexts and a shared FastAPI dependency.
SQL values are supplied separately as parameters. No ORM or authentication routes.

Added `0001_accounts_and_sessions.sql` for accounts, capabilities, and hashed-token
sessions. Usernames are unique regardless of case. Added forward-only `status` /
`apply` CLI commands, a checksum ledger, advisory locking, and transactional
migration execution. Applied migrations cannot be edited silently.

Added database-independent liveness and database/migration readiness at
`/api/health` and `/api/ready`. Local/reload Compose waits for a one-shot migration
service. Production uses a separately invoked, profiled migration service before
application rollout, after a backup and restore check when migrations are pending.
Restart and image rollback do not migrate. API credentials use a separate copy of
the existing secret readable by non-root UID 10001. Updated CI, Make commands,
setup docs, and runbook. Deployment smoke checks now match the CSR page and include
readiness; foundation-image rollback uses its earlier health contract.

Local verification on 2026-10-31:

- `make verify` with a dedicated disposable `TEST_DATABASE_URL`: passed web type
  checks/build, 6 existing API checks, 3 focused database checks, 17 infrastructure
  checks, and base/reload Compose configuration validation.
- `actionlint .github/workflows/ci.yaml` and `git diff --check`: passed.
- Isolated production container build: passed, including frontend types/build.
- Isolated local Compose startup: applied migration before API startup; migration
  `status` and repeat `apply` both reported no pending/applied changes. SPA/API
  smoke checks passed on port 18082. Docker Desktop rejected the repository config
  bind mount, so the smoke run used an identical copy in `/private/tmp`.
- Isolated production Compose verification: mounted API secret was readable as
  UID 10001, migration application/rerun succeeded, and SPA/API/readiness smoke
  passed on port 18083 using dedicated containers and a disposable volume.
- Focused checks prove transaction rollback, failed migration rollback/retry, and
  backup/migration failure preventing application rollout and release activation.
  No per-column, index, or application-schema snapshot tests were added.

Ticket 01 completion was confirmed by the maintainer during this implementation.
[PR #1](https://github.com/Caidora/bluddit/pull/1) contains the implementation.
[CI run 41174129177](https://github.com/Caidora/bluddit/actions/runs/41174129177)
passed verification for implementation commit `647c8d8`, including disposable
PostgreSQL checks and production-container migration/rerun/readiness smoke checks.
Image publication and deployment were correctly skipped for the PR.

Pending: required maintainer PR review, merge and deployment through Actions, and
production migration/readiness/rerun evidence with deployed image references.
Do not mark Complete before production acceptance is recorded.

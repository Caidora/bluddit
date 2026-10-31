# 02: SQL migrations and database access

Status: Not started

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

Implement meaningful checks for the behavior and failure paths above. Record commands run and results in the completion notes; do not claim external verification that has not happened.

## Completion notes

To be filled in by the implementing AI: changes, migrations/configuration, verification evidence, and any unresolved acceptance items.

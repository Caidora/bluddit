# Contributing to Bluddit

## All changes go through a pull request

**Every ticket must be implemented on a branch and merged into `main` through a
pull request (PR). Never commit or push directly to `main`.** This applies to
everyone, including maintainers and AI contributors, and includes documentation,
configuration, dependency updates, and urgent fixes.

1. Start from the latest `main` and create a descriptive branch such as
   `feature/02-sql-migrations` or `feature/fix-event-time-display`.
2. Keep commits focused, with messages that explain the change.
3. Open a PR targeting `main`, linking the ticket or issue it addresses.
4. Run the relevant checks, resolve review feedback, and obtain approval from
   another maintainer before merging. Required CI checks must pass; do not bypass
   checks or review requirements.
5. Merge through GitHub and delete the branch when it is no longer needed.

Maintainers should enforce this policy with a GitHub ruleset or branch protection
on `main`: require PRs, at least one approving review, passing CI, and resolved
review conversations; block force pushes and deletion, and apply the rules to
administrators as well. This document describes the policy; it does not configure
repository protection.

## Choose and scope work

- Read the [README](README.md), [release-1 feature plan](website-feature-plan.md),
  and [ticket index](tickets/README.md) before starting.
- Complete implementation tickets in numerical order, one at a time, respecting
  their dependencies. Coordinate with maintainers before taking a ticket or
  changing its scope.
- For a new bug or improvement, create or agree on an issue first. Include the
  problem, expected behavior, and reproduction steps where applicable.
- Keep each PR focused on one ticket or coherent fix. Avoid unrelated refactors,
  formatting changes, and unplanned features.
- Human and AI contributors follow the same workflow. Review generated code and
  verify its behavior before submitting it.

## Set up and verify locally

Follow the [operations runbook](docs/operations.md) for prerequisites, selected
versions, environment setup, and commands. Copy `.env.example` to `.env` and set a
local database password before running the stack or Compose checks. Host database
checks also require `TEST_DATABASE_URL` pointing to a disposable PostgreSQL database
ending in `_test`, with a user allowed to create disposable databases; see the runbook.

```sh
make setup   # Install locked frontend and backend dependencies
make dev     # Start the local stack with source reload
make verify  # Check web types/build, API, infrastructure, and Compose config
```

Add or update meaningful tests for changed behavior and regressions. Check affected
user flows manually, including mobile layouts, permissions, and regional times
where relevant. Documentation-only PRs can use documentation checks; state which
checks you ran and explain any omissions. CI must still pass before merge.

Use Ruff to format Python code. Before committing or requesting review, run the
following final checks from the repository root, replacing `<changed-python-paths>`
with every Python file or directory touched by the change (including tests and
infrastructure scripts):

```sh
ruff format <changed-python-paths>
ruff format --check <changed-python-paths>
ruff check <changed-python-paths>
make verify
git diff --check
```

Resolve formatting and lint failures before handing off the change. Review any
automatic fixes; do not suppress findings just to pass. These final checks are
additional to feature-specific verification. Ruff is a host tool; install it with
`uv tool install ruff` if unavailable. `make verify` does not currently run Ruff,
so run the Ruff commands explicitly.

## Implementation practices

- Follow the existing React Router/React CSR frontend (SPA mode) and FastAPI backend patterns.
  Prefer small, readable changes and avoid new dependencies without a clear need.
  Include the appropriate lockfile whenever dependencies change.
- Use explicit parameterized SQL and numbered migrations, with no ORM. Preserve
  existing data and document migration, compatibility, and recovery implications.
- Bind SQL values by name, using placeholders such as `%(account_id)s` and a
  separate mapping such as `{"account_id": account_id}`. Do not use positional
  `%s` placeholders or positional parameter sequences. Let the driver bind values;
  never interpolate them with Python formatting or f-strings.
- Name ID columns with the singular table/entity name in snake_case followed by
  `_id`: `accounts.account_id`, `sessions.session_id`, and
  `refresh_sessions.refresh_session_id`, never a bare `id`. Foreign-key ID columns
  use the referenced entity's name, such as `sessions.account_id`. This applies to
  new schema work; existing bare `id` columns are tracked in
  [ticket 21](tickets/21-table-prefixed-id-columns.md) and must not be renamed as
  an unrelated change. Natural and composite keys do not need synthetic ID columns.
- Keep application SQL in repository methods, using one triple-quoted string per
  query. Repository methods represent complete persistence operations and may
  execute multiple queries in one transaction; do not split an operation into
  chained repository helpers. Keep ordinary authorization,
  membership transitions, and other business rules in API handlers/helpers, with
  a service layer only when needed. Avoid static methods in new repositories.
  Existing repository patterns outside the current ticket can remain unchanged.
  Routes belong in `bluddit_api/routes`, with shared helpers in `bluddit_api/utils`.
  Repositories own operation-level transaction boundaries; dependency providers
  construct repositories without opening a request-wide transaction. Keep related
  writes atomic where correctness requires it, such as membership revocation with
  session revocation, or checking the current GM and transferring that role.
  Ordinary permission checks run in the API and may race with later changes.
  Handlers call repository operations without executing SQL or managing
  connections. Inject repositories into routes
  and request dependencies using reusable `Annotated` aliases such as
  `AuthRepositoryDep`. Define the aliases and their FastAPI `Depends` providers in
  `bluddit_api/utils/dependencies.py`. Pool lifecycle and migration
  tooling remain infrastructure concerns.
- During review, update the existing migration in the same PR if it has not run
  in production; do not add another migration just to revise that PR. Once a
  migration has run in production, preserve its contents and checksum and add a
  new numbered migration for schema changes. Local or CI execution alone does not
  make a migration immutable. If an edited migration was already applied locally,
  recreate only the disposable development/test database; never rewrite the ledger
  to disguise a schema mismatch or reset production/member data.
- Enforce authorization and validate input at the API. Hiding a UI control is not
  an access-control check. Cover denied access as well as successful requests.
- Make common workflows usable on a phone and with a keyboard. Use clear labels,
  useful validation messages, and explicit loading, empty, and error states.
- Never commit secrets, `.env` files, production database dumps, or private member
  information. Use synthetic test data and remove sensitive details from logs,
  screenshots, issues, and PRs. Report suspected credential exposure privately to
  a maintainer and arrange rotation.
- Update setup instructions, the runbook, and relevant feature documentation when
  behavior, configuration, or operational steps change.

## Make PRs easy to review

Include the ticket or issue link, a concise explanation of the problem and change,
the checks performed and their results, and any remaining limitations. Add
screenshots for visible UI changes and call out migrations, new configuration,
dependency changes, and deployment or rollback considerations when applicable.

Use a draft PR for unfinished work. Keep feedback constructive, explain important
tradeoffs, and resolve outstanding discussions before merge. After substantial
changes during review, rerun affected checks and request another review.

## Deployment and ticket completion

Successful builds on `main` trigger production deployment, so merging has an
operational effect. All production changes must use the GitHub Actions workflow
described in the [runbook](docs/operations.md).

Interactive first-officer creation and password resets through the documented
administrative CLI are the approved exception to Actions-only production changes.
Use hidden terminal prompts; never put passwords in commands, logs, or PRs.

After merging an implementation ticket, confirm deployment succeeded and verify
its acceptance criteria in production using dedicated test records, preserving
member data. Record implementation details, verification evidence, deployed
version, and unresolved items in the ticket. Mark it Complete only when all its
acceptance conditions are met. Any follow-up documentation changes also go through
a PR. For a failed deployment, follow the runbook's recovery procedure and record
what remains unresolved.

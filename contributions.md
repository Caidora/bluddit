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

## Implementation practices

- Follow the existing React Router/React CSR frontend (SPA mode) and FastAPI backend patterns.
  Prefer small, readable changes and avoid new dependencies without a clear need.
  Include the appropriate lockfile whenever dependencies change.
- Use explicit parameterized SQL and numbered migrations, with no ORM. Preserve
  existing data and document migration, compatibility, and recovery implications.
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

After merging an implementation ticket, confirm deployment succeeded and verify
its acceptance criteria in production using dedicated test records, preserving
member data. Record implementation details, verification evidence, deployed
version, and unresolved items in the ticket. Mark it Complete only when all its
acceptance conditions are met. Any follow-up documentation changes also go through
a PR. For a failed deployment, follow the runbook's recovery procedure and record
what remains unresolved.

# 04: Membership approval and permissions

Status: In progress — implementation and local verification complete; PR review, deployment, and production acceptance pending

Dependencies: Ticket 03.

## Outcome

Implement Guild Master, Officer, and Member roles with fixed Python permission
mappings and membership administration. Document future attribute-based access
checks for organizer/quartermaster duties; implement those with their resources.

## Implementation

- Use registration with officer approval as the release-1 membership path. New accounts remain pending and cannot read guild data.
- Add pending registration and officer approval/rejection endpoints and account deactivation. Validate and normalize usernames and validate membership-state transitions in the application layer.
- Add reusable active-membership and permission checks. Document ownership and organizer/quartermaster attribute checks for later feature tickets. Officers may correct shared records through explicitly authorized feature actions.
- Use exactly one role per account: Guild Master (`guild_master`), Officer (`officer`), or Member (`member`). All permissions come from role-to-permission mappings; do not add direct account grants. Define the permission catalog and default role mappings here, subject to active membership and resource scope. Organizer and quartermaster duties are permissions/scoped assignments, not separate roles.
- Add distinct GM-only promotion-to-Officer, demotion-to-Member, and GM-succession endpoints and repository methods. All use `accounts.manage` with an additional GM check. Add a read-only permission catalog. Define mappings in a Python policy class; drop unused `role_permissions` and `permissions` tables while retaining `roles`. No policy-write endpoints or startup synchronization.
- Protect GM accounts from Officer changes. Only the active GM may transfer the role atomically to another active account, becoming an Officer. The repo manager establishes the first GM directly in PostgreSQL; enforce at most one GM and prevent ordinary GM deactivation/demotion.
- Prevent removal or deactivation of the last active administrator (Officer or GM).
- Revoking membership immediately prevents further use of existing sessions. Prevent users from granting themselves permissions.
- Document a route/action permission matrix that later feature tickets must implement. Organizer access is scoped to assigned squads/events.

## Acceptance and verification

Pending users cannot access member records. Members cannot approve themselves or
change roles. Officers can approve, reject, deactivate, and activate accounts.
Only the current GM can promote/demote roles or pass GM. Permission mappings are fixed in
code and exposed read-only. Concurrent administration preserves active leadership;
GM transfer is atomic. Ownership and organizer-scope tests arrive with the
resources in subsequent feature tickets, following the documented matrix.

Implement meaningful checks for the behavior and failure paths above. Record commands run and results in the completion notes; do not claim external verification that has not happened.

## Completion notes

Implemented in [PR #4](https://github.com/Caidora/bluddit/pull/4) on
`feature/04-membership-permissions`, based on merged ticket 03
commit `20419e4095d3288e4a400263f458da9c04b6e5f1`. Confirmed PR #3 merged and
[workflow 41184400705](https://github.com/Caidora/bluddit/actions/runs/41184400705)
passed verify, publish, production deployment, and public HTTPS smoke. Ticket 03's
recorded feature-specific production acceptance remains outstanding; no additional
ticket 03 acceptance is claimed here.

Registration creates pending Members, with normalized unique usernames, Argon2id
password hashes, CSRF/origin validation, 8 KiB JSON limits, and a separate bounded
process-wide throttle (10 attempts/15 minutes). Password work shares the existing
two-slot concurrency limit. Registration never issues sessions. Added paginated
account reads, approval/rejection/deactivation/reactivation, Member/Officer role
assignment, and GM transfer. Deactivation revokes all refresh-session families;
reactivation requires new credentials. Responses omit credential/session data.

Role/permission enums and an immutable Python policy replace database mappings.
Added permission dependency aliases, effective permissions on `/api/auth/me`, and
the read-only `/api/permissions` catalog. All API responses disable caching.
Operations that can reduce leadership share the bootstrap advisory lock.
GM succession locks affected accounts in ID order and rechecks GM authority within
its transaction; ordinary permission checks run at request time. Self-role changes,
Officer changes to GM accounts, and last-administrator removal are denied.

Migration `0003_membership_policy.sql` drops the unused permission tables and adds
the single-GM unique index without changing accounts, role references, or existing
ID names. Duplicate GMs cause a clear transactional failure. First-GM setup is
manual repository-manager database administration; subsequent succession is an
atomic API transfer, with the outgoing GM becoming Officer. No CLI change.

The [permission matrix](../docs/permissions.md) specifies endpoint gates and future
ownership, manager, quartermaster, and state checks. Resource assignments and
cross-resource write tests remain with their respective feature tickets. Ticket 05
owns all account screens. The runbook documents API shapes, rate limits, GM setup,
and rollback: older runtime authentication does not use the removed tables, but
its migration checker rejects the newer ledger, so use a compatible image/forward fix.

Local verification on 2026-10-31:

- `make verify`, using an isolated PostgreSQL 17 container on port 18404:
  16 API/unit tests, 29 database integration tests, 18 infrastructure tests,
  frontend types/build, and base/reload Compose configuration passed.
- Tests cover registration validation/duplicates, membership transitions, pending
  access denial, permanent session revocation, fixed mappings, live role changes,
  concurrent administrator deactivation/demotion, GM transfer concurrency/rollback,
  and migration preservation/removal/duplicate-GM failure.
- Ruff formatting/checks and `git diff --check`: passed.

Pending: maintainer review, merge/Actions deployment, and production membership-flow
acceptance with dedicated test records. No ticket 04 production verification or
deployed version is claimed; leave status In progress until these are recorded.

### PR review updates — 2026-10-31

Addressed the review by replacing the action-dispatch repository method and
generic mutation routes with seven explicit operations: approve, reject,
deactivate, activate, promote to Officer, demote to Member, and pass Guild Master.
Each route calls its corresponding repository method. Shared private helpers
retain transaction/locking, membership-transition, and leadership safeguards.
Repository parameters and SQL bindings now consistently use `membership_state`.

All seven actions require `accounts.manage`. Promotion, demotion, and passing GM
additionally require the current active GM, enforced at the route and rechecked
inside the write transaction. Removed the separate role-assignment/GM-transfer
permission names; Officers and GM have identical fixed permission sets, with
the role attribute constraining these actions. Officer membership administration
is retained. No migration changes are required.

Updated API documentation, the permission matrix, and ticket 05 guidance. Tests
exercise the explicit routes, Officer denial of role changes at both layers,
GM-only promotion/demotion, live authority after succession, removed generic
routes, and the preserved concurrent deactivation/GM-transfer safeguards.

Verification: Ruff format/check, `git diff --check`, and `make verify` passed:
16 API/unit tests, 31 PostgreSQL 17 integration tests, 18 infrastructure tests,
frontend types/build, and both Compose configurations. Production verification
and maintainer approval remain pending.

### Repository responsibility review — 2026-10-31

Removed business rules, static methods, and transaction orchestration from the
ticket 04 membership repository. Each method now executes a distinct SQL
operation on a supplied connection. Account API handlers/helpers perform
membership/role validation, missing-account handling, leadership safeguards,
and authorization rechecks after locking. Registration maps duplicate usernames
to HTTP 409 in its API handler. No API or migration changes.

The repository dependency opens one transaction for the endpoint, using
`scope="function"` so commit finishes before success is sent. Membership changes
and session revocation, and both GM succession writes, remain atomic. Existing
repositories/static helpers from earlier tickets are unchanged, as requested.
Updated contributor/runbook guidance and the permission matrix to document this
boundary; no service layer is introduced.

Verification: `make verify` passed 17 API/unit tests, 32 PostgreSQL 17 integration
tests, 18 infrastructure tests, frontend types/build, and both Compose
configurations. Tests now exercise the API flows for concurrent administration
and duplicate registration, stale GM authority under lock, GM-transfer rollback,
deactivation rollback when revocation fails, and commit failure returning 503
instead of a false registration success. Ruff format/check and
`git diff --check` passed. Maintainer approval and production acceptance remain
pending.

### Operation transaction boundaries — 2026-10-31

Replaced the request-wide transaction and connection-bound dependency with the
normal Database-backed repository provider. Each distinct repository operation
owns its transaction and may execute multiple SQL queries directly; there are no
chained lock/revocation/demotion repository helpers. API permission and input
checks remain separate and may race with subsequent account changes.

Deactivation/rejection include their session revocation in the same repository
transaction. Passing GM includes locking both affected accounts, verifying that
the caller is still the active GM, demoting that caller, and promoting the
recipient in one transaction. Deactivation, demotion, and succession retain the
shared leadership lock; conditional writes protect target states, prevent direct
changes to a GM, and retain an active administrator. Conflicting writes return
409; stale GM authority during succession returns 403. No API or schema changes.

Updated contributor guidance, the runbook, and permission matrix. `make verify`
passed 17 API/unit tests, 31 PostgreSQL 17 integration tests, 18 infrastructure
tests, frontend types/build, and both Compose configurations. Rollback tests fail
the SQL statement after the first write inside each operation; tests also cover
concurrent leadership changes, a stale GM caller, and succession between a
deactivation precheck and its write. Ruff format/check and `git diff --check`
passed. Review, deployment, and production acceptance remain pending.

### Membership predicate cleanup — 2026-10-31

Removed the redundant GM exclusions from approval, rejection, and activation:
these transitions assume a GM is always active. Retained the deactivation
predicate, which protects an active GM, including succession after an API precheck.
No new support for pending/inactive GM accounts or schema changes was added.

Verification: Ruff format/check, `git diff --check`, and `make verify` passed
(17 API/unit tests, 31 PostgreSQL 17 integration tests, 18 infrastructure tests,
frontend types/build, and both Compose configurations).

### Route clarity and session revocation review — 2026-10-31

Removed all private helpers from the account routes and repeated target lookup,
GM protection, membership-transition validation, and update-conflict handling
inside each explicit route. Contributor guidance now says to extract functionality
deliberately and sparingly. Self-transfer returns before opening a repository
transaction; current-GM authority and recipient state are still rechecked under
lock before either succession write.

Moved duplicated refresh-session revocation SQL out of membership operations into
`AuthRepository.revoke_account_sessions`. Rejection/deactivation routes call it
separately after a successful membership update. This supersedes earlier atomic
membership/session-revocation notes: the review explicitly accepts separate
commits and races. A revocation failure returns 503 while leaving membership
revoked; live membership checks deny access, but reactivation can restore old
sessions if revocation failed. Concurrent reactivation/login can also race with
revocation. Updated the runbook and permission documentation accordingly. No
schema changes or unrelated repository refactors.

Verification: `make verify` passed with an isolated PostgreSQL 17 container:
17 API/unit tests, 32 database integration tests, 18 infrastructure tests,
frontend types/build, and both Compose configurations. Failure tests cover both
rejection and deactivation, checking committed membership, immediate access denial,
and retained sessions after reactivation when the separate revocation fails.
Existing successful session-revocation, leadership concurrency, and atomic
succession rollback checks pass. Ruff format/check and `git diff --check` passed.
Maintainer approval, deployment, and production acceptance remain pending.

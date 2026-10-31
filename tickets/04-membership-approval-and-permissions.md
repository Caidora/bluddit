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
- Add account-role assignment and read-only permission catalog endpoints. Define mappings in a Python policy class; drop unused `role_permissions` and `permissions` tables while retaining `roles`. No policy-write endpoints or startup synchronization.
- Protect GM accounts from Officer changes. Only the active GM may transfer the role atomically to another active account, becoming an Officer. The repo manager establishes the first GM directly in PostgreSQL; enforce at most one GM and prevent ordinary GM deactivation/demotion.
- Prevent removal or deactivation of the last active administrator (Officer or GM).
- Revoking membership immediately prevents further use of existing sessions. Prevent users from granting themselves permissions.
- Document a route/action permission matrix that later feature tickets must implement. Organizer access is scoped to assigned squads/events.

## Acceptance and verification

Pending users cannot access member records. Members cannot approve themselves or
change roles. Officers can approve, reject, deactivate, reactivate, and manage
authorized Member/Officer role assignments. Permission mappings are fixed in
code and exposed read-only. Concurrent administration preserves active leadership;
GM transfer is atomic. Ownership and organizer-scope tests arrive with the
resources in subsequent feature tickets, following the documented matrix.

Implement meaningful checks for the behavior and failure paths above. Record commands run and results in the completion notes; do not claim external verification that has not happened.

## Completion notes

Implemented on `feature/04-membership-permissions`, based on merged ticket 03
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
Administrative writes share the bootstrap advisory lock, lock affected accounts
in ID order, and recheck actor authority within the transaction. Self-role changes,
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

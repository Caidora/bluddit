# Permission policy and resource authorization

`bluddit_api/utils/permissions.py` is the single source of truth. Each account has
one role; mappings are immutable Python sets. There are no account grants,
database permission mappings, or policy-write endpoints. Policy changes use a
reviewed PR. Authentication and permissions are checked against current account
state on every request; pending, rejected, and inactive accounts have no access.

## Current routes

| Action | Permission | Additional restriction |
| --- | --- | --- |
| Register | Public | Always creates a pending Member; cannot supply role/state |
| Login / refresh / current account | Active account | Valid credentials/session; `/me` only returns the caller |
| List/read accounts; approve/reject/deactivate/activate | `accounts.manage` | Officers and GM; protected GM and membership-transition rules |
| Promote to Officer / demote to Member | `accounts.manage` | GM only; explicit source role; no self-role changes or changes to GM; retain an active administrator |
| Read policy | `policy.read` | Officers and GM; no mutation API |
| Pass GM | `accounts.manage` | Current active GM → different active account; atomic succession |

Members have `guild.read`, `profile.edit_own`, `characters.edit_own`,
`wishlist.edit_own`, and `signups.edit_own`. Officers inherit those permissions
and add `accounts.manage`, `policy.read`, and `shared_records.correct`. The GM has
the same permission set as Officers. Role changes additionally require the actor
to be the current GM. The API checks this at the endpoint gate. Ordinary permission
checks may race with later account changes. Passing GM additionally rechecks the
caller against locked records inside the repository operation's transaction,
together with both role updates. Conditional SQL writes preserve target-state
and leadership invariants even if API prechecks become stale.

Rejection/deactivation commit membership changes before a separate auth repository
call revokes all account refresh sessions. Failed revocation returns 503 without
rolling back membership. Live membership checks still deny access while inactive
or rejected, but old sessions may work after reactivation if revocation failed.
Concurrent reactivation/login can race with revocation; this tradeoff is accepted.

## Contract for later feature tickets

Permissions gate an action. Attribute-based authorization then limits which
records and operations that action can affect. Check both on the server; UI
capabilities are hints and never a substitute. Use `require_permission` for the
endpoint gate. Place state/relationship checks inside the operation transaction
where their consistency is required for correctness.
Never accept a client-supplied owner/manager ID as proof of authority.

| Future action | Permission gate | Required resource/state check |
| --- | --- | --- |
| Read guild profiles, squads, priorities, events, directory, handbook | `guild.read` | Active membership; resource visibility/state |
| Edit profile/characters/wishlist/signups | Corresponding `*.edit_own` | Ownership through persisted account/character relationships; feature-specific state validation |
| Manage a squad/event/roster | Add the action permission with that feature | Persisted manager assignment for that exact resource, plus allowed state |
| Create an event | Add the action permission in ticket 11 | Validate creation and establish creator's manager relationship atomically |
| Maintain routing/crafter/buff assignments | Add the action permission in tickets 13–14 | Persisted quartermaster responsibility and its defined scope |
| Correct shared records / edit handbook / assign managers | `shared_records.correct` | Explicit Officer/GM action, existing target, and all record-validity constraints |

Organizer and quartermaster are responsibilities, not account roles. Future
tickets add action permissions to the fixed mappings alongside concrete assignment
models. Assignment-gated actions may be available to the Member role, but grant no
write access without the qualifying relationship. No generic assignment schema or
duty endpoints are introduced in ticket 4.

For example, creating a dungeon run can establish its creator as manager. Event
updates must check the stored manager relationship. If the feature allows an
Officer to take over management, implement an explicit authorized reassignment
action before using manager capabilities. Any Officer correction bypass must be
explicitly documented by that feature; do not infer it from the role name.

Feature tests must deny cross-owner writes and unassigned/cross-resource manager
writes, including changed relationships during concurrent updates. Duty removal
and membership/role changes must affect subsequent requests without waiting for
token expiry. Ticket 4 tests concrete account/role restrictions; resource-specific
tests arrive with the resources in later tickets.

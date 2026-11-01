# Permission policy and resource authorization

`bluddit_api/utils/permissions.py` is the single source of truth. Each account has
one role; mappings are immutable Python sets. There are no account grants,
database permission mappings, or policy-write endpoints. Policy changes use a
reviewed PR. Authentication and permissions are checked against current account
state on every request; pending, rejected, and inactive accounts have no access.

## Current routes

| Action | Permission | Additional restriction |
| --- | --- | --- |
| Register | Verified Battle.net signup cookie | Always creates a pending Member; cannot supply identity, role, or state |
| Battle.net login / refresh / current account | Active linked account | Valid provider identity/session; fixed expiry up to 24 hours; `/me` only returns the caller |
| Legacy migration proof and linking | Unlinked account with valid password | Allowed in every membership state; grants no member access and preserves membership/role |
| List/read accounts; approve/reject/deactivate/activate | `accounts.manage` | Officers and GM; protected GM and membership-transition rules |
| Promote to Officer / demote to Member | `accounts.manage` | GM only; explicit source role; no self-role changes or changes to GM; retain an active administrator |
| Read policy | `policy.read` | Officers and GM; no mutation API |
| Read/search handbook | `guild.read` | Active member; current published content |
| Create/edit handbook; read revisions | `handbook.edit` | Officer/GM; server-attributed author; stable slug; expected revision required for edits |
| Delete handbook sections | `handbook.delete` | GM only; expected revision required; deletion removes all revisions |
| Read Bluds and game references | `bluds.view` | Active member; includes archived records |
| Create Blud | `bluds.edit_own` | Owner is always the caller |
| Edit/archive/restore own Blud | `bluds.view` + `bluds.edit_own` | Persisted `account_id` matches caller; ownership cannot change |
| Correct/edit/archive/restore another member’s Blud | `bluds.view` + `shared_records.correct` | Explicit officer correction controls; last modifier attributed by the server |
| Read events/references | `guild.read` | Active membership; scheduled and cancelled records are readable |
| Create event / preview scheduling | `events.create` | Active member; creator assignment established atomically |
| Edit/cancel event | `events.manage` | Current event organizer assignment, or explicit Officer/GM `shared_records.correct` bypass; cancelled events reject edits |
| Replace event organizers | `shared_records.correct` | Officer/GM only; distinct active accounts, nonempty assignment set, scheduled event |
| Pass GM | `accounts.manage` | Current active GM → different active account; atomic succession |

Members have `guild.read`, `bluds.view`, `bluds.edit_own`, `profile.edit_own`, `characters.edit_own`,
`wishlist.edit_own`, `signups.edit_own`, `events.create`, and `events.manage`. Officers inherit those permissions
and add `accounts.manage`, `policy.read`, `handbook.edit`, and
`shared_records.correct`. The GM also has `handbook.delete`. Role changes additionally require the actor
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

Bluds updates deliberately use last-write-wins behavior, with no revisions, row
locking, or conflict detection. Ordinary membership/permission checks retain the
existing policy’s race tradeoff. Blud ownership is immutable and is also checked
in the update statement. `characters.edit_own` remains reserved for the broader
character roadmap; it does not grant Bluds access. See [Bluds](bluds.md).

## Contract for future features

Permissions gate an action. Attribute-based authorization then limits which
records and operations that action can affect. Check both on the server; UI
capabilities are hints and never a substitute. Use `require_permission` for the
endpoint gate. Place state/relationship checks inside the operation transaction
where their consistency is required for correctness.
Never accept a client-supplied owner/manager ID as proof of authority.

| Future action | Permission gate | Required resource/state check |
| --- | --- | --- |
| Read future guild profiles, wishlists, directory | `guild.read` | Active membership; resource visibility/state |
| Edit profile/characters/wishlist/signups | Corresponding `*.edit_own` | Ownership through persisted account/character relationships; feature-specific state validation |
| Manage a future event roster | `events.manage` | Persisted assignment to that exact event, or documented officer bypass; allowed state and roster constraints |
| Maintain routing/crafter assignments | Add the action permission with directory maintenance | Persisted quartermaster responsibility and its defined scope |
| Correct shared records / assign managers | `shared_records.correct` | Explicit Officer/GM action, existing target, and all record-validity constraints |

Organizer and quartermaster are responsibilities, not account roles. Future
features add action permissions to the fixed mappings alongside concrete assignment
models. Assignment-gated actions may be available to the Member role, but grant no
write access without the qualifying relationship. No generic assignment schema or
duty endpoints exist in the current membership implementation.

For example, creating a dungeon run can establish its creator as manager. Event
updates must check the stored manager relationship. If the feature allows an
Officer to take over management, implement an explicit authorized reassignment
action before using manager capabilities. Any Officer correction bypass must be
explicitly documented by that feature; do not infer it from the role name.

Feature tests must deny cross-owner writes and unassigned/cross-resource manager
writes, including changed relationships during concurrent updates. Duty removal
and membership/role changes must affect subsequent requests without waiting for
token expiry. Current membership tests cover concrete account/role restrictions;
resource-specific tests belong with the features that introduce those resources.

Events lock the event before checking current assignments and writing. Organizer
removal therefore affects edits queued behind that lock. Assignment updates use
the same lock. See [Events](events.md) for the concrete API and section 12 contract.

## Battle.net identity migration

Account IDs and all ownership relationships remain stable. Battle.net account ID
is unique and authoritative; BattleTags and display names never merge accounts.
Linking atomically removes the password and revokes all old refresh sessions.
Migration 0008 revokes existing sessions immediately, while unlinked credentials
remain available for migration. Linked accounts cannot receive a local password
through the administrative CLI. Pending, rejected, and inactive accounts can link
without receiving member access. Each login has its own fixed expiry; signing in
elsewhere does not renew it. Provider tokens remain encrypted and private.

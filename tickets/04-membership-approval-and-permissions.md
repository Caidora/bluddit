# 04: Membership approval and permissions

Status: Not started

Dependencies: Ticket 03.

## Outcome

Implement Guild Master, Officer, and Member roles with role-based permissions and scoped organizer/quartermaster duties.

## Implementation

- Use registration with officer approval as the release-1 membership path. New accounts remain pending and cannot read guild data.
- Add pending registration and officer approval/rejection endpoints and account deactivation. Validate and normalize usernames and validate membership-state transitions in the application layer.
- Add reusable server-side permission checks for members, assigned organizers, quartermasters, and officers. Officers may correct shared records.
- Use exactly one role per account: Guild Master (`guild_master`), Officer (`officer`), or Member (`member`). All permissions come from role-to-permission mappings; do not add direct account grants. Define the permission catalog and default role mappings here, subject to active membership and resource scope. Organizer and quartermaster duties are permissions/scoped assignments, not separate roles.
- Add account-role assignment and role-permission management endpoints; prevent removal or deactivation of the last active officer.
- Revoking membership immediately prevents further use of existing sessions. Prevent users from granting themselves permissions.
- Document a route/action permission matrix that later feature tickets must implement. Organizer access is scoped to assigned squads/events.

## Acceptance and verification

Pending users cannot access member records. Members cannot approve themselves, change their role, or modify role permissions. Officers can approve, reject, deactivate, and manage authorized role assignments and role permissions. Ownership and organizer-scope tests deny cross-user and unassigned-resource writes.

Implement meaningful checks for the behavior and failure paths above. Record commands run and results in the completion notes; do not claim external verification that has not happened.

## Completion notes

To be filled in by the implementing AI: changes, migrations/configuration, verification evidence, and any unresolved acceptance items.

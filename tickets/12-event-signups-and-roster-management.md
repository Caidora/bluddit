# 12: Event signups and roster management

Status: Not started

Dependencies: Ticket 11.

## Outcome

Let members RSVP and organizers fill confirmed places.

## Implementation

- Add one signup per account per event with selected active character, requested role, availability (available/tentative/declined), and roster state (pending/confirmed/standby).
- Provide own-signup create/update/withdraw endpoints and organizer roster-assignment endpoints.
- Confirm only available signups and compatible selected roles. Declining or withdrawing removes any confirmed place; changing a confirmed character or role returns it to pending.
- Use transactions and database constraints/locking to prevent concurrent assignments exceeding event capacity or role limits.
- Reject event edits that would put an existing confirmed roster over new limits until the organizer resolves assignments.
- Build signup controls, member status display, organizer roster controls, and open-role counts calculated from confirmed places.
- Cancelled events retain readable records and reject new signups or roster changes. Do not auto-promote standby members.

## Acceptance and verification

Signup, change, withdraw, standby, and confirmation work. Duplicate signups and cross-member writes fail. Concurrent final-place confirmations cannot overfill the event. Tentative/declined members do not occupy confirmed places.

Implement meaningful checks for the behavior and failure paths above. Record commands run and results in the completion notes; do not claim external verification that has not happened.

## Completion notes

To be filled in by the implementing AI: changes, migrations/configuration, verification evidence, and any unresolved acceptance items.

# 08: Squads, flex assignments, and leveling pairs

Status: Not started

Dependencies: Ticket 07.

## Outcome

Make Alpha, Bravo, flex members, and leveling pairs maintainable.

## Implementation

- Add squads, squad-organizer assignments, character memberships with assigned roles, flex assignments, and leveling-pair records.
- Create officer squad-management endpoints and assigned-organizer update permissions. Members have read access.
- Build squad list/detail pages with members, assigned roles, timezone labels, and maintained class utility.
- Add controls for moving members, assigning flex status, and pairing active characters. Prevent duplicate memberships and self-pairing.
- Complete the roster squad filter. Keep squad assignments distinct from an event’s confirmed roster.

## Acceptance and verification

Officers can create Alpha/Bravo and move a character. Assigned organizers can edit their squad; unrelated organizers cannot. Flex and pair records display correctly and archived characters are not offered for new assignments.

Implement meaningful checks for the behavior and failure paths above. Record commands run and results in the completion notes; do not claim external verification that has not happened.

## Completion notes

To be filled in by the implementing AI: changes, migrations/configuration, verification evidence, and any unresolved acceptance items.

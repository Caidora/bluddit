# 16: Member home page

Status: Not started

Dependencies: Ticket 12, Ticket 14, Ticket 15.

## Outcome

Connect the completed release-1 workflows on one useful page.

## Implementation

- Show the member’s next events, local times, and signup/roster status; distinguish cancelled events.
- Link to their characters, squad, and wishlist.
- Show dungeons benefiting their characters and current guild priorities from ticket 10 queries.
- Provide material/crafter search and handbook shortcuts.
- Reuse existing endpoints or add a small read-only aggregation endpoint; do not maintain a second set of totals.
- Provide useful empty states for a member without a character, targets, squad, or signups.

## Acceptance and verification

The home page reflects changes to signups, targets, and squads without stale duplicated records. A new member can reach character setup, and a returning member can reach their next run from a phone.

Implement meaningful checks for the behavior and failure paths above. Record commands run and results in the completion notes; do not claim external verification that has not happened.

## Completion notes

To be filled in by the implementing AI: changes, migrations/configuration, verification evidence, and any unresolved acceptance items.

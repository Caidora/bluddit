# 07: Roster search and composition summaries

Status: Not started

Dependencies: Ticket 06.

## Outcome

Replace the Overview roster and its composition formulas.

## Implementation

- Add roster queries and UI filters for role, profession, region, and squad; wire squad filtering after ticket 08.
- Display active characters grouped by member, with links to their profiles.
- Define summary counts as active mains only, so alts and secondary roles do not inflate primary composition. Show the counting basis in the UI.
- Calculate class, primary-role, armor, and profession coverage from stored character records, without fixed row limits.
- Treat secondary roles as potential utility, not extra people or guaranteed readiness.
- Keep query results bounded and add indexes for actual roster filtering needs.

## Acceptance and verification

Fixtures with mains, alts, secondary roles, and archived characters produce correct counts. Adding a member or changing a profession updates results. Combined filters work and a no-results state is usable.

Implement meaningful checks for the behavior and failure paths above. Record commands run and results in the completion notes; do not claim external verification that has not happened.

## Completion notes

To be filled in by the implementing AI: changes, migrations/configuration, verification evidence, and any unresolved acceptance items.

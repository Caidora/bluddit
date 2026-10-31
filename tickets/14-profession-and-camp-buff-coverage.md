# 14: Profession and camp-buff coverage

Status: Not started

Dependencies: Ticket 13.

## Outcome

Show maintained coverage without overstating active availability.

## Implementation

- Add configurable profession-to-camp-buff mappings and designated coverage assignments confirmed for the guild’s server.
- Provide quartermaster/officer maintenance controls for mappings and assignments.
- Calculate profession counts from active mains, with active alts listed separately as additional crafters.
- Show buffs with and without active assigned providers. Separate profession ownership from designated buff responsibility.
- Add coverage views to the roster/crafting directory and recalculate after profession, assignment, or active-state changes.

## Acceptance and verification

Changing professions or archiving a specialist updates coverage. A buff without an active assigned provider displays a gap. Shared buffs count once in covered-buff totals, and empty configuration does not show 100% coverage.

Implement meaningful checks for the behavior and failure paths above. Record commands run and results in the completion notes; do not claim external verification that has not happened.

## Completion notes

To be filled in by the implementing AI: changes, migrations/configuration, verification evidence, and any unresolved acceptance items.

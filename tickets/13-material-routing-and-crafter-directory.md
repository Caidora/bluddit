# 13: Material routing and crafter directory

Status: Not started

Dependencies: Ticket 07.

## Outcome

Replace Economy routing tables with searchable maintained records.

## Implementation

- Add routing categories/entries with material keywords, designated recipient references, outputs, priority, handling rules, and delivery instructions.
- Store crafter specialization, accepted-material descriptions, and deliverables against character profession assignments.
- Add read/search endpoints and quartermaster/officer create/update/archive endpoints. Support a guild-bank destination as a named destination, without inventory accounting.
- Build Crafting Directory search, category/detail views, linked member profiles, and maintenance forms.
- Preserve explicit recipient assignments separately from profession matching. Indicate inactive recipients rather than silently rerouting materials.

## Acceptance and verification

Searching a material finds its routing instructions and crafter links. Quartermasters can edit; members cannot. Entries can reference multiple recipients and a bank destination. Empty results and inactive recipients are clear.

Implement meaningful checks for the behavior and failure paths above. Record commands run and results in the completion notes; do not claim external verification that has not happened.

## Completion notes

To be filled in by the implementing AI: changes, migrations/configuration, verification evidence, and any unresolved acceptance items.

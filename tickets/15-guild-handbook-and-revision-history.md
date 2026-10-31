# 15: Guild handbook and revision history

Status: Not started

Dependencies: Ticket 05.

## Outcome

Publish the charter and operational rules with officer editing.

## Implementation

- Add handbook sections with stable slugs, title, body, updated time, author, and immutable revisions.
- Seed reviewed sections for charter, leadership contacts, scheduling expectations, loot, material handling, and conduct.
- Add member read/search endpoints and officer edit/revision-read endpoints. Detect stale edits rather than silently overwriting a newer revision.
- Build handbook navigation, section pages, simple search, editing forms, and revision display.
- Render content safely. Link events to scheduling/loot guidance and directory entries to material rules without duplicating policy text.

## Acceptance and verification

Members can find and read rules; officer edits create attributable revisions. Non-officer edits fail, stale saves are reported, and unsafe markup does not execute. Event and material links reach the right section.

Implement meaningful checks for the behavior and failure paths above. Record commands run and results in the completion notes; do not claim external verification that has not happened.

## Completion notes

To be filled in by the implementing AI: changes, migrations/configuration, verification evidence, and any unresolved acceptance items.

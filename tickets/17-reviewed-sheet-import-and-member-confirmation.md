# 17: Reviewed sheet import and member confirmation

Status: Not started

Dependencies: Ticket 16.

## Outcome

Move agreed source records into the website without making template data authoritative.

## Implementation

- Define a documented import format and a dry-run CLI for a reviewed local sheet snapshot; retain source row identifiers for reconciliation. No live bidirectional sync.
- Map roster, squads, professions, routing, and handbook records to their canonical entities. Preserve uncertain data in an import staging area.
- Never interpret “likely highest level” as current level, planned alts as existing characters, or region labels as precise timezones.
- Keep template wishlist/acquisition rows staged until confirmed. Members can review their officer-assigned imported profile and accept, correct, or discard draft targets.
- Officers link imported member records to approved accounts; do not let users claim another member’s identity by name.
- Make imports idempotent and transactional, report unmatched/duplicate rows, and never overwrite member edits on rerun.
- Confirm server-specific references and authoritative scheduling guidance before importing rules; do not turn generic windows into dated events.

## Acceptance and verification

A dry run writes nothing. Importing the same snapshot twice does not duplicate records. Unconfirmed targets do not affect live totals. Members can confirm only assigned drafts, and reconciliation accounts for every imported or excluded source row.

Implement meaningful checks for the behavior and failure paths above. Record commands run and results in the completion notes; do not claim external verification that has not happened.

## Completion notes

To be filled in by the implementing AI: changes, migrations/configuration, verification evidence, and any unresolved acceptance items.

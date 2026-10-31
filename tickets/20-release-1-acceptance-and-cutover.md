# 20: Release-1 acceptance and cutover

Status: Not started

Dependencies: Ticket 19.

## Outcome

Verify the complete member workflow and prepare the switch from the sheet.

## Implementation

- Exercise officer bootstrap → member registration/approval → imported profile confirmation → character edit → target update → event creation/signup/confirmation → acquisition update.
- Verify roster totals, farming demand, material routing, coverage, handbook revisions, and home-page links with representative records.
- Check permissions across every write path, narrow mobile layouts, keyboard navigation, loading/error states, and timezone display across regions.
- Run a pilot with an officer and members across the relevant regions; record issues and resolve release-blocking failures.
- Record approved source data, final schedule, backup/restore evidence, production test results, and a cutover checklist.
- Agree the editing cutoff, retain a dated sheet snapshot, reconcile final changes, and make the website authoritative only after the pilot and deployment checks pass.
- If member participation, server configuration, or go-live approval is unavailable, report the specific pending acceptance item; do not mark launch complete.

## Acceptance and verification

Release-1 acceptance checks in `website-feature-plan.md` pass with recorded evidence. Pilot participants confirm they can complete the core workflows without the sheet, recovery is verified, and cutover status accurately distinguishes prepared from live.

Implement meaningful checks for the behavior and failure paths above. Record commands run and results in the completion notes; do not claim external verification that has not happened.

## Completion notes

To be filled in by the implementing AI: changes, migrations/configuration, verification evidence, and any unresolved acceptance items.

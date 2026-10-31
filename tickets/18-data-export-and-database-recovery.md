# 18: Data export and database recovery

Status: Not started

Dependencies: Ticket 17.

## Outcome

Provide the release-1 data retention and recovery path.

## Implementation

- Add an officer-only export command or download for members/characters, squads, wishlists, events/signups, routing, coverage, and handbook revisions.
- Exclude password hashes, session tokens, and other authentication secrets from member-data exports.
- Add documented PostgreSQL backup and restore commands, retention configuration, and an example scheduled backup setup.
- Document backup storage outside the application host’s failure boundary using operator-provided storage configuration.
- Restore a backup into an isolated database and reconcile representative records. Keep production secrets out of exported diagnostics.

## Acceptance and verification

Exports contain the expected linked records and no authentication secrets. A backup can be restored into a clean database and the application reads the restored data. Failure of a backup command is visible to the operator.

Implement meaningful checks for the behavior and failure paths above. Record commands run and results in the completion notes; do not claim external verification that has not happened.

## Completion notes

To be filled in by the implementing AI: changes, migrations/configuration, verification evidence, and any unresolved acceptance items.

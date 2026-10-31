# 06: Member profiles and characters

Status: Not started

Dependencies: Ticket 05.

## Outcome

Let members maintain their own profile and playable characters.

## Implementation

- Add character, profession, and character-profession tables. Characters reference an account and include name, main/alt status, class, race, nullable current level, armor type, primary role, secondary roles, and active state.
- Store precise named timezones on profiles and separate region labels for filtering. Include configurable class utility metadata for squad display.
- Provide profile read/update and character create/read/update/archive endpoints with ownership checks and officer corrections.
- Use a small editable/seeded server-specific reference set for classes, races, roles, armor, and professions. Do not assume standard-server combinations; support the confirmed guild server.
- Add My Profile/My Characters forms and member profile pages. Keep characters referenced by historical records instead of hard-deleting them.
- Enforce at most one active main per account and prevent duplicate profession assignments.

## Acceptance and verification

Members can edit their own characters but cannot change another member’s ownership. Invalid timezones and reference values fail clearly. Unknown current levels can remain blank. Archiving preserves references and removes a character from active choices.

Implement meaningful checks for the behavior and failure paths above. Record commands run and results in the completion notes; do not claim external verification that has not happened.

## Completion notes

To be filled in by the implementing AI: changes, migrations/configuration, verification evidence, and any unresolved acceptance items.

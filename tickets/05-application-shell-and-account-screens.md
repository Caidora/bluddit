# 05: Application shell and account screens

Status: Not started

Dependencies: Ticket 04.

## Outcome

Provide navigation, authentication screens, and reusable member-page patterns.

## Implementation

- Implement login, registration, pending-approval, logout, and unauthorized screens.
- Add protected navigation: Home, Roster & Squads, Gear & Farming, Events, Crafting Directory, and Guild Handbook.
- Add officer membership screens, GM-only promotion/demotion/succession controls, and a read-only permission view using ticket 04 endpoints. Role-permission mappings are fixed in Python; do not offer mapping-edit controls.
- Create simple shared form, list, loading, empty, and error components. Preserve form input after validation errors.
- Hide unavailable controls according to capabilities, while retaining API authorization.
- Make navigation and forms work on phones and with a keyboard. Unbuilt feature destinations show a clear temporary empty state until their tickets land.

## Acceptance and verification

Registration → approval → login works through the UI. Refresh preserves a valid session; logout returns to login. Member and officer navigation reflect permissions. The shell works at narrow mobile widths without horizontal page scrolling.

Implement meaningful checks for the behavior and failure paths above. Record commands run and results in the completion notes; do not claim external verification that has not happened.

## Completion notes

To be filled in by the implementing AI: changes, migrations/configuration, verification evidence, and any unresolved acceptance items.

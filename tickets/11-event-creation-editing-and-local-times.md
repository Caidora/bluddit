# 11: Event creation, editing, and local times

Status: Not started

Dependencies: Ticket 08, Ticket 10.

## Outcome

Allow organizers to create dated activities linked to guild needs.

## Implementation

- Add events with title, activity type, optional canonical destination, organizer assignments, optional squad, start instant, scheduling timezone, duration, requirements text, capacity, role limits, and scheduled/cancelled state.
- Implement event list/detail/create/update/cancel endpoints. Officers manage any event; organizers manage assigned events and may create events they organize.
- Validate positive duration/capacity and coherent role limits. Confirmed roster constraints from ticket 12 must also apply to later event edits.
- Build event forms and list/detail pages; link destination needs to ticket 10 views.
- Interpret date/time entry in the selected named timezone, reject nonexistent daylight-saving times, and require explicit disambiguation for repeated times.
- Store a single authoritative start instant and display it in the viewer’s timezone with a visible label and date.

## Acceptance and verification

Authorized organizers can create/edit/cancel; unrelated organizers cannot. Tests cover Auckland, Sydney, Perth, date rollover, and daylight-saving transitions. A destination link opens the correct farming needs.

Implement meaningful checks for the behavior and failure paths above. Record commands run and results in the completion notes; do not claim external verification that has not happened.

## Completion notes

To be filled in by the implementing AI: changes, migrations/configuration, verification evidence, and any unresolved acceptance items.

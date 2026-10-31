# Release 1 implementation tickets

These tickets implement only [the release-1 feature plan](../website-feature-plan.md). Complete them in numerical order, one at a time. Dependencies identify the earlier work each ticket relies on; the sequence is intentionally suitable for a single implementing AI.

## Working rules

- Read the feature plan and the ticket before implementation. Inspect the current code and repository instructions before choosing exact files or commands.
- Keep work within the ticket. Do not add AI product features, crafting requests, cooldown tracking, loot tracking, recurring events, notifications, or other roadmap features.
- Each ticket includes its necessary database changes, API authorization, UI behavior, and verification. Do not leave an API-only feature marked complete when its UI is required.
- Use explicit parameterized SQL and numbered migrations, no ORM. Enforce permissions at the API, not just in the UI.
- Run appropriate checks and record evidence. Update the ticket status to Complete only when its acceptance conditions are met; otherwise record exactly what remains.
- Keep CI current as features and tests are added. After checks pass, deploy each completed implementation ticket through the workflow established in ticket 01 and verify its behavior on the Hetzner production instance using dedicated test records. Preserve member data and record the deployed version and results.
- Record migration/configuration changes and update setup instructions as needed. Preserve existing member data and user edits.

## Implementation defaults

To make tickets executable without reopening routine design decisions:

- Use one guild and one same-origin website/API deployment. Render the frontend client-side with React Router SPA mode; use FastAPI for backend operations.
- Establish production hosting on the existing Hetzner server in ticket 01. Test deployed behavior in production throughout implementation; no separate staging environment is planned. Local and CI tests still run before deployment.
- Use username/password accounts with officer-approved registration and server-side sessions. Password recovery uses an administrative CLI; no email or third-party login integration is included.
- Members may have multiple characters but at most one active main. Composition counts active mains; alts are separately visible.
- Use canonical source IDs shared by wishlists and events, with manually maintained item descriptions. No game-data integration is required.
- Event availability and organizer-assigned roster status are separate fields. One member has one signup per event.
- Use reviewed snapshot import with staging/confirmation, not live sheet synchronization.
- Exact dependency versions, SQL driver, and test commands are chosen and documented during foundation work. Confirm the `ngpsql` wording against the Python backend before choosing a driver.
- Server-specific rules, actual member identity mapping, real event times, credentials, and final cutover remain facts to confirm. Do not fabricate them or silently make template values live.

## Ticket order

| Ticket | Outcome | Depends on |
| --- | --- | --- |
| [01](./01-project-foundation.md) | Project foundation, CI, and Hetzner deployment | None |
| [02](./02-sql-migrations-and-database-access.md) | SQL migrations and database access | 01 |
| [03](./03-session-login-and-logout.md) | Session login and logout | 02 |
| [04](./04-membership-approval-and-permissions.md) | Membership approval and permissions | 03 |
| [05](./05-application-shell-and-account-screens.md) | Application shell and account screens | 04 |
| [06](./06-member-profiles-and-characters.md) | Member profiles and characters | 05 |
| [07](./07-roster-search-and-composition-summaries.md) | Roster search and composition summaries | 06 |
| [08](./08-squads-flex-assignments-and-leveling-pairs.md) | Squads, flex assignments, and leveling pairs | 07 |
| [09](./09-personal-gear-wishlist.md) | Personal gear wishlist | 06 |
| [10](./10-guild-farming-priorities-and-completion-totals.md) | Guild farming priorities and completion totals | 09 |
| [11](./11-event-creation-editing-and-local-times.md) | Event creation, editing, and local times | 08, 10 |
| [12](./12-event-signups-and-roster-management.md) | Event signups and roster management | 11 |
| [13](./13-material-routing-and-crafter-directory.md) | Material routing and crafter directory | 07 |
| [14](./14-profession-and-camp-buff-coverage.md) | Profession and camp-buff coverage | 13 |
| [15](./15-guild-handbook-and-revision-history.md) | Guild handbook and revision history | 05 |
| [16](./16-member-home-page.md) | Member home page | 12, 14, 15 |
| [17](./17-reviewed-sheet-import-and-member-confirmation.md) | Reviewed sheet import and member confirmation | 16 |
| [18](./18-data-export-and-database-recovery.md) | Data export and database recovery | 17 |
| [19](./19-production-operational-checks.md) | Production operational checks | 18 |
| [20](./20-release-1-acceptance-and-cutover.md) | Release-1 acceptance and cutover | 19 |

## Definition of release completion

The website supports the core workflows in all four sheet areas, and members can maintain their own information and join runs without editing the sheet. Correct permissions, regional event times, confirmed imports, recoverable data, and the pilot/cutover checks must all be verified.

Ticket completion is tracked in each file. Planning these tickets does not mean implementation or launch has happened.

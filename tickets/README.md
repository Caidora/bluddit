# Implementation workflow and completed tickets

Active implementation work is tracked in [GitHub issues](https://github.com/Caidora/bluddit/issues).
Each migrated issue contains the original ticket scope, dependencies, acceptance
checks, status, and verification history. Historical ticket numbers in issue
sections are distinct from GitHub issue numbers. Complete release-1 ticket
sections in their original numerical order, one at a time, respecting their
linked dependencies. Separately scheduled maintenance remains deferred as stated
in its issue; migration does not authorize implementing it.

Incomplete tickets are recorded only in GitHub issues. Record future progress,
verification evidence, deployed versions, and unresolved acceptance items there.
Completed ticket docs remain here as historical references, linked to their issues.

## Working rules

- Read the feature plan and the ticket before implementation. Inspect the current code and repository instructions before choosing exact files or commands.
- Keep work within the ticket. Do not add AI product features, crafting requests, cooldown tracking, loot tracking, recurring events, notifications, or other roadmap features.
- Each ticket includes its necessary database changes, API authorization, UI behavior, and verification. Do not leave an API-only feature marked complete when its UI is required.
- Use explicit parameterized SQL and numbered migrations, no ORM. Enforce permissions at the API, not just in the UI.
- Bind SQL values with named placeholders (`%(account_id)s`) and a separate mapping;
  do not use positional `%s` placeholders or interpolate values into SQL.
- Run appropriate checks and record evidence. Close the GitHub issue as completed only when its acceptance conditions are met; otherwise record exactly what remains in the issue.
- Use `ruff format` for changed Python files. Final checks include
  `ruff format --check`, `ruff check`, `make verify`, and `git diff --check`;
  see the contribution guide for command scope and documentation-only exceptions.
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

## Completed ticket references

| Ticket | Outcome | GitHub issue |
| --- | --- | --- |
| [01](./01-project-foundation.md) | Project foundation, CI, and Hetzner deployment | [#21](https://github.com/Caidora/bluddit/issues/21) |

## Definition of release completion

The website supports the core workflows in all four sheet areas, and members can maintain their own information and join runs without editing the sheet. Correct permissions, regional event times, confirmed imports, recoverable data, and the pilot/cutover checks must all be verified.

Completion is tracked in GitHub issues. Migration does not mean implementation or launch has happened.

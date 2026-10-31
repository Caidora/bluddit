# 05: Application shell and account screens

Status: In progress — implementation and local verification complete; PR review, deployment, and production acceptance pending

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

Implemented on `feature/05-application-shell`, based on merged ticket 04 and the
latest `main` (`6b7f3e1`). Replaced the public landing with login/member routing.
Added registration, pending guidance, login/logout, unauthorized/not-found screens,
protected member navigation and temporary feature states, membership filtering and
pagination, explicit membership actions, GM role/succession confirmations, and a
read-only permission matrix. The visual direction is dark modern Reddit, retaining
Bluddit branding, using local shadcn/ui primitives and Tailwind CSS.

The central typed API module owns endpoint contracts, requests, CSRF headers,
in-memory tokens, single-flight refresh, Web Lock/BroadcastChannel coordination,
and bounded authentication retry. TanStack Query owns server state, query keys,
read retry policy, mutation invalidation, and identity-scoped protected caches.
Credentials are never mutation variables or cached results. Session loss/logout
cancels protected queries and removes member data. Forms retain input on errors.

Added Playwright checks, including an isolated real API/PostgreSQL fixture. CI
installs Chromium and `make verify` runs browser tests. The fixture validates a
`_test` database name and creates/drops its own database with synthetic accounts.
No API endpoints or database migrations changed. Setup/browser requirements and
frontend structure are documented in the operations runbook.

Local verification on 2026-11-01:

- `make verify` with an isolated PostgreSQL 17 container on port 18405: passed
  frontend types/build, 20 Playwright tests (including the real registration →
  approval → login/refresh/logout flow), 20 API/unit tests, 32 database integration
  tests, 18 infrastructure tests, and both Compose configurations.
- Browser coverage includes error/input preservation, generic login errors and
  safe return navigation, capability changes, GM succession, pagination, keyboard
  dialogs, 320px/375px layouts, outages, failed/cross-tab logout, single-flight
  refresh, bounded retries, cross-tab locking, late responses, and cache cleanup.
- `ruff format --check apps/api/tests/browser_server.py`,
  `ruff check apps/api/tests/browser_server.py`, and `git diff --check`: passed.
- Fixed first-run Vite dependency reloads by pre-scanning lazy route dependencies;
  a cold-cache rerun passed all 19 browser tests. No external production behavior
  is inferred from local tests.
- Desktop login/membership and mobile home/navigation screenshots using only
  synthetic accounts are in [the screenshot folder](../docs/screenshots/ticket05/).

Pending: maintainer PR review, Actions deployment, ticket 04's outstanding recorded
acceptance, and ticket 05 production UI acceptance using dedicated test records.
No production deployment or verification is claimed; do not mark Complete yet.

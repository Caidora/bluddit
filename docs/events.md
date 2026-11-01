# Events: section 11

Active members can create general activities: dungeon runs, leveling, questing,
PvP, guild meetings, or other activities. Title, activity type, a local start time,
and a named scheduling timezone are required. Dungeon destination, maximum group
size, and expected duration are optional. Requirements are plain text. Historical
start dates are allowed.

The creator becomes an organizer in the creation transaction. Assigned active
organizers can edit or cancel their event. Officer/GM can manage any event through
an explicit `shared_records.correct` bypass and are the only accounts allowed to
replace organizer assignments. Assignment saves require distinct active accounts
and at least one organizer. Subsequent account deactivation denies that person's
access immediately; officers can recover events left without an active organizer.
There is no separate organizer account role.

Cancellation preserves the event and its assignments, is idempotent, and prevents
further edits or assignment changes. There is no deletion or reopening workflow.
Updates use last-write-wins behavior. Management operations lock the event row
before reading its assignments. A queued edit must observe an organizer removal
committed while it waited. Ordinary account membership/role checks retain the
existing permission policy's request-time race tradeoff.

## Scheduling

The API accepts `local_start` without an offset, `scheduling_timezone` as a named
IANA zone, and optional `occurrence: earlier|later`. It round-trips both timezone
folds through UTC, discards nonexistent wall times, and requires an explicit
choice if two different instants match. The preview endpoint exposes the valid
candidates and their offsets; writes independently resolve the input again.
Python `zoneinfo` uses system timezone data where available and the explicitly
pinned `tzdata` package as fallback. No runtime game-data/timezone service is used.

Only `starts_at` (PostgreSQL `timestamptz`) and the scheduling zone are persisted,
not a second local start time. A scheduling patch must supply both local time and
zone. Unrelated patches preserve the stored instant. Pages show the date and time
in the browser's timezone with its visible name; detail pages additionally show
the original scheduling-zone date and time. Forms default to the browser zone,
fall back to UTC, and populate edits using the event's scheduling zone. Missing
optional capacity/duration means unspecified, not zero.

## API

All endpoints require active membership and use the existing session and CSRF
protections. Request bodies reject unknown fields. IDs and attribution are
server-controlled.

| Endpoint | Behavior |
| --- | --- |
| `GET /api/events` | `period=upcoming|past|all`, `state=scheduled|cancelled|all`, `mine`, `limit`, `offset`; ascending start instant/event ID; defaults upcoming/scheduled |
| `GET /api/events/reference-data` | Activity choices, existing dungeon IDs/names, supported timezone names |
| `POST /api/events/preview-start` | `valid`, `ambiguous`, or `nonexistent`, with candidate instants/offsets |
| `POST /api/events` | Create and assign the caller; returns 201 |
| `GET /api/events/{event_id}` | Read scheduled or cancelled event |
| `PATCH /api/events/{event_id}` | Assigned organizer or Officer/GM update |
| `POST /api/events/{event_id}/cancel` | Assigned organizer or Officer/GM cancellation |
| `PUT /api/events/{event_id}/organizers` | Officer/GM replaces assignments using `account_ids` |

Lists return `events`, `limit`, `offset`, and `has_more`. Event responses include
organizer names and active status. Not found is 404, unauthorized management 403,
invalid values 422, and changes to cancelled events 409. Officer assignment
controls reuse the existing paginated active-account listing.

## Delivery boundaries and migration

Migration `0007_events.sql` is additive and preserves existing member records.
Image rollback does not reverse this migration. There are no new environment
variables. No production migrations or acceptance checks are performed merely by
running local tests.

Dungeon links open the existing Bluds directory filtered to incomplete dungeon
progress. They do not represent farming demand or wishlist totals. Squads, raids,
role limits, signups, rosters, recurrence, notifications, and profile timezone
editing are outside section 11.

Section 12 must lock the same event row for roster assignments and event limit
edits before checking confirmed capacity/role counts, and reject changes to
cancelled events. It must add those roster constraints to event edits when roster
storage exists. No unused signup tables or artificial zero roster counts are
introduced here. Issue #20 remains open for section 12 and production acceptance.

## Local verification: 1 November 2026

Implemented on `feature/event-scheduling`; merge, deployment, and production
acceptance remain pending.

- `TEST_DATABASE_URL=<dedicated disposable PostgreSQL 17 database> POSTGRES_PASSWORD=<local config value> make verify` passed: web typecheck/build, 61 Playwright tests,
  139 standalone API tests, 51 database tests, 22 infrastructure tests, and both
  Compose configurations. Test credentials were synthetic and the dedicated test
  container was removed afterward.
- `ruff format --check` and `ruff check` passed for all 10 changed Python files.
  `git diff --check` passed.
- Browser tests exercised Auckland, Sydney, and Perth dates, mobile layout,
  creation/edit/cancellation persistence, officer assignment controls, repeated
  times and skipped times, destination links, and failed-create recovery. The
  generated mobile event detail screenshot was visually inspected.
- Database tests include a queued edit that loses authorization after an officer
  removes its organizer while holding the event lock. The older handbook migration
  test now isolates migration 0006 so later additive migrations do not break it.
- The API suite emits an existing Starlette/httpx deprecation warning; checks pass.

Issue #20 remains open for section 12. Review/merge, production migration/deployment,
and dedicated-record production acceptance remain outstanding.

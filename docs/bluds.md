# Bluds

Bluds provides a focused guild character directory. `/bluds` replaces the roster placeholder; `/roster` redirects
while preserving query parameters. Character details live at `/bluds/:bludId`.

Each account can create multiple Bluds. Name, class, and the actual character
creation date are required. The date is a calendar date supplied by the member,
separate from the server's record-creation timestamp. Spec, professions and
profession levels can remain unknown. Farming zones are deferred; their former
controls and API fields have been removed while stored values are preserved.

Owners can edit, archive and restore their characters. Officers and the GM can
explicitly enter correction mode for another member's character. The API enforces
these permissions and attributes the latest modification to the actor. Ownership
cannot be reassigned. Archived characters retain their identity and progress,
remain readable by guild viewers, and appear through the archived filter instead
of the default list. An account becoming inactive revokes its access; its Bluds
and their guild-visible history are retained.

Updates are last-write-wins, with no version field, conflict response or custom
concurrency handling. PATCH omits unchanged fields. A supplied profession list
replaces the assignments; supplied dungeon entries update only those entries.
Profession timestamps change only when an assignment or its level changes.
Other edits do not refresh profession timestamps. There is no full edit-history UI.

## Progress and finding characters

Each dungeon has one of `not_completed`, `completed`, or `completed_rerun`.
The last state means **Completed — looking to rerun**. Both completed states
count toward the completion total; rerun interest is shown separately. A dungeon
without saved progress is not completed. Totals use active Blizzard dungeons.
Retired progress is retained and displayed separately. Unknown level ranges are
shown under “Levels unknown.” Suggested levels are guidance, not entry restrictions.
No third-party guide links or curated game facts are supplied.

On each visit to a Blud detail page, Dungeon progress starts collapsed with a
completed/total count. Expand it to view all dungeons and any permitted editing
controls. Collapsing and reopening preserves unsaved selections during that visit.

The directory searches character and member display names. Filters combine Mine,
class, profession, archived state, and one dungeon's exact status.
A selected dungeon defaults to Not completed; status without a dungeon is ignored.
Filters and pagination live in the URL. Lists default to 25 records and cap at
100, ordered by character name then ID. Details link back to the filtered page.

## API and reference contract

- `GET /api/bluds/reference-data`: catalogs, labels, relationships, limits,
  source links, per-category fetch timestamps, refresh-in-progress flag and catalog version.
- `GET /api/bluds`: `q`, `mine`, `archived`, `class_id`, `profession_id`,
  `dungeon_id`, `dungeon_status`, `limit`, `offset`.
- `POST /api/bluds`: name, class, character creation date, optional spec.
  Professions and dungeon progress are maintained on the detail page after creation.
- `GET /api/bluds/{blud_id}`: persisted character and progress, completion totals.
- `PATCH /api/bluds/{blud_id}`: any editable fields, `archived`, `professions`,
  or `dungeons`. Ownership, audit fields and revision fields are not accepted.

Member reads require `bluds.view`, own writes require `bluds.edit_own`, and
cross-owner writes require `shared_records.correct`. See [permissions](permissions.md).

Game catalogs come from Blizzard’s Forever Game Data API through one shared
backend service used by Bluds and Events. Public IDs remain strings. Existing
IDs are retained for verified exact legacy matches; new entries use
`blizzard-{kind}-{numeric ID}`. Established mappings survive renames. Ambiguous
named dungeon wings are not merged into a parent instance.

Each choice includes `active`. Inactive entries provide historical labels and
filters, not new assignments. Existing inactive selections can be kept or cleared.
Retired dungeon progress can be kept or cleared, but cannot be changed to another completed status. Stored
profession levels remain valid when left unchanged, even if a new cap is lower.
Unknown profession classifications are visible but cannot be newly assigned.
Dungeon locations/ranges and profession caps are nullable; caps are enforced only
when Blizzard supplies them. The two-primary-profession rule remains local.

Validated provider GET responses are cached in PostgreSQL for one hour. Complete
categories publish atomically; malformed/failed refreshes preserve the last
successful snapshot. Valid empty indexes retire active choices without deleting
history. No credentials means no refresh; a fresh installation has no active
bundled fallback. Missing classes disable character creation, while other tools
and existing records remain readable.

Expired catalogs are returned silently while a background task refreshes them.
The client polls briefly during an in-progress refresh and otherwise refreshes
hourly. There is no stale-data notice. Open edit forms retain their choices and
values until closed; the API still validates against the current catalog.
See the [operations runbook](operations.md#blizzard-reference-data-issue-57)
for credentials, namespace updates, cache behavior and acceptance steps.

## Deferred scope

Profiles/timezones, main/alt rules, race/current character level,
composition summaries, squads, wishlist features, quest tracking, farming zones
and character synchronization remain deferred. They are not represented as completed by
this feature. No initial spreadsheet/member import is included.

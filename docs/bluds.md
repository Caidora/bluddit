# Bluds

Issue [#18](https://github.com/Caidora/bluddit/issues/18) delivers a focused guild
character directory. `/bluds` replaces the roster placeholder; `/roster` redirects
while preserving query parameters. Character details live at `/bluds/:bludId`.

Each account can create multiple Bluds. Name, class, and the actual character
creation date are required. The date is a calendar date supplied by the member,
separate from the server's record-creation timestamp. Spec, farming zone,
professions and profession levels can remain unknown.

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
Farming-zone timestamps change only when its value changes, including clearing it.
Other edits do not refresh those timestamps. There is no full edit-history UI.

## Progress and finding characters

Each dungeon has one of `not_completed`, `completed`, or `completed_rerun`.
The last state means **Completed — looking to rerun**. Both completed states
count toward the completion total; rerun interest is shown separately. A dungeon
without saved progress is not completed. Totals use the current 35-entry catalog,
including its named wings. Suggested levels are guidance, not entry restrictions.
Available dungeon/quest guides are external links; no quests are copied or tracked.

The directory searches character and member display names. Filters combine Mine,
class, profession, farming zone, archived state, and one dungeon's exact status.
A selected dungeon defaults to Not completed; status without a dungeon is ignored.
Filters and pagination live in the URL. Lists default to 25 records and cap at
100, ordered by character name then ID. Details link back to the filtered page.

## API and reference contract

- `GET /api/bluds/reference-data`: catalogs, labels, relationships, limits,
  source links, review date and catalog version.
- `GET /api/bluds`: `q`, `mine`, `archived`, `class_id`, `profession_id`,
  `farming_zone_id`, `dungeon_id`, `dungeon_status`, `limit`, `offset`.
- `POST /api/bluds`: name, class, character creation date, optional spec/zone.
  Professions and dungeon progress are maintained on the detail page after creation.
- `GET /api/bluds/{blud_id}`: persisted character and progress, completion totals.
- `PATCH /api/bluds/{blud_id}`: any editable fields, `archived`, `professions`,
  or `dungeons`. Ownership, audit fields and revision fields are not accepted.

Member reads require `bluds.view`, own writes require `bluds.edit_own`, and
cross-owner writes require `shared_records.correct`. See [permissions](permissions.md).

Game facts are declared in the API, not duplicated in the frontend. IDs are stable
Bluddit keys, not claims about Blizzard IDs. A future provider integration must
map into these IDs and retain the client contract. The current implementation
requires no provider credentials, network access during requests, or catalog UI.
Sources were rechecked on **1 November 2026**:

- [Blizzard's nine new dungeons](https://news.blizzard.com/en-gb/article/24301455/explore-the-new-dungeons-of-world-of-warcraft-forever): authoritative published ranges for those dungeons.
- [Icy Veins dungeon overview](https://www.icy-veins.com/wow-forever/dungeons-overview/): the 35-entry checklist, other suggested ranges, available guide links and class/spec guides.
- [Blizzard character reference](https://worldofwarcraft.blizzard.com/en-us/news/24304075/): supported classes.
- [Blizzard profession overview](https://news.blizzard.com/en-us/article/24301516/gather-around-the-campfire-in-world-of-warcraft-forever): nine primaries, up to two per character, and all three secondaries.
- [Icy Veins professions](https://www.icy-veins.com/wow-forever/professions-overview): skill caps.
- [Icy Veins zones](https://www.icy-veins.com/wow-forever/zones-and-maps): Classic outdoor/city choices plus Mount Hyjal, Riverglades, Shen'Dralas and Zephras Isle.
- [Wowhead dungeon quests](https://www.wowhead.com/forever/guide/dungeons/every-dungeon-quest-location): additional reference, explicitly identifying beta and Classic-derived information.

Published ranges disagree in places: Hall of Thanes uses Blizzard's 13–18,
Ruins of Lordaeron 15–20, Excavation Site 24–29, and City of Dalaran 28–33.
High-level guides marked Coming Soon have no fabricated URLs. See the
[operations runbook](operations.md#bluds-migration-and-reference-updates) for catalog updates.

## Deferred migrated requirements

This delivery supersedes the broader implementation scope originally migrated
into #18. Profiles/timezones, main/alt rules, race/current character level,
composition summaries, squads, wishlist features, quest tracking, and external
catalog integration remain deferred. They are not represented as completed by
this feature. No initial spreadsheet/member import is included.

# Bluddit: Release 1 feature plan

## Product direction

Give Bluds a useful member website for WoW Forever characters, gear goals, activities, crafting help, and guild knowledge. The [Bludlets spreadsheet](https://docs.google.com/spreadsheets/d/1CtopiBvc1u_skUH29yOnmCAhc2qDYqVqrAiMTNWOgYE/edit) provides context and ideas; its structure and formulas do not define the product or the release checklist.

See the [README](README.md#project-status) for current availability. The sections below describe intended behavior, including work that is still planned.

## Accounts and access

Username/password registration creates a pending Member requiring officer approval. Active members use server-side sessions. Officers administer membership and guild knowledge; only the GM changes account roles or transfers the GM role. Password recovery uses the administrative CLI, without email or third-party login integration.

Permissions gate actions, with persisted ownership or management relationships limiting the records each action can affect. Enforce both at the API. Organizer and quartermaster responsibilities are not additional account roles. Do not introduce assignment machinery until the corresponding feature needs it.

## Bluds

- Members maintain multiple characters and browse a searchable guild directory with character details.
- Name, class, and user-entered creation date are required. Spec, professions and levels, and farming zone can remain blank. Show when profession and farming-zone information was updated.
- Dungeon progress distinguishes not completed, completed, and completed with interest in rerunning. Both completed states count as complete.
- Search and filters help members find characters by owner/name, class, profession, farming zone, or dungeon status, including a view of their own characters.
- Owners edit their characters; Officer/GM corrections are explicit and cannot reassign ownership. Archive/restore preserves character identity and progress.
- Typed, API-owned reference data supplies stable IDs and available dungeon level ranges and guide/quest links. No live game-data provider or quest tracking is required.
- Character updates use last-write-wins behavior; revision/conflict workflows are outside the agreed character scope.

Profiles/timezones, main/alt constraints, race/current level, composition summaries, and squads are deferred from this character scope.

## Events

Any active member can create an activity. Use a general event with optional fields such as destination, maximum group size, and expected duration, rather than requiring a separate model for every activity. Support dungeon runs, leveling, questing, PvP, and guild meetings; raid-specific support is deferred.

Store one authoritative start instant and show a clearly labelled time in the viewer’s timezone. Handle daylight-saving transitions and date changes across Auckland, Sydney, and Perth. Members can sign up with a character and role, change availability, or withdraw. Availability and organizer-assigned confirmed/standby status are separate; one member has one signup per event. Event managers maintain the event and roster through explicit resource authorization. Validate optional capacity and role limits where supplied.

Do not make event creation depend on deferred squads or guild farming rankings. Precise timezone handling belongs to the scheduling workflow; it does not require the broader deferred member-profile feature.

## Personal gear wishlist

Members maintain character-owned targets with item, slot, intended role/spec, source, optional boss, notes, and needed/acquired status. Support adding, editing, deleting, filtering, marking acquired, and undoing an acquisition. Prevent accidental exact duplicates while keeping different characters’ needs separate.

Use explicit item descriptions and stable source IDs for dungeons, crafting, quests, and other sources, without requiring an external item API. Enforce ownership and explicit officer corrections. Guild-wide dungeon rankings and composition/farming dashboards are deferred; a personal wishlist can ship independently.

## Materials and crafters

Search materials or categories to find designated recipients, intended outputs, priorities, and delivery instructions. Link crafters to maintained character professions, specializations, accepted materials, and deliverables. Recipients can include multiple characters and a named guild-bank destination without inventory accounting.

Officer/GM maintenance must preserve explicit recipient assignments rather than infer delivery destinations from professions. Show inactive recipients clearly. Any delegated quartermaster controls need an explicit scoped authorization model. Automated camp-buff coverage and profession-composition dashboards are deferred.

## Guild handbook

Start with an empty handbook. Officers author sections about rules, leadership, expectations, and useful guild knowledge; the application does not seed policy prose or contacts. Members browse and search current content. Edits retain immutable, attributable revisions and detect stale saves. Render content safely; richer Markdown formatting is a planned improvement. Related features can link to handbook guidance without copying policy text.

## Member home

Connect the completed tools through upcoming activities and signup/roster status, character and wishlist shortcuts, crafter/material search, and handbook access. Reuse current records rather than maintain duplicate totals. Provide useful empty states and a route into character setup for a new member. Deferred squads and farming dashboards are not prerequisites for a useful home page.

## Database recovery

Expand the existing deployment backup/restore checks into an operational recovery path: documented snapshots and restores, configurable retention, scheduled backups, and storage outside the application host’s failure boundary. Restore into an isolated database and verify representative records. Backup failures must be visible to the operator. Existing on-host deployment backups alone do not provide disaster recovery.

## Delivery and boundaries

Common workflows must work on a phone and with a keyboard, with clear loading, empty, validation, and error states. Deliver complete database/API/UI behavior with server authorization, meaningful verification, and deployment evidence. Do not infer availability from a placeholder page or from work being closed without implementation.

Squads, leveling pairs, composition summaries, guild farming rankings, camp-buff coverage, automated spreadsheet import, and a formal spreadsheet cutover are not current release commitments. AI product features, crafting requests, cooldown/loot tracking, recurring events, and notifications require separately agreed scope.

The sheets can inform future decisions without requiring a migration project. If data is ever brought across, confirm ownership and actual values first: template wishlists, planned characters, estimated levels, broad regions, and suggested schedule windows must not silently become authoritative member data or events. Preserve member edits and do not add live synchronization by default.

Use the architecture in the [high-level plan](high-level-plan.md) and delivery practices in the [contribution guide](contributions.md). Release readiness depends on the agreed member workflows, permissions, regional times, and recoverable data working in production, rather than parity with every spreadsheet tab.

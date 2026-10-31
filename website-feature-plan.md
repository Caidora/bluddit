# Bluddit: release 1 feature plan

## Goal

Replace the guild spreadsheet with a simple website where members maintain their characters, track gear goals, join runs, and find the right guild crafters.

The main workflow is **update my character → identify upgrades → join a useful run → record what I acquired**.

Based on `high-level-plan.md` and the four tabs of the [Bludlets spreadsheet](https://docs.google.com/spreadsheets/d/1CtopiBvc1u_skUH29yOnmCAhc2qDYqVqrAiMTNWOgYE/edit).

## Release 1 overview

| Feature | What members can do |
| --- | --- |
| Profiles and roster | Maintain characters and professions; find members and view squads |
| Gear wishlists | Track needed and acquired items; see which dungeons benefit the guild |
| Events and signups | See local start times, sign up with a character and role, and check roster status |
| Crafting directory | Find crafters, material recipients, and delivery instructions |
| Guild handbook | Read the charter, leadership responsibilities, and operational rules |
| Member home page | See upcoming events and quickly reach personal and guild information |

## 1. Profiles, roster, and squads

- Members sign in and edit their own profile and timezone.
- Characters include main/alt status, class, race, current level, primary and secondary roles, and professions.
- Members can filter the roster by role, profession, squad, or region.
- Officers maintain Alpha, Bravo, flex assignments, and leveling pairs.
- Squad pages show members, assigned roles, and relevant class utility.
- Class, role, armor, and profession summaries update automatically from character records.

## 2. Gear wishlists and farming priorities

- Members add, edit, remove, and filter targets for their own characters.
- Targets include item name, slot, role/spec, source, boss, notes, and Needed/Acquired status.
- Members mark items acquired and can undo mistakes.
- The guild view ranks dungeons by outstanding target count and shows the members and items behind each ranking.
- Crafting and quest targets remain identifiable separately from dungeon drops.
- Personal and guild totals update automatically when targets change.

Label the progress metric **wishlist completion** so its meaning is clear.

## 3. Events and signups

- Members see upcoming runs with destination, organizer, start time, expected duration, requirements, and open roles.
- Start times display in each member’s timezone, including daylight-saving changes.
- Members sign up with a character and role, indicate tentative availability, or decline.
- Members can change or withdraw signups and see pending, confirmed, or standby status.
- Organizers create events, assign rosters, and fill gaps with flex members.
- Events link to destination wishlist needs to help organizers choose useful runs.
- Group capacity and required roles are configurable for the activity.

## 4. Crafting and material directory

- Search materials or categories to find designated recipients, intended outputs, priorities, and delivery instructions.
- View crafters’ professions, accepted materials, deliverables, and specializations.
- Read routing rules for drops, recipes, gems, and other guild resources.
- See profession and camp-buff coverage based on maintained assignments.
- Quartermasters update routing instructions and designated recipients.

## 5. Guild handbook

- Publish the charter, leadership responsibilities, attendance expectations, loot policy, material-handling rules, and communication standards.
- Link relevant rules from event and directory pages.
- Officers can edit handbook content, with an updated date and change history.
- Show the appropriate contacts for private concerns.

## 6. Member home page

- My upcoming events, local start times, and roster status.
- Links to my characters, squad, and wishlist.
- Dungeons that benefit me and current guild farming priorities.
- Material/crafter search and handbook access.

Navigation: **Home · Roster & Squads · Gear & Farming · Events · Crafting Directory · Guild Handbook**.

All core actions should work comfortably on a phone, with clear forms and readable lists.

## Access

| User | Permissions |
| --- | --- |
| Member | View member areas; edit own profile, characters, wishlist, and signups |
| Organizer / squad lead | Manage assigned squads, events, and rosters |
| Quartermaster | Maintain material routing and crafter assignments |
| Officer / admin | Approve membership, edit rules, and correct shared records; only the GM promotes/demotes account roles or passes GM |

Use session-based authentication. Membership requires an invitation or officer approval.

Release 1 uses officer-approved registration. Each account has one role, with
permissions defined by fixed Python mappings. The Guild Master is protected from
Officer changes and delegates that role through an atomic transfer. Resource
ownership and manager/quartermaster assignments further constrain feature actions.

## Before launch

- Confirm member data and wishlist entries before importing them: the wishlist is labelled as a template.
- Keep planned alternates and expected maximum levels separate from existing characters and current levels.
- Confirm server-specific classes, item sources, and camp-buff rules.
- Choose the authoritative event schedule: the sheet lists both 20:30 and 21:00 NZDT windows.
- Collect precise member timezones instead of relying on “AU” or “NZ” labels.
- Import shared information once and calculate summaries from those records, including newly added members and items.
- Trial with a squad across the regions, reconcile the data, and set a date for switching from the sheet.
- Preserve a sheet snapshot and provide core data exports and database backups.

## Completion criteria

Release 1 is complete when members can maintain their own characters and wishlists, find crafters and guild rules, and join a run without using the spreadsheet. Organizers can see member needs, assign a roster, and communicate one correct event time across regions.

Use the stack specified in `high-level-plan.md`: React Router framework with client-side rendering (CSR / SPA mode), FastAPI, PostgreSQL with explicit SQL and no ORM, Nginx, session authentication, Docker Compose, and GitHub Actions.

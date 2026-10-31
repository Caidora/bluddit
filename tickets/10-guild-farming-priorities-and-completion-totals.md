# 10: Guild farming priorities and completion totals

Status: Not started

Dependencies: Ticket 09.

## Outcome

Replace wishlist formulas with live demand queries.

## Implementation

- Add guild and character totals for needed/acquired items and wishlist completion, excluding archived characters and unconfirmed import drafts.
- Group outstanding dungeon targets by canonical source and return item count, distinct benefiting member count, and item/member/boss details.
- Rank by needed-item count descending and use a stable name-based tie-breaker. Keep crafting, quest, and other targets outside dungeon rankings.
- Build Gear & Farming views with drill-down into a dungeon and links to member wishlists.
- Return zero completion for an empty list and label the metric “wishlist completion.”

## Acceptance and verification

Adding or acquiring a target updates totals and rank. One member needing several items counts once in distinct members. Fixtures cover ties, empty lists, archived characters, and non-dungeon sources.

Implement meaningful checks for the behavior and failure paths above. Record commands run and results in the completion notes; do not claim external verification that has not happened.

## Completion notes

To be filled in by the implementing AI: changes, migrations/configuration, verification evidence, and any unresolved acceptance items.

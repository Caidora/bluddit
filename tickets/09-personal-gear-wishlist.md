# 09: Personal gear wishlist

Status: Not started

Dependencies: Ticket 06.

## Outcome

Implement member-owned target items and acquisition updates.

## Implementation

- Add shared source records with source type (dungeon, crafting, quest, or other) and stable IDs. Add wishlist targets referencing a character and source, with item name, slot, intended role/spec, optional boss, notes, and Needed/Acquired status.
- Implement target list/create/update/delete endpoints scoped to character ownership, with officer corrections.
- Build My Wishlist and member wishlist views with character, slot, source, and status filters.
- Allow acquisition and undo through the same validated update path.
- Use explicit item/source fields rather than external item APIs. Handle equivalent source naming through canonical source IDs.
- Prevent accidental exact duplicate targets for the same character, item, slot, and intended role. Keep different characters’ needs separate.

## Acceptance and verification

A member can create, update, acquire, undo, and delete a target. Cross-member writes fail. Source/status filters work and an empty wishlist has a clear add action.

Implement meaningful checks for the behavior and failure paths above. Record commands run and results in the completion notes; do not claim external verification that has not happened.

## Completion notes

To be filled in by the implementing AI: changes, migrations/configuration, verification evidence, and any unresolved acceptance items.

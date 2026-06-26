---
description: dramaturgy — write a meaning-map card for each area
argument-hint: "[area-id]  (optional; omit to do all areas)"
---

Generate meaning-map cards for the areas in `.dramaturgy/area-tree.json` and
write each to `.dramaturgy/area-maps/<area-id>.json`.

For the area id in `$1` (or every area if `$1` is empty):
1. Run `dra pack --area-id <id>` to gather the analysis pack.
2. Read the pack and produce a card: actors and their actions, key concepts,
   key flows, CRUD summary, related tables/APIs/screens, code refs, state
   transitions, risk points, open_questions, confidence. Keep implementation
   detail out of the body but keep references to the evidence. Separate
   inference from evidence.
3. Write a single-area area-map JSON to `.dramaturgy/area-maps/<id>.json`,
   pretty-printed (indent 2), with `"content_lang"` matching the config.
4. If `dra pack` warned the area is too large, run
   `dra subdivide --area-id <id>` and propose natural sub-areas to the user
   instead of forcing one giant card.

When done, tell the user to finalize (`/dramaturgy:finalize`).

---
description: dramaturgy — merge area cards, validate, and render the HTML
---

Merge the per-area cards into the canonical meaning map, validate it, and
render the HTML view.

Steps:
1. Run `dra merge` (merges `.dramaturgy/area-maps/*.json` into
   `.dramaturgy/meaning-map.json`).
2. Run `dra validate`. If it reports errors, fix them by editing the
   canonical JSON (`.dramaturgy/meaning-map.json` / `area-tree.json`) — these
   are the source of truth — then re-run `dra validate` until it passes.
   Surface any `confidence: low` items and any warnings to the user.
3. Run `dra render` to produce `.dramaturgy/meaning-map.html`.
4. Tell the user they can open the HTML, or run `dra serve` to view and edit
   the map in the browser (edits there write back to the JSON).

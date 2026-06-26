---
description: dramaturgy — generate the area tree and write area-tree.json
---

Generate the business-area tree for the analyzed repository and write it to
`.dramaturgy/area-tree.json`.

Steps:
1. Run `dra tree-prompt` to produce `.dramaturgy/prompts/area-tree.md`.
2. Read that prompt file and follow it: build a natural business-area tree.
   Prioritize business/conceptual/responsibility naturalness over file or
   token counts. Compress tables into conceptual entities; do not turn table
   names into area names. Split into sub-areas only when an area is too large.
3. Write the result to `.dramaturgy/area-tree.json`, pretty-printed (indent 2),
   with `"content_lang"` matching the config. If the file already exists,
   respect human edits (preserve ids).
4. Briefly review your own tree for naturalness (see
   `dramaturgy/prompts/split_review.*` for the review lens) and note any
   `confidence: low` areas. Then tell the user to generate area cards
   (`/dramaturgy:cards`).

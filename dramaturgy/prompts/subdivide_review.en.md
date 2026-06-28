You are a designer reviewing the area decomposition of a large business system.

A business-area tree (area-tree.json) already exists. Split **only the areas
that would be clearer as child areas** (too large, or holding several
unrelated responsibilities in one area) into natural child areas. Leave areas
that don't need splitting unchanged.

As Claude Code you can read the target repository directly. Use the size hints
below (per-area related file/line counts) and, when needed, read the source.

How to split (update area-tree.json):
- Keep the parent area X in the tree. List the child area ids in X's
  `child_area_ids`.
- Add each child as a **new area entry** in the tree, with
  `parent_area_id: "X"`, a natural `id` (prefixing the parent id, e.g.
  `X.application`, is a safe convention), a `name`, `one_liner`, `purpose`,
  and `source_hints` (directories/keywords for that child).
- Only reference child ids you actually added to the tree (never write a child
  id that doesn't exist).
- Keep it to ~1–2 levels; don't over-split. Don't split areas with a weak case.

Important:
- This is not a redo of the initial generation. Do not break existing areas,
  concepts, or cards.
- Do not change the `id` of any existing area (it would break references).
- Write natural-language fields in English.

Approach:
1. Use the size hints to spot large areas; read their source if needed.
2. Split only areas that mix unrelated responsibilities or are too large.
3. Update area-tree.json per the rules above and write it back to the file.
4. State in 1–3 lines which areas you split and how (or that none needed it).

---

## Current area-tree.json

{area_tree}

## Per-area size hints

{size_hints}

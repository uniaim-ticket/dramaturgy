
---

## Output target (important)

You are running as Claude Code. Do not paste the result into chat; write it
directly to a file.

- Write the generated area-tree JSON, **pretty-printed (indent 2)**, to:
  `{area_tree_path}`
- Include `"content_lang": "{lang}"` at the top of the JSON.
- If the file already exists, update it while respecting human edits
  (preserve ids; do not needlessly recreate entries).
- After writing, state a 1–3 line summary of what changed.

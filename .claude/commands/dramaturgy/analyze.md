---
description: dramaturgy — inventory the target repo (files & directories only)
---

Run the mechanical inventory step of dramaturgy for the repository at the
current working directory (or the `repo_root` in `.dramaturgy/config.json`).

Steps:
1. If `.dramaturgy/config.json` does not exist, run `dra setup --no-input`
   (ask the user for `ui_lang` / `content_lang` if they haven't said).
2. Run `dra analyze-repo`. This only collects a reliable file/directory
   inventory (paths, extensions, line counts, per-directory aggregates).
3. Report the file/line counts and the largest directories, and tell the user
   the next step is to generate the area tree (`/dramaturgy:tree`).

Do NOT try to extract tables, entities, routes, or "roles" mechanically.
Those are discovered later by reading the source (in `/dramaturgy:tree` and
`/dramaturgy:cards`). This step gathers only the inventory.

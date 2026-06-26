---
description: dramaturgy — index the target repo (source + schema + area candidates)
---

Run the mechanical analysis step of dramaturgy for the repository at the
current working directory (or the `repo_root` in `.dramaturgy/config.json`).

Steps:
1. If `.dramaturgy/config.json` does not exist, run `dra setup --no-input`
   (ask the user for `ui_lang` / `content_lang` if they haven't said).
2. Run `dra analyze-repo`.
3. Run `dra analyze-schema` (it scans for `*.sql`; pass `--schema <file>` if
   the user points at a specific DDL file).
4. Run `dra candidates`.
5. Report the file/line/table counts and tell the user the next step is to
   generate the area tree (`/dramaturgy:tree`).

Do not make semantic judgments here — this step only gathers material.

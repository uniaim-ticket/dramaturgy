# Meaning Map

Generate a compact, human-readable **meaning map** of a large existing system,
driven from inside Claude Code. CLI tools gather material and run mechanical
checks; Claude makes the semantic judgments (area boundaries, naming, concept
compression). The canonical artifacts are `area-tree.json` and
`meaning-map.json`; the HTML is a generated view.

日本語版は [README.ja.md](README.ja.md) を参照してください。

## Bilingual by design

Language is handled in two independent layers (they may be mixed):

| Layer | Setting | Controls |
| --- | --- | --- |
| UI / CLI | `ui_lang` | CLI messages and HTML chrome (labels, nav) — the operator's language |
| Content | `content_lang` | The generated meaning map itself and the Claude prompts — chosen to match the target system |

Supported languages: **`ja`** and **`en`**. A single canonical JSON holds one
`content_lang`; to get another language, change `content_lang` and regenerate
(no multilingual fields). Adding a language = adding a message catalog and the
prompt templates; no code change.

## Requirements

Python 3.10+ (standard library only — no external dependencies).

## Install

```bash
pip install -e .        # exposes the `dra` (and `dramaturgy`) command
```

Both `dra` and the full name `dramaturgy` resolve to the same CLI; `dra` is
the short alias. Without installing you can also run `python -m dramaturgy`.

## Quick start

```bash
# 0. Set ui_lang / content_lang / project, writing .dramaturgy/config.json
dra setup --ui-lang en --content-lang en \
  --project-name "My System" --repo-root /path/to/target

# 1-3. Gather material
dra analyze-repo   --repo-root /path/to/target
dra analyze-schema --schema /path/to/target/db/schema.sql --repo-root /path/to/target
dra candidates     --repo-root /path/to/target

# 4. Build the prompt for Claude, then have Claude write area-tree.json
dra tree-prompt    --repo-root /path/to/target
#    -> .dramaturgy/prompts/area-tree.md   (run it in Claude; save area-tree.json)

# 5. Per area: build a pack, have Claude write the area map JSON
dra pack      --area-id sales --repo-root /path/to/target
dra subdivide --area-id sales --repo-root /path/to/target   # if too large

# 6-8. Merge, validate, render
dra merge    .dramaturgy/area-maps/*.json --repo-root /path/to/target
dra validate --repo-root /path/to/target
dra render   --repo-root /path/to/target
```

Every command accepts `--ui-lang`, `--content-lang` (generators only) and
`--repo-root` to override `config.json` per invocation. Run `dra --help` for
the command list and `dra <command> --help` for command options.

## Commands

| Command | Role |
| --- | --- |
| `dra setup` | Write `.dramaturgy/config.json` (languages + project) |
| `dra analyze-repo` | Index source files, roles, routes, table hints |
| `dra analyze-schema` | Parse SQL DDL into tables / FKs / status columns |
| `dra candidates` | Grouping material (dirs, FK graph, API prefixes) |
| `dra tree-prompt` | Render the `content_lang` area-tree prompt |
| `dra pack` | Gather one area's files/tables/APIs; warn if too large |
| `dra subdivide` | Propose natural sub-areas (never auto-splits) |
| `dra merge` | Merge per-area maps; detect dup ids / drift / orphans |
| `dra validate` | Mechanical consistency + language invariants |
| `dra render` | Render `meaning-map.json` to a self-contained HTML |

## Principles

- CLIs collect material and run mechanical checks; **Claude makes meaning
  judgments.** Oversized areas yield a *suggested* subdivision, never an
  automatic split.
- Intermediate JSON is pretty-printed UTF-8 for reviewable Git diffs.
- `validate_map.py` enforces the language invariants: supported codes, a
  recorded `content_lang` matching config, and catalogs with no key drift.

## Development

```bash
python -m unittest discover tests        # or: python -m pytest tests/
```

## License

MIT — see [LICENSE](LICENSE).

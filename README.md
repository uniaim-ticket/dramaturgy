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

## Quick start

```bash
# 0. Set ui_lang / content_lang / project, writing .meaning-map/config.json
python tools/meaning_map/setup.py --ui-lang en --content-lang en \
  --project-name "My System" --repo-root /path/to/target

# 1-3. Gather material
python tools/meaning_map/analyze_repo.py            --repo-root /path/to/target
python tools/meaning_map/analyze_schema.py --schema /path/to/target/db/schema.sql
python tools/meaning_map/propose_area_candidates.py --repo-root /path/to/target

# 4. Build the prompt for Claude, then have Claude write area-tree.json
python tools/meaning_map/build_area_tree_prompt.py  --repo-root /path/to/target
#    -> .meaning-map/prompts/area-tree.md   (run it in Claude; save area-tree.json)

# 5. Per area: build a pack, have Claude write the area map JSON
python tools/meaning_map/build_area_pack.py --area-id sales --repo-root /path/to/target
python tools/meaning_map/suggest_subdivision.py --area-id sales --repo-root /path/to/target  # if too large

# 6-8. Merge, validate, render
python tools/meaning_map/merge_maps.py .meaning-map/area-maps/*.json --repo-root /path/to/target
python tools/meaning_map/validate_map.py --repo-root /path/to/target
python tools/meaning_map/render_html.py  --repo-root /path/to/target
```

Every CLI accepts `--ui-lang`, `--content-lang` (generators only) and
`--repo-root` to override `config.json` per invocation.

## Tools

| Tool | Role |
| --- | --- |
| `setup.py` | Write `.meaning-map/config.json` (languages + project) |
| `analyze_repo.py` | Index source files, roles, routes, table hints |
| `analyze_schema.py` | Parse SQL DDL into tables / FKs / status columns |
| `propose_area_candidates.py` | Grouping material (dirs, FK graph, API prefixes) |
| `build_area_tree_prompt.py` | Render the `content_lang` area-tree prompt |
| `build_area_pack.py` | Gather one area's files/tables/APIs; warn if too large |
| `suggest_subdivision.py` | Propose natural sub-areas (never auto-splits) |
| `merge_maps.py` | Merge per-area maps; detect dup ids / drift / orphans |
| `validate_map.py` | Mechanical consistency + language invariants |
| `render_html.py` | Render `meaning-map.json` to a self-contained HTML |

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

# dramaturgy

Generate a compact, human-readable **meaning map** of a large existing system.
Mechanical steps (indexing, validation, HTML rendering) are scripted; the
semantic work (area boundaries, naming, concept compression) is done by
**Claude Code**. The canonical artifacts are `area-tree.json` and
`meaning-map.json`; the HTML is a generated, editable view.

You do not run the analysis by hand. You either:

- **drive it from a local web UI** (`dra serve`) that views/edits the map and
  invokes Claude Code for you, or
- **drive it from inside Claude Code** with the bundled custom commands
  (`/dramaturgy:analyze`, `:tree`, `:cards`, `:finalize`).

日本語版は [README.ja.md](README.ja.md) を参照してください。

## How it works

```
            ┌─────────────── you ───────────────┐
            │                                    │
      web UI (dra serve)                 Claude Code session
            │                                    │
            ▼                                    ▼
   ┌──────────────────────────────────────────────────┐
   │  mechanical CLI:  analyze · merge · validate · render │
   │  (stdlib Python, no semantic judgment)             │
   └──────────────────────────────────────────────────┘
            │                                    ▲
            ▼  invokes (headless)                │ writes JSON back
      ┌───────────────┐                          │
      │  Claude Code   │ ── generates area tree / area cards ──┘
      └───────────────┘
                       canonical: .dramaturgy/area-tree.json
                                  .dramaturgy/meaning-map.json
```

The web UI invokes Claude Code as a headless subprocess
(`claude -p … --output-format stream-json --permission-mode acceptEdits`),
the same model the
[requirements-reviewer](https://github.com/uniaim-ticket/requirements-reviewer)
project uses. Claude writes the JSON artifacts directly; the UI re-renders the
HTML from JSON and lets you edit cards, **writing edits back to the JSON**.

## Bilingual by design

Language is handled in two independent layers (they may be mixed):

| Layer | Setting | Controls |
| --- | --- | --- |
| UI / CLI | `ui_lang` | CLI messages, web-UI chrome, HTML labels — the operator's language |
| Content | `content_lang` | The generated meaning map itself and the Claude prompts — chosen to match the target system |

Supported languages: **`ja`** and **`en`**. A single canonical JSON holds one
`content_lang`; to get another language, change `content_lang` and regenerate
(no multilingual fields).

## Requirements

- Python 3.10+ (standard library only — no external Python dependencies, no
  Node/build step).
- The [Claude Code](https://claude.com/claude-code) CLI (`claude`) on your
  PATH, for the generation steps.

## Install

Installing exposes the `dra` (and full-name `dramaturgy`) command. Pick one:

```bash
# A) virtual environment (recommended, no system impact)
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e .
dra --version

# B) pipx (isolated, on PATH globally)
pipx install -e .

# C) user install
pip install -e . --user
```

On Debian/Ubuntu and other PEP 668 "externally-managed" environments, a bare
`pip install` is blocked. Use option A or B, or add
`--break-system-packages` to a `--user` install:

```bash
pip install -e . --user --break-system-packages
```

If `dra` is installed but "command not found", the install's bin directory is
not on your `PATH`. For a `--user` install add it:

```bash
export PATH="$(python3 -m site --user-base)/bin:$PATH"   # e.g. ~/.local/bin
```

**No-install fallback** — from the repo root you can always run the CLI as a
module, which needs no install and no PATH changes:

```bash
python3 -m dramaturgy --version
python3 -m dramaturgy serve --repo-root /path/to/target
```

Substitute `python3 -m dramaturgy` for `dra` in any command below.

## Usage — web UI (recommended)

```bash
dra setup --repo-root /path/to/target      # choose ui_lang / content_lang / project
dra serve --repo-root /path/to/target      # opens http://127.0.0.1:5178/app/
```

The UI is a **map preview + a review queue**. The flow is:

1. **Initialize all with Claude** (button in the header) — runs the whole
   pipeline as one job (analyze → area tree → area cards → merge → validate →
   render) and reports progress live (elapsed time, the Claude process id, and
   its CPU/memory, so you can see the session is alive). Transient Claude API
   errors are retried; an area that still fails is skipped and reported so the
   run finishes with a partial map you can complete later.
2. **Read the preview** on the left. It shows actors (first), **concept data**
   (physical tables grouped by business meaning) with the areas that use them,
   business areas as clickable boxes, and **CRUD** viewable both *by area* and
   *by concept*.
3. **Add findings inline**: click the **+** on any actor, concept, or area to
   open a small popover, pick a kind, write a remark, and either *Add to queue*
   or *Add & run*. Each finding (a remark) has one of three kinds, processed
   differently:

   | Kind | What Claude does | Where it goes |
   | --- | --- | --- |
   | **reframe** | accept the remark and re-organize the understanding | edits `meaning-map.json` |
   | **audit** | check for contradictions / cases it can't explain | writes `audits/<id>.json`; map unchanged |
   | **proposal** | record a desired future change | writes `proposals/<id>.md`; as-is map unchanged |

4. **Process the queue** on the right: run findings individually, or **Run
   queued** to process all open ones in order. Toggle **continue Claude
   session** to keep context across findings, or leave it off to run each in a
   fresh session. Findings persist in `.dramaturgy/reviews.json`; after a
   reframe the preview refreshes automatically.

## Usage — inside Claude Code

With this repo's `.claude/commands/` available, run in a Claude Code session
opened on your target repository:

```
/dramaturgy:analyze        # inventory repo files/dirs (no semantic extraction)
/dramaturgy:tree           # Claude reads the source, builds area-tree.json
/dramaturgy:cards [id]     # Claude reads the files, writes area-maps/<id>.json
/dramaturgy:finalize       # merge + validate + render
```

## Commands (scriptable / internal)

`setup` and `serve` are the entry points. The rest are the mechanical steps
the web UI and slash commands call; they're exposed for scripting too.

| Command | Role |
| --- | --- |
| `dra setup` | Write `.dramaturgy/config.json` (languages + project) |
| `dra serve` | Start the web UI; drives Claude Code and writes edits back |
| `dra analyze-repo` | Inventory files/dirs only (paths, line counts) — no semantic extraction |
| `dra tree-prompt` | Render the `content_lang` area-tree prompt |
| `dra pack` | List one area's files for Claude to read; warn if too large |
| `dra subdivide` | Propose natural sub-areas (never auto-splits) |
| `dra merge` | Merge per-area maps; detect dup ids / drift / orphans |
| `dra validate` | Mechanical consistency + language invariants |
| `dra render` | Render `meaning-map.json` to a self-contained HTML |

## Principles

- Mechanical steps gather only **reliable facts** (the file/directory
  inventory). They do **not** guess tables, entities, routes, or roles —
  those depend on the framework/ORM and are discovered by **Claude reading
  the actual source**. Oversized areas yield a *suggested* subdivision, never
  an automatic split.
- The canonical sources are the JSON files; HTML is a generated view, and
  edits in the UI are written back to JSON. Intermediate JSON is
  pretty-printed UTF-8 for reviewable Git diffs.
- `dra validate` enforces the language invariants: supported codes, a recorded
  `content_lang` matching config, and message catalogs with no key drift.
- The server binds to `127.0.0.1` only — it is a local single-user tool.

## Development

```bash
python -m unittest discover tests        # or: python -m pytest tests/
```

## License

MIT — see [LICENSE](LICENSE).

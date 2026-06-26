#!/usr/bin/env python3
"""build_area_tree_prompt.py — generate the area-tree prompt for Claude.

Reads source-index / schema-index / area-candidates, builds compact
summaries (so the prompt stays readable rather than dumping every file),
and fills the language-specific ``area_tree`` template chosen by
``content_lang``. Writes ``.meaning-map/prompts/area-tree.md``.

The prompt instructions are in ``content_lang`` and ask Claude to write the
generated fields in that same language and to stamp ``content_lang`` into
the output JSON.
"""

from __future__ import annotations

import argparse
import json

from common.bootstrap import setup_path

setup_path()

from common.config import add_lang_args, resolve  # noqa: E402
from common.paths import read_json, workspace_dir  # noqa: E402
from common.prompts import render_prompt  # noqa: E402


def _summarize_source(idx: dict) -> str:
    s = idx.get("summary", {})
    lines = [
        f"- files: {s.get('files', 0)}, lines: {s.get('lines', 0)}",
        f"- by_role: {json.dumps(s.get('by_role', {}), ensure_ascii=False)}",
        f"- by_ext: {json.dumps(s.get('by_ext', {}), ensure_ascii=False)}",
    ]
    return "\n".join(lines)


def _summarize_schema(idx: dict | None) -> str:
    if not idx:
        return "(no schema)"
    tables = idx.get("tables", [])
    lines = [f"- tables: {len(tables)}"]
    for t in tables[:80]:
        flag = f" [{','.join(t['flags'])}]" if t.get("flags") else ""
        status = (f" status={t['status_columns']}"
                  if t.get("status_columns") else "")
        lines.append(f"  - {t['name']} ({t['column_count']} cols){flag}{status}")
    if len(tables) > 80:
        lines.append(f"  ... and {len(tables) - 80} more tables")
    return "\n".join(lines)


def _summarize_candidates(cand: dict) -> str:
    parts = []
    dg = cand.get("directory_groups", [])[:15]
    parts.append("directory_groups (top by lines):")
    parts += [f"  - {g['dir']}: {g['files']} files / {g['lines']} lines" for g in dg]
    edges = cand.get("table_graph", {}).get("edges", [])
    parts.append(f"table_graph edges: {len(edges)}")
    parts += [f"  - {e['from']} -> {e['to']}" for e in edges[:40]]
    api = cand.get("api_prefix_groups", [])[:15]
    parts.append("api_prefix_groups:")
    parts += [f"  - {g['prefix']}: {len(g['routes'])} routes" for g in api]
    lc = cand.get("lifecycle_candidates", [])[:30]
    parts.append("lifecycle_candidates:")
    parts += [f"  - {c['table']}: {c['status_columns'] + c['enum_columns']}"
              for c in lc]
    return "\n".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build area-tree prompt")
    add_lang_args(parser)
    parser.add_argument("--source-index", default=None)
    parser.add_argument("--schema-index", default=None)
    parser.add_argument("--area-candidates", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)
    rs = resolve(args)
    ws = workspace_dir(rs.config.repo_root)

    print(rs.ui.t("prompt.start", content_lang=rs.content_lang))

    source_index = read_json(args.source_index or ws / "source-index.json")
    try:
        schema_index = read_json(args.schema_index or ws / "schema-index.json")
    except FileNotFoundError:
        schema_index = None
    candidates = read_json(args.area_candidates or ws / "area-candidates.json")

    try:
        prompt = render_prompt(
            "area_tree", rs.content_lang,
            system_summary=rs.config.project_name or source_index.get("repo_root", ""),
            source_index_summary=_summarize_source(source_index),
            schema_index_summary=_summarize_schema(schema_index),
            area_candidates_summary=_summarize_candidates(candidates),
        )
    except FileNotFoundError as exc:
        print(rs.ui.t("prompt.missing_template", path=str(exc)))
        return 2

    from pathlib import Path
    out_path = Path(args.out) if args.out else (ws / "prompts" / "area-tree.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(prompt, encoding="utf-8")
    print(rs.ui.t("common.wrote", path=str(out_path)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

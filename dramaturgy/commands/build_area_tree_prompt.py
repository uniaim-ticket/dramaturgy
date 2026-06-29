#!/usr/bin/env python3
"""build_area_tree_prompt — generate the area-tree prompt for Claude.

Feeds Claude the reliable file/directory inventory and instructs it to read
the actual source to discover the business areas, concepts, and entities.
Writes ``.dramaturgy/prompts/area-tree.md``.

The prompt is in ``content_lang`` and asks Claude to write the generated
fields in that language and to stamp ``content_lang`` into the output JSON.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..common.config import add_lang_args, resolve
from ..common.paths import read_json, workspace_dir
from ..common.prompts import render_prompt


def _summarize_inventory(idx: dict) -> str:
    s = idx.get("summary", {})
    lines = [
        f"- files: {s.get('files', 0)}, lines: {s.get('lines', 0)}",
        f"- by_ext: {json.dumps(s.get('by_ext', {}), ensure_ascii=False)}",
        "",
        "directories (top by line count):",
    ]
    for d in idx.get("directories", [])[:60]:
        lines.append(f"  - {d['dir']}: {d['files']} files / {d['lines']} lines")
    n = len(idx.get("directories", []))
    if n > 60:
        lines.append(f"  ... and {n - 60} more directories")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build area-tree prompt")
    add_lang_args(parser)
    parser.add_argument("--source-index", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)
    rs = resolve(args)
    ws = workspace_dir(rs.config.repo_root)

    print(rs.ui.t("prompt.start", content_lang=rs.content_lang))

    source_index = read_json(args.source_index or ws / "source-index.json")

    try:
        prompt = render_prompt(
            "area_tree", rs.content_lang,
            system_summary=rs.config.project_name or source_index.get("repo_root", ""),
            repo_root=source_index.get("repo_root", "."),
            inventory_summary=_summarize_inventory(source_index),
        )
    except FileNotFoundError as exc:
        print(rs.ui.t("prompt.missing_template", path=str(exc)))
        return 2

    out_path = Path(args.out) if args.out else (ws / "prompts" / "area-tree.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(prompt, encoding="utf-8")
    print(rs.ui.t("common.wrote", path=str(out_path)))
    return 0

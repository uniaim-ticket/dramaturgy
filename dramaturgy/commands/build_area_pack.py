#!/usr/bin/env python3
"""build_area_pack — assemble the file list for one area, for Claude to read.

Requires an existing ``area-tree.json``. For the requested ``--area-id`` it
collects the files whose paths match the area's hints, so Claude knows which
files to open. It does NOT pre-extract tables/APIs/entities — Claude reads
the listed files to discover those. Warns (never auto-splits) when the listed
files are large enough that the area may be worth subdividing.

    dra pack --area-id ticket_sales.application
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..common.area_match import estimate_tokens, find_area, match_files
from ..common.config import add_lang_args, resolve
from ..common.paths import read_json, workspace_dir

# A rough size guard: if the matched files are this large (in estimated
# tokens), suggest the area may need subdividing. Reading is Claude's call.
DEFAULT_TOKEN_LIMIT = 100_000


def build_pack(area: dict, source_index: dict) -> dict:
    files = match_files(area, source_index)
    total_lines = sum(f.get("lines") or 0 for f in files)
    return {
        "area": {
            "id": area.get("id"),
            "name": area.get("name"),
            "one_liner": area.get("one_liner"),
            "purpose": area.get("purpose"),
            "primary_actors": area.get("primary_actors", []),
            "primary_concepts": area.get("primary_concepts", []),
            "source_hints": area.get("source_hints", {}),
        },
        "instructions": (
            "Open and read the files listed below to discover the area's "
            "tables/entities, APIs, screens, flows, and state transitions. "
            "Do not rely on file paths alone; the definitions may live in "
            "ORM models, migrations, or framework conventions."
        ),
        "files": files,
        "counts": {"files": len(files), "lines": total_lines},
    }


def render_markdown(pack: dict) -> str:
    return "# Area pack: {id}\n\n```json\n{body}\n```\n".format(
        id=pack["area"]["id"],
        body=json.dumps(pack, ensure_ascii=False, indent=2),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build an area file pack")
    add_lang_args(parser)
    parser.add_argument("--area-id", required=True)
    parser.add_argument("--area-tree", default=None)
    parser.add_argument("--source-index", default=None)
    parser.add_argument("--out", default=None)
    parser.add_argument("--token-limit", type=int, default=DEFAULT_TOKEN_LIMIT)
    args = parser.parse_args(argv)
    rs = resolve(args)
    ws = workspace_dir(rs.config.repo_root)

    print(rs.ui.t("pack.start", area_id=args.area_id))

    area_tree = read_json(args.area_tree or ws / "area-tree.json")
    area = find_area(area_tree, args.area_id)
    if area is None:
        print(rs.ui.t("pack.area_not_found", area_id=args.area_id))
        return 1

    source_index = read_json(args.source_index or ws / "source-index.json")
    pack = build_pack(area, source_index)
    tokens = estimate_tokens(pack)
    print(rs.ui.t("pack.estimate", tokens=tokens))
    if tokens > args.token_limit:
        # Warn only — splitting is Claude's judgment (see rfp.md).
        print(rs.ui.t("pack.too_large", tokens=tokens, limit=args.token_limit))

    out_path = Path(args.out) if args.out else (
        ws / "area-packs" / f"{args.area_id}.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_markdown(pack), encoding="utf-8")
    print(rs.ui.t("common.wrote", path=str(out_path)))
    return 0

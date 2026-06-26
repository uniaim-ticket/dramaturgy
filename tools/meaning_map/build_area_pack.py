#!/usr/bin/env python3
"""build_area_pack.py — assemble the analysis pack for one area.

Requires an existing ``area-tree.json``. For the requested ``--area-id``,
gathers the related files, tables, and APIs (via the area's source_hints),
estimates token size, and warns — but never automatically splits — when the
pack exceeds the limit. Output is a Markdown pack written for Claude.

    python tools/meaning_map/build_area_pack.py \
      --area-id ticket_sales.application \
      --area-tree .meaning-map/area-tree.json \
      --source-index .meaning-map/source-index.json \
      --schema-index .meaning-map/schema-index.json \
      --out .meaning-map/area-packs/ticket_sales.application.md
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from common.bootstrap import setup_path

setup_path()

from common.area_match import (  # noqa: E402
    estimate_tokens, find_area, match_apis, match_files, match_tables,
)
from common.config import add_lang_args, resolve  # noqa: E402
from common.paths import read_json, workspace_dir  # noqa: E402

DEFAULT_TOKEN_LIMIT = 100_000


def build_pack(area: dict, source_index: dict, schema_index: dict | None) -> dict:
    files = match_files(area, source_index)
    tables = match_tables(area, schema_index)
    apis = match_apis(area, source_index)
    return {
        "area": {
            "id": area.get("id"),
            "name": area.get("name"),
            "one_liner": area.get("one_liner"),
            "purpose": area.get("purpose"),
            "primary_actors": area.get("primary_actors", []),
            "primary_concepts": area.get("primary_concepts", []),
        },
        "files": files,
        "tables": tables,
        "apis": apis,
        "counts": {
            "files": len(files),
            "tables": len(tables),
            "apis": len(apis),
        },
    }


def render_markdown(pack: dict) -> str:
    return "# Area pack: {id}\n\n```json\n{body}\n```\n".format(
        id=pack["area"]["id"],
        body=json.dumps(pack, ensure_ascii=False, indent=2),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build an area analysis pack")
    add_lang_args(parser)
    parser.add_argument("--area-id", required=True)
    parser.add_argument("--area-tree", default=None)
    parser.add_argument("--source-index", default=None)
    parser.add_argument("--schema-index", default=None)
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
    try:
        schema_index = read_json(args.schema_index or ws / "schema-index.json")
    except FileNotFoundError:
        schema_index = None

    pack = build_pack(area, source_index, schema_index)
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


if __name__ == "__main__":
    raise SystemExit(main())

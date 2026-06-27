#!/usr/bin/env python3
"""suggest_subdivision — propose natural sub-areas for a large area.

Supporting material for Claude's judgment, NOT an automatic split (see
rfp.md). It clusters the area's matched files by directory and reports size
estimates, so Claude can decide whether a split is natural. Concept/table
grouping is left to Claude reading the files — not inferred here.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import PurePosixPath

from ..common.area_match import estimate_tokens, find_area, match_files
from ..common.config import add_lang_args, resolve
from ..common.paths import read_json, write_json, workspace_dir


def _cluster_files_by_dir(files: list[dict]) -> list[dict]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for f in files:
        parts = PurePosixPath(f["path"]).parts
        key = "/".join(parts[:3]) if len(parts) >= 3 else "/".join(parts[:-1]) or "."
        buckets[key].append(f)
    clusters = []
    for key, group in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
        clusters.append({
            "dir": key,
            "file_count": len(group),
            "lines": sum(f.get("lines") or 0 for f in group),
            "sample_files": [f["path"] for f in group[:8]],
        })
    return clusters


def suggest(area: dict, source_index: dict) -> dict:
    files = match_files(area, source_index)
    file_clusters = _cluster_files_by_dir(files)

    candidates = []
    for fc in file_clusters:
        candidates.append({
            "suggested_id": f"{area['id']}.{PurePosixPath(fc['dir']).name or 'core'}",
            "basis": "directory",
            "why_natural": "Files cluster under a distinct directory; often a "
                           "separate responsibility. Confirm by reading them.",
            "related_files": fc["sample_files"],
            "file_count": fc["file_count"],
            "lines": fc["lines"],
        })

    do_not_split = []
    if len(file_clusters) <= 1:
        do_not_split.append(
            "Files form a single cohesive directory cluster; splitting would "
            "likely harm comprehension. Keep as one area unless reading the "
            "code reveals a clear business reason.")

    return {
        "note": "Supporting material only. Claude decides whether to split, "
                "based on reading the files.",
        "area_id": area["id"],
        "estimated_tokens": estimate_tokens({"files": files}),
        "subdivision_candidates": candidates,
        "do_not_split_reasons": do_not_split,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Suggest sub-areas")
    add_lang_args(parser)
    parser.add_argument("--area-id", required=True)
    parser.add_argument("--area-tree", default=None)
    parser.add_argument("--source-index", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)
    rs = resolve(args)
    ws = workspace_dir(rs.config.repo_root)

    print(rs.ui.t("subdivision.start", area_id=args.area_id))
    area_tree = read_json(args.area_tree or ws / "area-tree.json")
    area = find_area(area_tree, args.area_id)
    if area is None:
        print(rs.ui.t("pack.area_not_found", area_id=args.area_id))
        return 1
    source_index = read_json(args.source_index or ws / "source-index.json")
    result = suggest(area, source_index)
    out = args.out or str(ws / "subdivisions" / f"{args.area_id}.json")
    write_json(out, result)
    print(rs.ui.t("common.wrote", path=out))
    return 0

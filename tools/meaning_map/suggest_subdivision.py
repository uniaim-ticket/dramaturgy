#!/usr/bin/env python3
"""suggest_subdivision.py — propose natural sub-areas for a large area.

This is supporting material for Claude's judgment, NOT an automatic split
(see rfp.md). For the requested area, it clusters the matched files by
directory and the matched tables by FK-connected components, and reports
size estimates plus reasons a split might be natural — and notes when a
split may not be warranted.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import PurePosixPath

from common.bootstrap import setup_path

setup_path()

from common.area_match import (  # noqa: E402
    estimate_tokens, find_area, match_files, match_tables,
)
from common.config import add_lang_args, resolve  # noqa: E402
from common.paths import read_json, write_json, workspace_dir  # noqa: E402


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
            "lines": sum(f["lines"] for f in group),
            "sample_files": [f["path"] for f in group[:8]],
        })
    return clusters


def _table_components(tables: list[dict]) -> list[list[str]]:
    """Connected components over FK edges among the matched tables."""
    names = {t["name"] for t in tables}
    adj: dict[str, set] = {n: set() for n in names}
    for t in tables:
        for fk in t.get("foreign_keys", []):
            ref = fk.get("ref_table")
            if ref in names:
                adj[t["name"]].add(ref)
                adj[ref].add(t["name"])
    seen: set[str] = set()
    comps: list[list[str]] = []
    for n in names:
        if n in seen:
            continue
        stack, comp = [n], []
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            comp.append(cur)
            stack.extend(adj[cur] - seen)
        comps.append(sorted(comp))
    return sorted(comps, key=lambda c: -len(c))


def suggest(area: dict, source_index: dict, schema_index: dict | None) -> dict:
    files = match_files(area, source_index)
    tables = match_tables(area, schema_index)
    file_clusters = _cluster_files_by_dir(files)
    table_comps = _table_components(tables)

    candidates = []
    for fc in file_clusters:
        candidates.append({
            "suggested_id": f"{area['id']}.{PurePosixPath(fc['dir']).name or 'core'}",
            "basis": "directory",
            "why_natural": "Files cluster under a distinct directory; often a "
                           "separate responsibility.",
            "related_files": fc["sample_files"],
            "file_count": fc["file_count"],
            "lines": fc["lines"],
        })
    for comp in table_comps:
        if len(comp) >= 2:
            candidates.append({
                "suggested_id": f"{area['id']}.{comp[0]}",
                "basis": "table_component",
                "why_natural": "Tables form a connected FK cluster; likely one "
                               "lifecycle/concept group.",
                "related_tables": comp,
            })

    do_not_split = []
    if len(file_clusters) <= 1 and len(table_comps) <= 1:
        do_not_split.append(
            "Material forms a single cohesive cluster; splitting would likely "
            "harm comprehension. Keep as one area unless Claude sees a clear "
            "business reason.")

    return {
        "note": "Supporting material only. Claude decides whether to split.",
        "area_id": area["id"],
        "estimated_tokens": estimate_tokens(
            {"files": files, "tables": tables}),
        "subdivision_candidates": candidates,
        "do_not_split_reasons": do_not_split,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Suggest sub-areas")
    add_lang_args(parser)
    parser.add_argument("--area-id", required=True)
    parser.add_argument("--area-tree", default=None)
    parser.add_argument("--source-index", default=None)
    parser.add_argument("--schema-index", default=None)
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
    try:
        schema_index = read_json(args.schema_index or ws / "schema-index.json")
    except FileNotFoundError:
        schema_index = None

    result = suggest(area, source_index, schema_index)
    out = args.out or str(ws / "subdivisions" / f"{args.area_id}.json")
    write_json(out, result)
    print(rs.ui.t("common.wrote", path=out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

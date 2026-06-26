#!/usr/bin/env python3
"""propose_area_candidates.py — assemble candidate material for Claude.

Combines source-index.json and schema-index.json into grouping material
that helps Claude form a natural area tree. This output is NOT a final
decision — it is supporting evidence only (see rfp.md).

Produces ``.meaning-map/area-candidates.json`` with:
- directory groupings (path depth-1/2 buckets with size)
- table relationship graph (FK edges)
- API-prefix groupings
- model reference hints
- screen/controller/route groupings
- status-column lifecycle candidates
- large candidate areas by file volume
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import PurePosixPath

from common.bootstrap import setup_path

setup_path()

from common.config import add_lang_args, resolve  # noqa: E402
from common.paths import read_json, write_json, workspace_dir  # noqa: E402


def _dir_groups(files: list[dict]) -> list[dict]:
    buckets: dict[str, dict] = defaultdict(lambda: {"files": 0, "lines": 0})
    for f in files:
        parts = PurePosixPath(f["path"]).parts
        key = "/".join(parts[:2]) if len(parts) > 1 else parts[0]
        buckets[key]["files"] += 1
        buckets[key]["lines"] += f["lines"]
    groups = [{"dir": k, **v} for k, v in buckets.items()]
    return sorted(groups, key=lambda g: -g["lines"])


def _api_prefix_groups(files: list[dict]) -> list[dict]:
    buckets: dict[str, set] = defaultdict(set)
    for f in files:
        for route in f.get("routes", []):
            seg = [s for s in route.split("/") if s and not s.startswith(("{", ":"))]
            prefix = "/" + "/".join(seg[:2]) if seg else route
            buckets[prefix].add(route)
    return sorted(
        ({"prefix": k, "routes": sorted(v)} for k, v in buckets.items()),
        key=lambda g: -len(g["routes"]),
    )


def _table_graph(tables: list[dict]) -> dict:
    edges = []
    names = {t["name"] for t in tables}
    for t in tables:
        for fk in t.get("foreign_keys", []):
            if fk.get("ref_table") in names:
                edges.append({"from": t["name"], "to": fk["ref_table"]})
    return {"nodes": sorted(names), "edges": edges}


def _lifecycle_candidates(tables: list[dict]) -> list[dict]:
    out = []
    for t in tables:
        if t.get("status_columns") or t.get("enum_columns"):
            out.append({
                "table": t["name"],
                "status_columns": t.get("status_columns", []),
                "enum_columns": t.get("enum_columns", []),
            })
    return out


def build_candidates(source_index: dict, schema_index: dict) -> dict:
    files = source_index.get("files", [])
    tables = schema_index.get("tables", []) if schema_index else []
    by_role = source_index.get("by_role", {})

    dir_groups = _dir_groups(files)
    return {
        "note": "Supporting material only. Claude makes the final area decisions.",
        "directory_groups": dir_groups,
        "api_prefix_groups": _api_prefix_groups(files),
        "table_graph": _table_graph(tables),
        "lifecycle_candidates": _lifecycle_candidates(tables),
        "role_groups": {
            role: by_role.get(role, [])
            for role in ("controller", "model", "view", "route", "job")
        },
        "large_candidate_areas": dir_groups[:10],
        "table_flags": {
            flag: [t["name"] for t in tables if flag in t.get("flags", [])]
            for flag in ("history", "junction", "master", "aggregate")
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Propose area candidates")
    add_lang_args(parser, content=False)
    parser.add_argument("--source-index", default=None)
    parser.add_argument("--schema-index", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)
    rs = resolve(args)
    repo_root = rs.config.repo_root
    ws = workspace_dir(repo_root)

    print(rs.ui.t("candidates.start"))
    source_index = read_json(args.source_index or ws / "source-index.json")
    schema_path = args.schema_index or ws / "schema-index.json"
    schema_index = None
    try:
        schema_index = read_json(schema_path)
    except FileNotFoundError:
        schema_index = {"tables": []}

    candidates = build_candidates(source_index, schema_index)
    out = args.out or str(ws / "area-candidates.json")
    write_json(out, candidates)
    print(rs.ui.t("candidates.done"))
    print(rs.ui.t("common.wrote", path=out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

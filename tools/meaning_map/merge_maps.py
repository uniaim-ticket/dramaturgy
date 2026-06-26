#!/usr/bin/env python3
"""merge_maps.py — merge per-area meaning maps into one meaning-map.json.

Takes several area-level map JSONs (each a partial meaning-map.json shape)
and merges areas/concepts/actors/flows. Detects duplicate IDs and concept
name drift, backfills related-area links, checks parent/child consistency,
and flags orphan areas. All inputs must share one ``content_lang`` (the
single-language model); a mismatch is a warning and the first value wins.
"""

from __future__ import annotations

import argparse
from collections import defaultdict

from common.bootstrap import setup_path

setup_path()

from common.config import add_lang_args, resolve  # noqa: E402
from common.paths import read_json, write_json, workspace_dir  # noqa: E402


def _merge_by_id(target: dict, items: list[dict], key: str, problems: list):
    for item in items:
        ident = item.get("id")
        if not ident:
            continue
        if ident in target:
            problems.append(("duplicate", key, ident))
            continue
        target[ident] = item


def merge(maps: list[dict], ui) -> tuple[dict, list]:
    problems: list = []

    langs = {m.get("content_lang") for m in maps if m.get("content_lang")}
    if len(langs) > 1:
        print(ui.t("merge.lang_mismatch", langs=sorted(langs)))
    content_lang = next(iter(langs)) if langs else None

    areas: dict[str, dict] = {}
    concepts: dict[str, dict] = {}
    actors: dict[str, dict] = {}
    flows: dict[str, dict] = {}
    system = {}

    for m in maps:
        system = system or m.get("system", {})
        _merge_by_id(areas, m.get("areas", []), "area", problems)
        _merge_by_id(concepts, m.get("concepts", []), "concept", problems)
        _merge_by_id(flows, m.get("flows", []), "flow", problems)
        # Actors may legitimately recur; merge their action lists.
        for a in m.get("actors", []):
            ident = a.get("id")
            if not ident:
                continue
            if ident in actors:
                actors[ident].setdefault("actions", []).extend(
                    a.get("actions", []))
            else:
                actors[ident] = a

    # Concept name drift: same normalized name, different ids.
    name_to_ids = defaultdict(set)
    for c in concepts.values():
        if c.get("name"):
            name_to_ids[c["name"].strip().lower()].add(c["id"])
    name_drift = {n: sorted(ids) for n, ids in name_to_ids.items() if len(ids) > 1}

    # Backfill related links symmetrically and check parent/child.
    for area in areas.values():
        for rel in area.get("related_area_ids", []):
            other = areas.get(rel)
            if other is not None:
                rl = other.setdefault("related_area_ids", [])
                if area["id"] not in rl:
                    rl.append(area["id"])
        parent_id = area.get("parent_area_id")
        if parent_id and parent_id in areas:
            kids = areas[parent_id].setdefault("child_area_ids", [])
            if area["id"] not in kids:
                problems.append(("parent_child", area["id"], parent_id))

    orphans = [a["id"] for a in areas.values()
               if not a.get("parent_area_id")
               and not a.get("child_area_ids")
               and len(areas) > 1]

    merged = {
        "content_lang": content_lang,
        "system": system,
        "actors": list(actors.values()),
        "areas": list(areas.values()),
        "concepts": list(concepts.values()),
        "flows": list(flows.values()),
        "validations": [],
        "merge_report": {
            "duplicate_ids": [p[1:] for p in problems if p[0] == "duplicate"],
            "concept_name_drift": name_drift,
            "parent_child_issues": [p[1:] for p in problems
                                    if p[0] == "parent_child"],
            "orphan_areas": orphans,
        },
    }
    return merged, problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Merge area meaning maps")
    add_lang_args(parser)
    parser.add_argument("inputs", nargs="+", help="area-map JSON files")
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)
    rs = resolve(args)
    ws = workspace_dir(rs.config.repo_root)

    print(rs.ui.t("merge.start"))
    maps = [read_json(p) for p in args.inputs]
    merged, _ = merge(maps, rs.ui)
    out = args.out or str(ws / "meaning-map.json")
    write_json(out, merged)
    print(rs.ui.t("merge.merged", count=len(merged["areas"])))
    print(rs.ui.t("common.wrote", path=out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

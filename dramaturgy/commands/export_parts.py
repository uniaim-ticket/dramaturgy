#!/usr/bin/env python3
"""export_parts — derive partial, self-contained views from meaning-map.json.

The canonical map (``meaning-map.json``) is a single file holding the whole
system. That is ideal for "read everything" but forces a reader who only cares
about one area to parse the entire file. These derivatives let an external
agent (e.g. a separate Claude Code session doing a code change) read *only*
what it needs:

* ``map-index.json`` — a small manifest: the system purpose, the area tree
  (id / name / one_liner / parent / children), the concept and actor name
  lists, and a byte-size hint per part. A few KB; enough to grasp the whole
  shape and decide which parts to open.
* ``parts/areas/<id>.json`` — one self-contained card per area, with the
  area's concepts/actors/classifications resolved and inlined (names + the
  data needed to act), so reading this one file is sufficient.
* ``parts/concepts/<id>.json`` — one card per concept, with the areas that use
  it (CRUD) and their names resolved.
* ``parts/README.md`` — explains the layout to whoever opens the directory.

All of this is **derived and read-only**: it is regenerated from the canonical
map on every render/merge, so it never drifts. Editing still happens on
``meaning-map.json`` only.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from ..common.config import add_lang_args, resolve
from ..common.i18n import Catalog
from ..common.paths import read_json, workspace_dir, write_json


def _nbytes(obj) -> int:
    return len(json.dumps(obj, ensure_ascii=False).encode("utf-8"))


def _area_part(area: dict, concept_map: dict, actor_map: dict,
               classifications: list) -> dict:
    """A self-contained view of one area: its own fields plus the resolved
    concepts/actors/classifications it touches, so the file stands alone."""
    cids = [e.get("concept_id") for e in area.get("concept_crud", []) or []]
    concepts = []
    for entry in area.get("concept_crud", []) or []:
        cid = entry.get("concept_id")
        c = concept_map.get(cid)
        concepts.append({
            "id": cid,
            "name": (c or {}).get("name", cid),
            "ops": entry.get("ops", ""),
            "physical_tables": (c or {}).get("physical_tables", []),
            "kind": (c or {}).get("kind"),
        })
    actors = []
    for a in area.get("actors", []) or []:
        aid = a.get("actor_id")
        ac = actor_map.get(aid) or {}
        actors.append({
            "id": aid, "name": ac.get("name", aid),
            "category": ac.get("category", "person"),
            "actions": a.get("actions", []),
        })
    # Classifications that detail one of this area's concepts.
    cls = [c for c in classifications
           if c.get("concept_id") in set(cids)]
    return {
        "kind": "area",
        "area": area,
        "resolved": {
            "concepts": concepts,
            "actors": actors,
            "classifications": cls,
        },
    }


def _concept_part(concept: dict, area_map: dict, classifications: list) -> dict:
    """A self-contained view of one concept: its fields plus the names of the
    areas that use it (CRUD) and any classifications detailing it."""
    areas = []
    for entry in concept.get("crud_by_area", []) or []:
        aid = entry.get("area_id")
        areas.append({
            "id": aid, "name": (area_map.get(aid) or {}).get("name", aid),
            "ops": entry.get("ops", ""),
        })
    cls = [c for c in classifications if c.get("concept_id") == concept.get("id")]
    return {"kind": "concept", "concept": concept,
            "resolved": {"areas": areas, "classifications": cls}}


def export_parts(mm: dict, out_dir: Path, cat: Catalog | None = None) -> dict:
    """Write map-index.json + parts/ under ``out_dir``. Returns the index."""
    areas = mm.get("areas", [])
    concepts = mm.get("concepts", [])
    actors = mm.get("actors", [])
    classifications = mm.get("classifications", [])
    components = mm.get("components", [])
    area_map = {a.get("id"): a for a in areas}
    concept_map = {c.get("id"): c for c in concepts}
    actor_map = {a.get("id"): a for a in actors}

    parts_dir = out_dir / "parts"
    # Regenerate cleanly so deleted entries don't linger as stale part files.
    if parts_dir.exists():
        shutil.rmtree(parts_dir)
    (parts_dir / "areas").mkdir(parents=True, exist_ok=True)
    (parts_dir / "concepts").mkdir(parents=True, exist_ok=True)

    area_entries = []
    for a in areas:
        part = _area_part(a, concept_map, actor_map, classifications)
        rel = f"parts/areas/{a.get('id')}.json"
        write_json(out_dir / rel, part)
        area_entries.append({
            "id": a.get("id"), "name": a.get("name"),
            "one_liner": a.get("one_liner"),
            "parent_area_id": a.get("parent_area_id"),
            "child_area_ids": a.get("child_area_ids", []),
            "concept_ids": [e.get("concept_id")
                            for e in a.get("concept_crud", []) or []],
            "part": rel, "bytes": _nbytes(part),
        })

    concept_entries = []
    for c in concepts:
        part = _concept_part(c, area_map, classifications)
        rel = f"parts/concepts/{c.get('id')}.json"
        write_json(out_dir / rel, part)
        # Keep the index entry small: name + kind + tags are enough to scan
        # and decide; physical_tables and the full CRUD live in the part file.
        concept_entries.append({
            "id": c.get("id"), "name": c.get("name"),
            "kind": c.get("kind"),
            "tags": c.get("tags", []),
            "part": rel, "bytes": _nbytes(part),
        })

    system = mm.get("system", {})
    index = {
        "content_lang": mm.get("content_lang"),
        "system": {
            "name": system.get("name"),
            "purpose": system.get("purpose"),
            "source": system.get("source"),
        },
        "counts": {
            "areas": len(areas), "concepts": len(concepts),
            "actors": len(actors), "classifications": len(classifications),
            "components": len(components),
        },
        "areas": area_entries,
        "concepts": concept_entries,
        "actors": [{"id": a.get("id"), "name": a.get("name"),
                    "category": a.get("category", "person")} for a in actors],
        "full_map": "meaning-map.json",
    }
    write_json(out_dir / "map-index.json", index)
    _write_readme(out_dir, cat)
    return index


_README = """\
# dramaturgy — meaning map (machine-readable)

This directory holds a compact "meaning map" of the system, generated by
dramaturgy. It is meant to be read by both humans (see `meaning-map.html`) and
agents working on the code.

## How to read it efficiently

- **Whole picture, cheaply:** start with `map-index.json` (a few KB). It has
  the system purpose, the area tree (id / name / one_liner / parent / children),
  and the lists of concepts and actors — with a `bytes` size hint and a `part`
  path for each entry.
- **A specific area or concept:** open just its part file, e.g.
  `parts/areas/<area-id>.json` or `parts/concepts/<concept-id>.json`. Each part
  is **self-contained**: the area part inlines the names + tables of the
  concepts it touches, its actors, and the classifications that detail them, so
  you do not need to open the full map to act on one area.
- **Everything at once:** read `meaning-map.json` (the canonical full map).

Suggested split for an agent doing a code change: read `map-index.json` to
locate the relevant area(s), then open only those `parts/areas/*.json`.

## Authority / freshness

`meaning-map.json` is the single source of truth. `map-index.json` and
everything under `parts/` are **derived, read-only** views, regenerated from it
on every render — do not edit them by hand (edits there will be overwritten).
"""


def _write_readme(out_dir: Path, cat: Catalog | None) -> None:
    (out_dir / "parts").mkdir(parents=True, exist_ok=True)
    (out_dir / "parts" / "README.md").write_text(_README, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Derive map-index.json + parts/ from meaning-map.json")
    add_lang_args(parser, content=False)
    parser.add_argument("--map", default=None)
    args = parser.parse_args(argv)
    rs = resolve(args)
    ws = workspace_dir(rs.config.repo_root)
    mm = read_json(args.map or ws / "meaning-map.json")
    cat = Catalog(rs.ui_lang, domain="cli")
    index = export_parts(mm, ws, cat)
    print(rs.ui.t("common.wrote", path=str(ws / "map-index.json")))
    print(f"  parts: {len(index['areas'])} areas, "
          f"{len(index['concepts'])} concepts")
    return 0

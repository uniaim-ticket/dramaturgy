"""Match indexed files/tables/APIs to an area via its ``source_hints``.

Used by build_area_pack and suggest_subdivision. Matching is intentionally
generous (substring / prefix on the hints provided by the area tree); the
goal is to gather candidate material for Claude, not to be authoritative.
"""

from __future__ import annotations

from typing import Any


def find_area(area_tree: dict, area_id: str) -> dict | None:
    for area in area_tree.get("areas", []):
        if area.get("id") == area_id:
            return area
    return None


def _hints(area: dict) -> dict[str, list[str]]:
    h = area.get("source_hints", {}) or {}
    return {
        "directories": [d.lower() for d in h.get("directories", [])],
        "tables": [t.lower() for t in h.get("tables", [])],
        "apis": [a.lower() for a in h.get("apis", [])],
        "screens": [s.lower() for s in h.get("screens", [])],
        "keywords": [k.lower() for k in h.get("keywords", [])],
    }


def match_files(area: dict, source_index: dict) -> list[dict]:
    hints = _hints(area)
    dirs = hints["directories"]
    keywords = hints["keywords"]
    out = []
    for f in source_index.get("files", []):
        path = f["path"].lower()
        if any(d and d in path for d in dirs) or \
           any(k and k in path for k in keywords):
            out.append(f)
    return out


def match_tables(area: dict, schema_index: dict | None) -> list[dict]:
    if not schema_index:
        return []
    hints = _hints(area)
    wanted = set(hints["tables"])
    keywords = hints["keywords"]
    out = []
    for t in schema_index.get("tables", []):
        name = t["name"].lower()
        if name in wanted or any(k and k in name for k in keywords):
            out.append(t)
    return out


def match_apis(area: dict, source_index: dict) -> list[str]:
    hints = _hints(area)
    prefixes = hints["apis"]
    found: set[str] = set()
    for f in source_index.get("files", []):
        for route in f.get("routes", []):
            rl = route.lower()
            if any(p and rl.startswith(p) for p in prefixes) or \
               any(p and p in rl for p in prefixes):
                found.add(route)
    return sorted(found)


def estimate_tokens(payload: Any) -> int:
    """Rough token estimate (~4 chars/token) for a JSON-serializable pack."""
    import json
    text = json.dumps(payload, ensure_ascii=False)
    return len(text) // 4

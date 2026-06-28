"""Match indexed files to an area via its ``source_hints``.

Used by build_area_pack and suggest_subdivision to gather the *files* that
likely belong to an area, so Claude knows which to open. Matching is on file
paths only (directories + keywords); it is intentionally generous and not
authoritative. Tables / APIs / entities are NOT matched here — those are
semantic facts Claude discovers by reading the files themselves.
"""

from __future__ import annotations

from typing import Any


def find_area(area_tree: dict, area_id: str) -> dict | None:
    for area in area_tree.get("areas", []):
        if area.get("id") == area_id:
            return area
    return None


def _strs(value) -> list[str]:
    """Coerce a hint value to a list of lowercase strings, tolerating a bare
    string or non-string elements."""
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return []
    return [str(v).lower() for v in value if v]


def _hints(area: dict) -> dict[str, list[str]]:
    # source_hints is meant to be a dict, but Claude sometimes emits a bare
    # list (treated as keywords) or omits it — tolerate all shapes.
    h = area.get("source_hints") or {}
    if isinstance(h, (list, tuple, str)):
        return {"directories": [], "keywords": _strs(h)}
    if not isinstance(h, dict):
        return {"directories": [], "keywords": []}
    return {
        "directories": _strs(h.get("directories")),
        "keywords": _strs(h.get("keywords")),
    }


def match_files(area: dict, source_index: dict) -> list[dict]:
    """Files whose path matches the area's directory or keyword hints."""
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


def estimate_tokens(payload: Any) -> int:
    """Rough token estimate (~4 chars/token) for a JSON-serializable pack."""
    import json
    text = json.dumps(payload, ensure_ascii=False)
    return len(text) // 4

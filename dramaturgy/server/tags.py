"""System-specific tag vocabulary for concept data.

Different systems care about different distinctions — e.g. master vs.
transaction data, or PII vs. non-PII. Rather than bake any taxonomy into the
tool, concepts carry a free-form ``tags: []`` list, and each project keeps its
own vocabulary in ``.dramaturgy/tags.json``:

    {
      "groups": [
        {"name": "データ区分", "description": "マスタ/トランザクションの別"}
      ],
      "tags": [
        {"name": "master", "description": "マスタデータ", "group": "データ区分"},
        {"name": "transaction", "description": "トランザクション", "group": "データ区分"}
      ]
    }

Each tag has a meaning (``description``) and may belong to a ``group``; groups
are defined in ``groups`` with their own description. The vocabulary is
advisory: it drives suggestions in the UI and is offered to Claude during card
generation, but any tag string is allowed on a concept.
"""

from __future__ import annotations

from pathlib import Path

from ..common.paths import read_json, workspace_dir, write_json

TAGS_FILE = "tags.json"


def _path(repo_root: str | Path) -> Path:
    return workspace_dir(repo_root) / TAGS_FILE


def load_vocab(repo_root: str | Path) -> dict:
    try:
        data = read_json(_path(repo_root))
    except FileNotFoundError:
        data = {}
    data.setdefault("tags", [])
    data.setdefault("groups", [])
    return data


def save_vocab(repo_root: str | Path, data: dict) -> dict:
    # Groups: {name, description}, deduped by name.
    seen_g: set[str] = set()
    groups = []
    for g in data.get("groups", []) or []:
        if isinstance(g, str):
            g = {"name": g, "description": ""}
        name = (g.get("name") or "").strip()
        if not name or name in seen_g:
            continue
        seen_g.add(name)
        groups.append({"name": name, "description": (g.get("description") or "").strip()})

    # Tags: {name, description, group}, deduped by name (keep first).
    seen: set[str] = set()
    norm = []
    for entry in data.get("tags", []) or []:
        if isinstance(entry, str):
            entry = {"name": entry, "description": ""}
        name = (entry.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        group = (entry.get("group") or "").strip()
        norm.append({
            "name": name,
            "description": (entry.get("description") or "").strip(),
            "group": group,
        })
    out = {"groups": groups, "tags": norm}
    write_json(_path(repo_root), out)
    return out


def vocab_names(repo_root: str | Path) -> list[str]:
    return [t["name"] for t in load_vocab(repo_root)["tags"]]


def group_of(repo_root: str | Path) -> dict[str, str]:
    """Map tag name -> group name (empty string when ungrouped)."""
    return {t["name"]: t.get("group", "")
            for t in load_vocab(repo_root)["tags"]}

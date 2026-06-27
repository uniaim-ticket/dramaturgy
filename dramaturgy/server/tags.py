"""System-specific tag vocabulary for concept data.

Different systems care about different distinctions — e.g. master vs.
transaction data, or PII vs. non-PII. Rather than bake any taxonomy into the
tool, concepts carry a free-form ``tags: []`` list, and each project keeps its
own vocabulary in ``.dramaturgy/tags.json``:

    {"tags": [{"name": "master", "description": "マスタデータ"},
              {"name": "transaction", "description": "トランザクション"}]}

The vocabulary is advisory: it drives suggestions in the UI and is offered to
Claude during card generation, but any tag string is allowed on a concept.
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
        return {"tags": []}
    data.setdefault("tags", [])
    return data


def save_vocab(repo_root: str | Path, data: dict) -> dict:
    # Normalize to {name, description}, drop blanks, dedupe by name (keep first).
    seen: set[str] = set()
    norm = []
    for entry in data.get("tags", []) or []:
        if isinstance(entry, str):
            entry = {"name": entry, "description": ""}
        name = (entry.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        norm.append({"name": name, "description": (entry.get("description") or "").strip()})
    out = {"tags": norm}
    write_json(_path(repo_root), out)
    return out


def vocab_names(repo_root: str | Path) -> list[str]:
    return [t["name"] for t in load_vocab(repo_root)["tags"]]

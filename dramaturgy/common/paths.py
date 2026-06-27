"""Canonical paths and JSON I/O helpers for the dramaturgy workspace.

All intermediate artifacts live under ``.dramaturgy/`` at the repo root.
JSON is always written pretty-printed and with ``ensure_ascii=False`` so
that Japanese (and other non-ASCII) content stays readable and diffs are
reviewable in Git.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

WORKSPACE_DIRNAME = ".dramaturgy"


def workspace_dir(repo_root: str | Path = ".") -> Path:
    return Path(repo_root) / WORKSPACE_DIRNAME


def config_path(repo_root: str | Path = ".") -> Path:
    return workspace_dir(repo_root) / "config.json"


def ensure_workspace(repo_root: str | Path = ".") -> Path:
    d = workspace_dir(repo_root)
    d.mkdir(parents=True, exist_ok=True)
    return d


def read_json(path: str | Path) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: str | Path, data: Any) -> None:
    """Write pretty-printed, UTF-8, newline-terminated JSON atomically.

    Writes to a temp file in the same directory then os.replace()s it into
    place, so a concurrent reader never sees a half-written file (the review
    auto-run worker and request threads both touch reviews.json).
    """
    import os
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, p)

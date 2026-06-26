"""Canonical paths and JSON I/O helpers for the meaning-map workspace.

All intermediate artifacts live under ``.meaning-map/`` at the repo root.
JSON is always written pretty-printed and with ``ensure_ascii=False`` so
that Japanese (and other non-ASCII) content stays readable and diffs are
reviewable in Git.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

WORKSPACE_DIRNAME = ".meaning-map"


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
    """Write pretty-printed, UTF-8, newline-terminated JSON.

    Sorted-by-insertion (not key) so authored ordering is preserved, but
    stable across runs for clean Git diffs.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

"""Interactive review store: per-item findings of three distinct kinds.

A *finding* is one human remark attached to a specific map item (an actor, a
concept, or an area). Findings come in three kinds, which differ in how they
are processed and where the result goes:

- ``reframe``  — accept the remark and re-organize the understanding:
  Claude EDITS the canonical meaning-map.json directly.
- ``audit``    — investigate without changing the canonical map: does this
  contradict the existing map, or is there a case it can't explain? Claude
  writes its findings back onto the finding (``audit_result``); the canonical
  map is left untouched.
- ``proposal`` — a desired FUTURE change to the system. Recorded separately
  under ``proposals/`` as a forward-looking note; the as-is map is not
  modified.

Findings live in ``.dramaturgy/reviews.json`` so they survive restarts and
are reviewable in Git. This module is pure storage + validation; running a
finding through Claude lives in the Api.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..common.paths import read_json, workspace_dir, write_json

TARGET_TYPES = ("actor", "concept", "area")
KINDS = ("reframe", "audit", "proposal")
STATUSES = ("open", "running", "done", "error", "dismissed")

REVIEWS_FILE = "reviews.json"


def _path(repo_root: str | Path) -> Path:
    return workspace_dir(repo_root) / REVIEWS_FILE


def load_reviews(repo_root: str | Path) -> dict:
    try:
        data = read_json(_path(repo_root))
    except FileNotFoundError:
        return {"next_id": 1, "findings": []}
    data.setdefault("next_id", 1)
    data.setdefault("findings", [])
    return data


def save_reviews(repo_root: str | Path, data: dict) -> None:
    write_json(_path(repo_root), data)


def validate_new(body: dict) -> str | None:
    """Return an error message, or None if the finding is well-formed."""
    if body.get("target_type") not in TARGET_TYPES:
        return f"target_type must be one of {TARGET_TYPES}"
    if not body.get("target_id"):
        return "target_id is required"
    if body.get("kind") not in KINDS:
        return f"kind must be one of {KINDS}"
    if not (body.get("comment") or "").strip():
        return "comment is required"
    return None


def create_finding(repo_root: str | Path, body: dict) -> dict:
    data = load_reviews(repo_root)
    fid = f"f-{data['next_id']}"
    data["next_id"] += 1
    finding = {
        "id": fid,
        "target_type": body["target_type"],
        "target_id": body["target_id"],
        "target_name": body.get("target_name", ""),
        "kind": body["kind"],
        "comment": body["comment"].strip(),
        "status": "open",
        "session_id": None,       # Claude session this finding last used
        "result": "",            # short human summary of the run
        "audit_result": None,     # structured result for kind == audit
        "proposal_ref": None,     # file path for kind == proposal
    }
    data["findings"].append(finding)
    save_reviews(repo_root, data)
    return finding


def get_finding(repo_root: str | Path, fid: str) -> dict | None:
    for f in load_reviews(repo_root)["findings"]:
        if f["id"] == fid:
            return f
    return None


def update_finding(repo_root: str | Path, fid: str, patch: dict) -> dict | None:
    data = load_reviews(repo_root)
    for i, f in enumerate(data["findings"]):
        if f["id"] == fid:
            f.update(patch)
            data["findings"][i] = f
            save_reviews(repo_root, data)
            return f
    return None


def delete_finding(repo_root: str | Path, fid: str) -> bool:
    data = load_reviews(repo_root)
    before = len(data["findings"])
    data["findings"] = [f for f in data["findings"] if f["id"] != fid]
    if len(data["findings"]) == before:
        return False
    save_reviews(repo_root, data)
    return True

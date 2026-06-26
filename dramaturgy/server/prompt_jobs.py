"""Assemble the prompts handed to Claude Code for each job kind.

Reuses the existing language-specific templates (area_tree / area_card) and
the per-language summary helpers, then appends a write-back footer telling
Claude exactly which JSON file to write. This keeps the *content* prompts
identical to the CLI path while adding the "you are Claude Code, write to
this file" instruction the headless flow needs.
"""

from __future__ import annotations

from pathlib import Path

from ..common.paths import read_json, workspace_dir
from ..common.prompts import load_prompt, render_prompt
from ..commands.build_area_tree_prompt import (
    _summarize_candidates, _summarize_schema, _summarize_source,
)
from ..commands.build_area_pack import build_pack
from ..common.area_match import find_area


def _load_optional(path: Path):
    try:
        return read_json(path)
    except FileNotFoundError:
        return None


def area_tree_prompt(repo_root: str, content_lang: str, project_name: str) -> str:
    ws = workspace_dir(repo_root)
    source_index = read_json(ws / "source-index.json")
    schema_index = _load_optional(ws / "schema-index.json")
    candidates = read_json(ws / "area-candidates.json")

    body = render_prompt(
        "area_tree", content_lang,
        system_summary=project_name or source_index.get("repo_root", ""),
        source_index_summary=_summarize_source(source_index),
        schema_index_summary=_summarize_schema(schema_index),
        area_candidates_summary=_summarize_candidates(candidates),
    )
    footer = render_prompt(
        "writeback_area_tree", content_lang,
        area_tree_path=str(ws / "area-tree.json"),
        lang=content_lang,
    )
    return body + footer


def area_card_prompt(repo_root: str, content_lang: str, area_id: str) -> str:
    ws = workspace_dir(repo_root)
    area_tree = read_json(ws / "area-tree.json")
    area = find_area(area_tree, area_id)
    if area is None:
        raise KeyError(area_id)
    source_index = read_json(ws / "source-index.json")
    schema_index = _load_optional(ws / "schema-index.json")
    pack = build_pack(area, source_index, schema_index)

    import json as _json
    body = render_prompt(
        "area_card", content_lang,
        area_summary=_json.dumps(pack["area"], ensure_ascii=False, indent=2),
        area_pack=_json.dumps(pack, ensure_ascii=False, indent=2),
    )
    footer = render_prompt(
        "writeback_area_card", content_lang,
        area_map_path=str(ws / "area-maps" / f"{area_id}.json"),
        lang=content_lang,
    )
    return body + footer

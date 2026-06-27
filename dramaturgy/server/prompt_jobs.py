"""Assemble the prompts handed to Claude Code for each job kind.

Reuses the language-specific templates (area_tree / area_card) and appends a
write-back footer telling Claude which JSON file to write. The area-tree
prompt feeds only the reliable file/directory inventory; Claude reads the
actual source to discover tables/entities/APIs.
"""

from __future__ import annotations

import json

from ..common.area_match import find_area
from ..common.paths import read_json, workspace_dir
from ..common.prompts import render_prompt
from ..commands.build_area_tree_prompt import _summarize_inventory
from ..commands.build_area_pack import build_pack


def area_tree_prompt(repo_root: str, content_lang: str, project_name: str) -> str:
    ws = workspace_dir(repo_root)
    source_index = read_json(ws / "source-index.json")

    body = render_prompt(
        "area_tree", content_lang,
        system_summary=project_name or source_index.get("repo_root", ""),
        repo_root=source_index.get("repo_root", "."),
        inventory_summary=_summarize_inventory(source_index),
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
    pack = build_pack(area, source_index)

    body = render_prompt(
        "area_card", content_lang,
        area_summary=json.dumps(pack["area"], ensure_ascii=False, indent=2),
        area_pack=json.dumps(pack, ensure_ascii=False, indent=2),
    )
    footer = render_prompt(
        "writeback_area_card", content_lang,
        area_map_path=str(ws / "area-maps" / f"{area_id}.json"),
        lang=content_lang,
    )
    return body + footer

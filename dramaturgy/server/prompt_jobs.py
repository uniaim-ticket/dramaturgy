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


def _instructions_block(extra_instructions: str | None) -> str:
    """A clearly-labeled block of operator-provided guidance, appended to the
    generation prompts. Empty when there is no guidance."""
    text = (extra_instructions or "").strip()
    if not text:
        return ""
    return (
        "\n\n---\n\n## 追加指示 / Additional instructions (operator-provided)\n\n"
        "以下はこのリポジトリ固有の追加指示です。必ず従ってください。\n"
        "Follow these repository-specific instructions:\n\n"
        + text + "\n")


def area_tree_prompt(repo_root: str, content_lang: str, project_name: str,
                     extra_instructions: str | None = None) -> str:
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
    return body + _instructions_block(extra_instructions) + footer


def area_card_prompt(repo_root: str, content_lang: str, area_id: str,
                     extra_instructions: str | None = None) -> str:
    ws = workspace_dir(repo_root)
    area_tree = read_json(ws / "area-tree.json")
    area = find_area(area_tree, area_id)
    if area is None:
        raise KeyError(area_id)
    source_index = read_json(ws / "source-index.json")
    pack = build_pack(area, source_index)

    # System-specific tag vocabulary (optional) to guide concept tagging.
    from . import tags as _tags
    vocab = _tags.load_vocab(repo_root)["tags"]
    if vocab:
        vocab_text = "\n".join(
            f"- {v['name']}" + (f": {v['description']}" if v.get("description") else "")
            for v in vocab)
    else:
        vocab_text = "(none defined yet — infer system-specific tags such as "
        vocab_text += "master vs. transaction where useful)"

    body = render_prompt(
        "area_card", content_lang,
        area_summary=json.dumps(pack["area"], ensure_ascii=False, indent=2),
        area_pack=json.dumps(pack, ensure_ascii=False, indent=2),
        tag_vocabulary=vocab_text,
    )
    footer = render_prompt(
        "writeback_area_card", content_lang,
        area_map_path=str(ws / "area-maps" / f"{area_id}.json"),
        lang=content_lang,
    )
    return body + _instructions_block(extra_instructions) + footer


# kind -> (template name, extra output path key)
_REVIEW_TEMPLATES = {
    "reframe": "review_reframe",
    "audit": "review_audit",
    "proposal": "review_proposal",
}


def review_prompt(repo_root: str, content_lang: str, finding: dict) -> tuple[str, str | None]:
    """Build the prompt for one review finding.

    Returns ``(prompt, output_path)`` where output_path is the audit/proposal
    file the run will produce (None for reframe, which edits the canonical map
    in place).
    """
    ws = workspace_dir(repo_root)
    name = _REVIEW_TEMPLATES[finding["kind"]]
    map_path = str(ws / "meaning-map.json")
    # Scope the comment to a sub-element when the finding has a field, so
    # Claude knows exactly what is being commented on (e.g. the purpose, a
    # specific concept's CRUD, one actor action).
    field = finding.get("field") or ""
    target_id = finding["target_id"]
    target_name = finding.get("target_name", "")
    if field:
        target_id = f"{target_id} › {field}"
        flabel = finding.get("field_label") or field
        target_name = f"{target_name} › {flabel}" if target_name else flabel
    slots = {
        "target_type": finding["target_type"],
        "target_id": target_id,
        "target_name": target_name,
        "comment": finding["comment"],
        "map_path": map_path,
    }
    output_path: str | None = None
    if finding["kind"] == "audit":
        output_path = str(ws / "audits" / f"{finding['id']}.json")
        slots["audit_path"] = output_path
    elif finding["kind"] == "proposal":
        output_path = str(ws / "proposals" / f"{finding['id']}.md")
        slots["proposal_path"] = output_path
    return render_prompt(name, content_lang, **slots), output_path

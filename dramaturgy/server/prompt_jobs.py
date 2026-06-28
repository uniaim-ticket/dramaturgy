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


def subdivide_review_prompt(repo_root: str, content_lang: str,
                            extra_instructions: str | None = None) -> str:
    """Ask Claude to split only the areas that warrant child areas, updating
    area-tree.json. Feeds the current tree + per-area size hints."""
    from ..common.area_match import match_files

    ws = workspace_dir(repo_root)
    area_tree = read_json(ws / "area-tree.json")
    source_index = read_json(ws / "source-index.json")

    hints = []
    for area in area_tree.get("areas", []):
        files = match_files(area, source_index)
        lines = sum(f.get("lines") or 0 for f in files)
        hints.append(f"- {area.get('id')} ({area.get('name')}): "
                     f"{len(files)} files / {lines} lines")
    size_hints = "\n".join(hints) or "(no size data)"

    body = render_prompt(
        "subdivide_review", content_lang,
        area_tree=json.dumps(area_tree, ensure_ascii=False, indent=2),
        size_hints=size_hints,
    )
    footer = render_prompt(
        "writeback_area_tree", content_lang,
        area_tree_path=str(ws / "area-tree.json"),
        lang=content_lang,
    )
    return body + _instructions_block(extra_instructions) + footer


def system_purpose_prompt(repo_root: str, content_lang: str,
                          extra_instructions: str | None = None) -> str:
    """Final-touch prompt: ask Claude to write a concise (<=1000 char) overall
    purpose for the system into meaning-map.json's system.purpose. Feeds a
    compact summary of the merged map (areas / actors / core concepts)."""
    ws = workspace_dir(repo_root)
    mm = read_json(ws / "meaning-map.json")

    system = mm.get("system", {})
    lines = []
    name = system.get("name")
    if name:
        lines.append(f"System name: {name}")
    areas = mm.get("areas", [])
    if areas:
        lines.append("\nAreas:")
        for a in areas:
            one = a.get("one_liner") or a.get("purpose") or ""
            lines.append(f"- {a.get('name')} ({a.get('id')}): {one}")
    actors = mm.get("actors", [])
    if actors:
        lines.append("\nActors:")
        for a in actors:
            cat = a.get("category", "person")
            lines.append(f"- {a.get('name')} [{cat}]: {a.get('description', '')}")
    concepts = mm.get("concepts", [])
    if concepts:
        names = ", ".join(c.get("name", "") for c in concepts)
        lines.append(f"\nCore concepts: {names}")
    map_summary = "\n".join(lines) or "(empty map)"

    body = render_prompt(
        "system_purpose", content_lang,
        map_path=str(ws / "meaning-map.json"),
        map_summary=map_summary,
    )
    return body + _instructions_block(extra_instructions)


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
    # Tags carry a meaning (description) and may belong to a group.
    from . import tags as _tags
    vdata = _tags.load_vocab(repo_root)
    vtags = vdata["tags"]
    if vtags:
        lines = []
        for v in vtags:
            line = f"- {v['name']}"
            if v.get("group"):
                line += f" [group: {v['group']}]"
            if v.get("description"):
                line += f": {v['description']}"
            lines.append(line)
        vocab_text = "\n".join(lines)
        if vdata.get("groups"):
            gl = "\n".join(
                f"- {g['name']}" + (f": {g['description']}" if g.get("description") else "")
                for g in vdata["groups"])
            vocab_text = f"Groups:\n{gl}\n\nTags:\n{vocab_text}"
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

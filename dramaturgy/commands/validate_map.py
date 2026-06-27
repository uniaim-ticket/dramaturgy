#!/usr/bin/env python3
"""validate_map — machine-checkable consistency checks.

Checks only what can be verified mechanically and reliably:
- code_refs point to files that actually exist
- parent/child and related-area consistency; cycle freedom
- language invariants (supported codes, content_lang matches config,
  message catalogs have no missing/extra keys)

It does NOT check that referenced tables/APIs "exist", because those are
discovered by Claude reading the source (ORM/migration/framework), not from
a mechanical index — so there is no authoritative list to check against.

Exits non-zero when any error-level problem is found (warnings don't fail).
"""

from __future__ import annotations

import argparse
from pathlib import Path


from ..common import SUPPORTED_LANGS  # noqa: E402
from ..common.config import add_lang_args, resolve  # noqa: E402
from ..common.i18n import validate_catalogs  # noqa: E402
from ..common.paths import read_json, workspace_dir  # noqa: E402


class Report:
    def __init__(self, ui):
        self.ui = ui
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, key: str, **kw):
        self.errors.append(self.ui.t(key, **kw))

    def warn(self, key: str, **kw):
        self.warnings.append(self.ui.t(key, **kw))


def _detect_cycle(areas: dict[str, dict]) -> list[str] | None:
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {aid: WHITE for aid in areas}

    def dfs(node, stack):
        color[node] = GRAY
        stack.append(node)
        for child in areas[node].get("child_area_ids", []):
            if child not in areas:
                continue
            if color[child] == GRAY:
                return stack[stack.index(child):] + [child]
            if color[child] == WHITE:
                res = dfs(child, stack)
                if res:
                    return res
        color[node] = BLACK
        stack.pop()
        return None

    for aid in areas:
        if color[aid] == WHITE:
            res = dfs(aid, [])
            if res:
                return res
    return None


def validate(mm: dict, source_index: dict, config, repo_root: str,
             report: Report) -> None:
    areas = {a["id"]: a for a in mm.get("areas", [])}
    concepts = {c["id"] for c in mm.get("concepts", [])}
    code_paths = {f["path"] for f in source_index.get("files", [])}
    root = Path(repo_root)

    # --- language invariants ---
    map_lang = mm.get("content_lang")
    if not map_lang:
        report.error("validate.missing_content_lang", file="meaning-map.json")
    else:
        if map_lang not in SUPPORTED_LANGS:
            report.error("validate.bad_lang", field="content_lang", lang=map_lang)
        if config and map_lang != config.content_lang:
            report.warn("validate.lang_config_mismatch",
                        map=map_lang, config=config.content_lang)
    if config:
        for fld, lang in (("ui_lang", config.ui_lang),
                          ("content_lang", config.content_lang)):
            if lang not in SUPPORTED_LANGS:
                report.error("validate.bad_lang", field=fld, lang=lang)

    for domain in ("cli", "html"):
        for problem in validate_catalogs(domain):
            report.error("validate.catalog_problem", detail=problem)

    # --- referential integrity (only reliably-checkable refs) ---
    for area in areas.values():
        for ref in area.get("code_refs", []):
            # code_refs may be "path" or "path:line"
            p = ref.split(":", 1)[0]
            if code_paths and p not in code_paths and not (root / p).exists():
                report.error("validate.missing_file", ref=ref)
        for rel in area.get("related_area_ids", []):
            if rel not in areas:
                report.error("validate.unknown_related", id=rel)
        parent = area.get("parent_area_id")
        if parent:
            if parent not in areas:
                report.error("validate.parent_child_mismatch",
                             detail=f"{area['id']} -> missing parent {parent}")
            elif area["id"] not in areas[parent].get("child_area_ids", []):
                report.error("validate.parent_child_mismatch",
                             detail=f"{parent} missing child {area['id']}")
        for child in area.get("child_area_ids", []):
            if child not in areas:
                report.error("validate.parent_child_mismatch",
                             detail=f"{area['id']} -> missing child {child}")

    # CRUD targets that look like concept ids must exist in concepts.
    # (Plain business names are allowed; only id-shaped keys are checked.)
    concept_names = {c.get("name") for c in mm.get("concepts", [])}
    for area in areas.values():
        for target in (area.get("crud_summary") or {}):
            looks_like_id = target.startswith("concept") or "." in target
            if looks_like_id and concepts and target not in concepts \
                    and target not in concept_names:
                report.error("validate.unknown_concept", name=target)

    cycle = _detect_cycle(areas)
    if cycle:
        report.error("validate.cycle", detail=" -> ".join(cycle))

    # Surface low-confidence items as a (non-failing) note.
    low = [a["id"] for a in areas.values() if a.get("confidence") == "low"]
    low += [c["id"] for c in mm.get("concepts", []) if c.get("confidence") == "low"]
    if low:
        report.warn("validate.low_confidence", count=len(low))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate meaning map")
    add_lang_args(parser)
    parser.add_argument("--map", default=None)
    parser.add_argument("--source-index", default=None)
    args = parser.parse_args(argv)
    rs = resolve(args)
    ws = workspace_dir(rs.config.repo_root)

    print(rs.ui.t("validate.start"))
    mm = read_json(args.map or ws / "meaning-map.json")
    try:
        source_index = read_json(args.source_index or ws / "source-index.json")
    except FileNotFoundError:
        source_index = {"files": []}

    report = Report(rs.ui)
    validate(mm, source_index, rs.config, rs.config.repo_root, report)

    for w in report.warnings:
        print("WARN: " + w)
    for e in report.errors:
        print("ERROR: " + e)

    if report.errors:
        print(rs.ui.t("validate.failed",
                      errors=len(report.errors), warnings=len(report.warnings)))
        return 1
    print(rs.ui.t("validate.ok",
                  errors=0, warnings=len(report.warnings)))
    return 0

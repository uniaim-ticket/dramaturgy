#!/usr/bin/env python3
"""analyze_repo.py — build a source-code index.

Walks the repository and produces ``.meaning-map/source-index.json`` with
per-file metadata plus heuristic candidates (routes, controllers, models,
migrations, views, jobs, table-name strings). The heuristics are
language-agnostic regexes; Claude does the meaning judgment downstream, so
false positives here are acceptable.

This tool emits only progress in the UI language; its output JSON is
data and contains no localized prose.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from common.bootstrap import setup_path

setup_path()

from common.config import add_lang_args, resolve  # noqa: E402
from common.paths import write_json, workspace_dir  # noqa: E402

# Directories that never carry domain meaning.
SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "vendor", "dist", "build",
    "__pycache__", ".meaning-map", ".venv", "venv", ".idea", ".vscode",
    "target", ".next", ".cache", "coverage", ".pytest_cache",
}
CODE_EXTS = {
    ".py", ".rb", ".php", ".js", ".jsx", ".ts", ".tsx", ".go", ".java",
    ".kt", ".cs", ".scala", ".rs", ".ex", ".exs", ".vue", ".sql",
}

IMPORT_RE = re.compile(
    r"^\s*(?:import|from|require|use|include|using)\b.*", re.MULTILINE)
CLASS_RE = re.compile(r"^\s*(?:class|interface|trait|struct)\s+([A-Za-z_]\w*)",
                      re.MULTILINE)
FUNC_RE = re.compile(
    r"^\s*(?:def|func|function|fn|public|private|protected|static)?\s*"
    r"(?:function\s+)?([A-Za-z_]\w*)\s*\(", re.MULTILINE)
ROUTE_RE = re.compile(
    r"""(?:get|post|put|patch|delete|route|Route|@app\.route|@router\.)\s*"""
    r"""[\(\.]?\s*['"`]([^'"`]+)['"`]""")
TABLE_RE = re.compile(
    r"""(?:create_table|table_name|@Table|from\s+|join\s+|into\s+)\s*"""
    r"""['"`]?([a-z][a-z0-9_]{2,})['"`]?""", re.IGNORECASE)


def _categorize(path: Path) -> list[str]:
    """Heuristic role tags from path segments and filename."""
    parts = [p.lower() for p in path.parts]
    name = path.stem.lower()
    tags: list[str] = []

    def has(*words):
        return any(w in p for p in parts for w in words)

    if has("controller") or name.endswith("controller"):
        tags.append("controller")
    if has("model", "models", "entity", "entities") or name.endswith("model"):
        tags.append("model")
    if has("migration", "migrations") or re.match(r"\d{6,}", name):
        tags.append("migration")
    if has("view", "views", "template", "templates", "page", "pages",
           "screen", "component", "components"):
        tags.append("view")
    if has("route", "routes", "router", "urls"):
        tags.append("route")
    if has("job", "jobs", "task", "tasks", "batch", "worker", "command",
           "commands", "cron"):
        tags.append("job")
    if path.suffix == ".sql":
        tags.append("sql")
    return tags


def analyze_file(path: Path, repo_root: Path) -> dict | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeError):
        return None
    rel = str(path.relative_to(repo_root))
    classes = CLASS_RE.findall(text)
    funcs = FUNC_RE.findall(text)
    # Drop common keyword false positives from the function regex.
    funcs = [f for f in funcs if f not in {
        "if", "for", "while", "switch", "catch", "return", "function"}]
    return {
        "path": rel,
        "ext": path.suffix,
        "lines": text.count("\n") + 1,
        "roles": _categorize(path),
        "imports": IMPORT_RE.findall(text)[:50],
        "classes": sorted(set(classes))[:50],
        "functions": sorted(set(funcs))[:80],
        "routes": sorted(set(ROUTE_RE.findall(text)))[:50],
        "table_hints": sorted(set(TABLE_RE.findall(text)))[:50],
    }


def analyze_repo(repo_root: str) -> dict:
    root = Path(repo_root).resolve()
    files: list[dict] = []
    total_lines = 0
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix not in CODE_EXTS:
            continue
        info = analyze_file(path, root)
        if info is None:
            continue
        files.append(info)
        total_lines += info["lines"]

    # Aggregate role buckets for quick downstream consumption.
    by_role: dict[str, list[str]] = {}
    for f in files:
        for role in f["roles"]:
            by_role.setdefault(role, []).append(f["path"])

    ext_counts: dict[str, int] = {}
    for f in files:
        ext_counts[f["ext"]] = ext_counts.get(f["ext"], 0) + 1

    return {
        "repo_root": str(root),
        "summary": {
            "files": len(files),
            "lines": total_lines,
            "by_ext": dict(sorted(ext_counts.items(),
                                  key=lambda kv: -kv[1])),
            "by_role": {k: len(v) for k, v in sorted(by_role.items())},
        },
        "by_role": by_role,
        "files": files,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Index repository source")
    add_lang_args(parser, content=False)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)
    rs = resolve(args)
    repo_root = rs.config.repo_root

    print(rs.ui.t("analyze_repo.start", root=repo_root))
    index = analyze_repo(repo_root)
    out = args.out or str(workspace_dir(repo_root) / "source-index.json")
    write_json(out, index)
    print(rs.ui.t("analyze_repo.counted",
                  files=index["summary"]["files"],
                  lines=index["summary"]["lines"]))
    print(rs.ui.t("common.wrote", path=out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

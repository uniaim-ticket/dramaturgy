#!/usr/bin/env python3
"""analyze_repo — collect a reliable file/directory inventory.

This step deliberately does NOT try to guess tables, routes, classes,
models, or "roles" from the source. Those are semantic facts that depend on
the framework/ORM/conventions in use and cannot be recovered reliably with
regexes — discovering them is Claude's job, reading the actual files (Claude
Code has repository access).

What we collect here is only what can be known mechanically and reliably:

* the list of files (path, extension, line count)
* per-directory and per-extension aggregates

This inventory orients Claude (where the code is, how big each area is) so it
can decide which files to open. It contains no inferred meaning.

Output: ``.dramaturgy/source-index.json``.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path, PurePosixPath

from ..common.config import add_lang_args, resolve
from ..common.paths import write_json, workspace_dir

# Directories that never carry domain meaning (skip wholesale).
SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "vendor", "dist", "build",
    "__pycache__", ".dramaturgy", ".venv", "venv", ".idea", ".vscode",
    "target", ".next", ".cache", "coverage", ".pytest_cache", ".mypy_cache",
    ".tox", ".gradle", "bin", "obj",
}
# Binary / non-source extensions to ignore when counting lines.
SKIP_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".pdf",
    ".zip", ".gz", ".tar", ".jar", ".class", ".o", ".so", ".dylib", ".dll",
    ".exe", ".bin", ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".mov",
    ".mp3", ".lock", ".map",
}
MAX_LINE_COUNT_BYTES = 2_000_000  # don't read huge files just to count lines


def _line_count(path: Path) -> int | None:
    try:
        if path.stat().st_size > MAX_LINE_COUNT_BYTES:
            return None
        with open(path, "rb") as fh:
            return fh.read().count(b"\n") + 1
    except OSError:
        return None


def analyze_repo(repo_root: str) -> dict:
    root = Path(repo_root).resolve()
    files: list[dict] = []
    total_lines = 0
    ext_counts: dict[str, int] = defaultdict(int)
    # Aggregate by top two directory levels so Claude can see where mass sits.
    dir_lines: dict[str, int] = defaultdict(int)
    dir_files: dict[str, int] = defaultdict(int)

    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if path.suffix.lower() in SKIP_EXTS:
            continue
        rel = str(path.relative_to(root))
        lines = _line_count(path)
        info = {"path": rel, "ext": path.suffix, "lines": lines}
        files.append(info)
        if lines:
            total_lines += lines
        ext_counts[path.suffix] += 1
        parts = PurePosixPath(rel).parts
        bucket = "/".join(parts[:2]) if len(parts) > 1 else "."
        dir_files[bucket] += 1
        if lines:
            dir_lines[bucket] += lines

    directories = sorted(
        ({"dir": d, "files": dir_files[d], "lines": dir_lines.get(d, 0)}
         for d in dir_files),
        key=lambda x: -x["lines"],
    )

    return {
        "repo_root": str(root),
        "summary": {
            "files": len(files),
            "lines": total_lines,
            "by_ext": dict(sorted(ext_counts.items(), key=lambda kv: -kv[1])),
        },
        "directories": directories,
        "files": files,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Index repository files (no semantic extraction)")
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

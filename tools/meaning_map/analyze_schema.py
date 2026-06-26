#!/usr/bin/env python3
"""analyze_schema.py — extract conceptual candidates from a DB schema.

Parses ``CREATE TABLE`` statements from one or more SQL/DDL files and emits
``.meaning-map/schema-index.json``: tables, columns, foreign keys, enum/
status-like columns, plus heuristic flags (history / junction / master /
aggregate table candidates).

Pure SQL-text parsing — no DB connection. Dialect-tolerant enough for
MySQL/PostgreSQL/SQLite DDL dumps. Claude does the conceptual compression
downstream.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from common.bootstrap import setup_path

setup_path()

from common.config import add_lang_args, resolve  # noqa: E402
from common.paths import write_json, workspace_dir  # noqa: E402

CREATE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"\[]?(\w+)[`\"\]]?\s*\((.*?)\)\s*"
    r"(?:ENGINE|;|$)",
    re.IGNORECASE | re.DOTALL,
)
COLUMN_RE = re.compile(r"^\s*[`\"\[]?(\w+)[`\"\]]?\s+([A-Za-z]+)", re.MULTILINE)
FK_RE = re.compile(
    r"(?:FOREIGN\s+KEY\s*\(\s*[`\"\[]?(\w+)[`\"\]]?\s*\)\s*)?REFERENCES\s+"
    r"[`\"\[]?(\w+)[`\"\]]?\s*\(\s*[`\"\[]?(\w+)[`\"\]]?\s*\)",
    re.IGNORECASE,
)
ENUM_RE = re.compile(r"^\s*[`\"\[]?(\w+)[`\"\]]?\s+(?:ENUM|SET)\s*\(", re.IGNORECASE | re.MULTILINE)
STATUS_NAME_RE = re.compile(r"(status|state|kind|type|phase|stage)$", re.IGNORECASE)

NON_COLUMN_TOKENS = {
    "primary", "foreign", "unique", "key", "index", "constraint", "check",
    "fulltext", "spatial",
}


def _parse_columns(body: str) -> list[dict]:
    cols: list[dict] = []
    seen: set[str] = set()
    for m in COLUMN_RE.finditer(body):
        name, dtype = m.group(1), m.group(2)
        low = name.lower()
        if low in NON_COLUMN_TOKENS or low in seen:
            continue
        seen.add(low)
        cols.append({"name": name, "type": dtype.upper()})
    return cols


def parse_schema(sql: str) -> list[dict]:
    tables: list[dict] = []
    for m in CREATE_RE.finditer(sql):
        name, body = m.group(1), m.group(2)
        cols = _parse_columns(body)
        col_names = {c["name"].lower() for c in cols}
        fks = [
            {"column": fk[0] or None, "ref_table": fk[1], "ref_column": fk[2]}
            for fk in FK_RE.findall(body)
        ]
        enum_cols = ENUM_RE.findall(body)
        status_cols = [c["name"] for c in cols if STATUS_NAME_RE.search(c["name"])]

        # Heuristic table-kind flags.
        nlow = name.lower()
        flags: list[str] = []
        if re.search(r"(history|histories|_log|_logs|audit|revision)", nlow):
            flags.append("history")
        # Junction: 2 FKs and few non-FK columns.
        if len(fks) >= 2 and len(cols) - len(fks) <= 3:
            flags.append("junction")
        if re.search(r"(master|_mst|^m_|_type$|category|categories|_kind)", nlow):
            flags.append("master")
        if re.search(r"(summary|aggregate|_agg|daily|monthly|stats|total)", nlow):
            flags.append("aggregate")

        tables.append({
            "name": name,
            "columns": cols,
            "foreign_keys": fks,
            "enum_columns": enum_cols,
            "status_columns": status_cols,
            "flags": flags,
            "column_count": len(cols),
        })
    return tables


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Index DB schema")
    add_lang_args(parser, content=False)
    parser.add_argument(
        "--schema", nargs="*", default=None,
        help="SQL/DDL file(s); if omitted, scans repo for *.sql",
    )
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)
    rs = resolve(args)
    repo_root = rs.config.repo_root

    print(rs.ui.t("analyze_schema.start"))

    if args.schema:
        sql_files = [Path(p) for p in args.schema]
    else:
        sql_files = [p for p in Path(repo_root).rglob("*.sql")
                     if ".meaning-map" not in p.parts]
    if not sql_files:
        print(rs.ui.t("analyze_schema.no_input"))
        return 1

    sql = "\n".join(
        p.read_text(encoding="utf-8", errors="replace") for p in sql_files
    )
    tables = parse_schema(sql)
    index = {
        "sources": [str(p) for p in sql_files],
        "summary": {"tables": len(tables)},
        "tables": tables,
    }
    out = args.out or str(workspace_dir(repo_root) / "schema-index.json")
    write_json(out, index)
    print(rs.ui.t("analyze_schema.counted", tables=len(tables)))
    print(rs.ui.t("common.wrote", path=out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

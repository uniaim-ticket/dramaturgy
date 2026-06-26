#!/usr/bin/env python3
"""render_html.py — render meaning-map.json into a single static HTML.

Language model (see rfp.md):
- Chrome (labels, nav, headings) comes from the HTML catalog for ``ui_lang``.
- Body content (area names, descriptions, concepts) is shown as-is in the
  map's ``content_lang``.
- ``<html lang>`` reflects the content language; a note shows both when they
  differ.

Produces a self-contained HTML file (no external assets) with the views
required by the RFP: overview, areas, actors, concepts, CRUD matrix,
developer reference, and validation.
"""

from __future__ import annotations

import argparse
import html
from pathlib import Path

from common.bootstrap import setup_path

setup_path()

from common.config import add_lang_args, resolve  # noqa: E402
from common.i18n import Catalog  # noqa: E402
from common.paths import read_json, workspace_dir  # noqa: E402

CSS = """
* { box-sizing: border-box; }
body { font-family: system-ui, -apple-system, "Hiragino Sans", "Noto Sans JP",
  sans-serif; margin: 0; color: #1c1f23; background: #f6f7f9; line-height: 1.6; }
header { background: #1c2733; color: #fff; padding: 16px 24px; }
header h1 { margin: 0; font-size: 20px; }
header .meta { font-size: 12px; opacity: .8; margin-top: 4px; }
nav { position: sticky; top: 0; background: #243140; padding: 8px 24px;
  display: flex; gap: 16px; flex-wrap: wrap; }
nav a { color: #cfe0f0; text-decoration: none; font-size: 13px; }
nav a:hover { color: #fff; }
main { max-width: 1100px; margin: 0 auto; padding: 24px; }
section { background: #fff; border: 1px solid #e2e6ea; border-radius: 8px;
  padding: 20px; margin-bottom: 24px; }
section > h2 { margin-top: 0; border-bottom: 2px solid #eef1f4; padding-bottom: 8px; }
.card { border: 1px solid #e2e6ea; border-radius: 6px; padding: 14px;
  margin-bottom: 14px; }
.card h3 { margin: 0 0 6px; }
.kv { display: grid; grid-template-columns: 160px 1fr; gap: 4px 12px;
  font-size: 14px; margin-top: 8px; }
.kv dt { color: #5a6573; font-weight: 600; }
.kv dd { margin: 0; }
.tag { display: inline-block; background: #eef1f4; border-radius: 4px;
  padding: 1px 8px; margin: 2px; font-size: 12px; }
.conf-high { color: #1a7f37; } .conf-medium { color: #9a6700; }
.conf-low { color: #cf222e; font-weight: 700; }
.low-note { background: #fff5f5; border-left: 3px solid #cf222e;
  padding: 6px 10px; font-size: 13px; margin-top: 8px; }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
th, td { border: 1px solid #e2e6ea; padding: 6px 8px; text-align: left; }
th { background: #f0f3f6; }
code { background: #f0f3f6; padding: 1px 4px; border-radius: 3px; font-size: 12px; }
.muted { color: #8b95a1; }
"""


def e(s) -> str:
    return html.escape(str(s)) if s is not None else ""


def tags(items) -> str:
    if not items:
        return '<span class="muted">—</span>'
    return "".join(f'<span class="tag">{e(i)}</span>' for i in items)


def conf_badge(cat: Catalog, level: str) -> str:
    if not level:
        return ""
    label = cat.t(f"confidence.{level}")
    return f'<span class="conf-{e(level)}">{e(label)}</span>'


def render_area(cat: Catalog, area: dict) -> str:
    rows = [
        (cat.t("label.one_liner"), e(area.get("one_liner"))),
        (cat.t("label.purpose"), e(area.get("purpose"))),
        (cat.t("label.parent"), e(area.get("parent_area_id")) or "—"),
        (cat.t("label.children"), tags(area.get("child_area_ids"))),
        (cat.t("label.related"), tags(area.get("related_area_ids"))),
        (cat.t("label.concepts"), tags(area.get("concepts"))),
        (cat.t("label.tables"), tags(area.get("tables"))),
        (cat.t("label.apis"), tags(area.get("apis"))),
        (cat.t("label.screens"), tags(area.get("screens"))),
        (cat.t("label.risk_points"), tags(area.get("risk_points"))),
        (cat.t("label.open_questions"), tags(area.get("open_questions"))),
        (cat.t("label.confidence"), conf_badge(cat, area.get("confidence"))),
    ]
    kv = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in rows)
    low = (f'<div class="low-note">{e(cat.t("note.low_confidence"))}</div>'
           if area.get("confidence") == "low" else "")
    return (f'<div class="card" id="area-{e(area.get("id"))}">'
            f'<h3>{e(area.get("name"))} '
            f'<span class="muted">({e(area.get("id"))})</span></h3>'
            f'<dl class="kv">{kv}</dl>{low}</div>')


def render_actors(cat: Catalog, actors: list) -> str:
    cards = []
    for a in actors:
        actions = "".join(
            f"<li>{e(act.get('action'))} "
            f"<span class='muted'>({e(act.get('area_id'))})</span> "
            f"— {e(act.get('description'))}</li>"
            for act in a.get("actions", []))
        cards.append(
            f'<div class="card"><h3>{e(a.get("name"))}</h3>'
            f'<p>{e(a.get("description"))}</p><ul>{actions}</ul></div>')
    return "".join(cards) or f'<p class="muted">{e(cat.t("empty.none"))}</p>'


def render_concepts(cat: Catalog, concepts: list) -> str:
    cards = []
    for c in concepts:
        rows = [
            ("kind", e(c.get("kind"))),
            (cat.t("label.tables"), tags(c.get("related_tables"))),
            (cat.t("label.states"), tags(c.get("states"))),
            (cat.t("label.confidence"), conf_badge(cat, c.get("confidence"))),
        ]
        kv = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in rows)
        cards.append(
            f'<div class="card" id="concept-{e(c.get("id"))}">'
            f'<h3>{e(c.get("name"))}</h3><p>{e(c.get("description"))}</p>'
            f'<dl class="kv">{kv}</dl></div>')
    return "".join(cards) or f'<p class="muted">{e(cat.t("empty.none"))}</p>'


def render_crud(cat: Catalog, areas: list) -> str:
    rows = []
    for area in areas:
        crud = area.get("crud_summary") or {}
        for concept, ops in crud.items():
            ops_str = ops if isinstance(ops, str) else ", ".join(ops)
            rows.append(f"<tr><td>{e(area.get('name'))}</td>"
                        f"<td>{e(concept)}</td><td>{e(ops_str)}</td></tr>")
    if not rows:
        return f'<p class="muted">{e(cat.t("empty.none"))}</p>'
    return (f"<table><tr><th>{e(cat.t('nav.areas'))}</th>"
            f"<th>{e(cat.t('label.concepts'))}</th>"
            f"<th>CRUD</th></tr>{''.join(rows)}</table>")


def render_dev(cat: Catalog, areas: list) -> str:
    rows = []
    for area in areas:
        refs = ", ".join(f"<code>{e(r)}</code>" for r in area.get("code_refs", []))
        rows.append(f"<tr><td>{e(area.get('name'))}</td>"
                    f"<td>{tags(area.get('tables'))}</td>"
                    f"<td>{tags(area.get('apis'))}</td>"
                    f"<td>{refs or '—'}</td></tr>")
    return (f"<table><tr><th>{e(cat.t('nav.areas'))}</th>"
            f"<th>{e(cat.t('label.tables'))}</th>"
            f"<th>{e(cat.t('label.apis'))}</th>"
            f"<th>{e(cat.t('label.code_refs'))}</th></tr>{''.join(rows)}</table>")


def render_validation(cat: Catalog, mm: dict) -> str:
    items = mm.get("validations", [])
    report = mm.get("merge_report", {})
    blocks = []
    if report:
        blocks.append(f"<pre><code>{e(__import__('json').dumps(report, ensure_ascii=False, indent=2))}</code></pre>")
    if items:
        blocks.append("<ul>" + "".join(f"<li>{e(v)}</li>" for v in items) + "</ul>")
    return "".join(blocks) or f'<p class="muted">{e(cat.t("empty.none"))}</p>'


def render_html(mm: dict, ui_lang: str) -> str:
    content_lang = mm.get("content_lang") or ui_lang
    cat = Catalog(ui_lang, domain="html")
    system = mm.get("system", {})
    src = system.get("source_summary", {})

    lang_note = ""
    if content_lang != ui_lang:
        lang_note = (f'<div class="meta">'
                     f'{e(cat.t("note.content_lang", content_lang=content_lang))}</div>')

    nav_items = [
        ("overview", "nav.overview"), ("areas", "nav.areas"),
        ("actors", "nav.actors"), ("concepts", "nav.concepts"),
        ("crud", "nav.crud"), ("dev", "nav.dev"),
        ("validation", "nav.validation"),
    ]
    nav = "".join(f'<a href="#{anchor}">{e(cat.t(key))}</a>'
                  for anchor, key in nav_items)

    areas = mm.get("areas", [])
    sections = [
        f'<section id="overview"><h2>{e(cat.t("nav.overview"))}</h2>'
        f'<h3>{e(system.get("name"))}</h3><p>{e(system.get("summary"))}</p>'
        f'<p class="muted">{e(cat.t("footer.source_summary", files=src.get("files",0), lines=src.get("lines",0), tables=src.get("tables",0)))}</p></section>',
        f'<section id="areas"><h2>{e(cat.t("nav.areas"))}</h2>'
        f'{"".join(render_area(cat, a) for a in areas)}</section>',
        f'<section id="actors"><h2>{e(cat.t("nav.actors"))}</h2>'
        f'{render_actors(cat, mm.get("actors", []))}</section>',
        f'<section id="concepts"><h2>{e(cat.t("nav.concepts"))}</h2>'
        f'{render_concepts(cat, mm.get("concepts", []))}</section>',
        f'<section id="crud"><h2>{e(cat.t("nav.crud"))}</h2>'
        f'{render_crud(cat, areas)}</section>',
        f'<section id="dev"><h2>{e(cat.t("nav.dev"))}</h2>'
        f'{render_dev(cat, areas)}</section>',
        f'<section id="validation"><h2>{e(cat.t("nav.validation"))}</h2>'
        f'{render_validation(cat, mm)}</section>',
    ]

    return f"""<!DOCTYPE html>
<html lang="{e(content_lang)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(cat.t("title"))} — {e(system.get("name"))}</title>
<style>{CSS}</style>
</head>
<body>
<header><h1>{e(cat.t("title"))} — {e(system.get("name"))}</h1>
<div class="meta">{e(cat.t("footer.generated_at", generated_at=system.get("generated_at","")))}</div>
{lang_note}</header>
<nav>{nav}</nav>
<main>{"".join(sections)}</main>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render meaning map to HTML")
    add_lang_args(parser)
    parser.add_argument("--map", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)
    rs = resolve(args)
    ws = workspace_dir(rs.config.repo_root)

    mm = read_json(args.map or ws / "meaning-map.json")
    content_lang = mm.get("content_lang") or rs.content_lang
    print(rs.ui.t("render.start", ui_lang=rs.ui_lang, content_lang=content_lang))

    out_path = Path(args.out) if args.out else (ws / "meaning-map.html")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_html(mm, rs.ui_lang), encoding="utf-8")
    print(rs.ui.t("render.done", path=str(out_path)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

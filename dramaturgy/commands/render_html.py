#!/usr/bin/env python3
"""render_html — render meaning-map.json into a single static HTML.

Language model (see rfp.md): chrome (labels/nav) comes from the ui_lang HTML
catalog; body content stays in the map's content_lang. ``<html lang>``
reflects the content language.

Views:
- Areas: a grid of clickable boxes; each expands (native <details>) to its
  detail card. No "overall map" section (it carried no real information).
- Concept data: each concept with the physical tables it abstracts and the
  areas that use it.
- CRUD: the same concept-centric data shown two ways — by area and by concept.
- Developer reference and validation.
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from ..common.config import add_lang_args, resolve
from ..common.i18n import Catalog
from ..common.paths import read_json, workspace_dir

CSS = """
* { box-sizing: border-box; }
body { font-family: system-ui, -apple-system, "Hiragino Sans", "Noto Sans JP",
  sans-serif; margin: 0; color: #1c1f23; background: #f6f7f9; line-height: 1.6; }
header { background: #1c2733; color: #fff; padding: 16px 24px; }
header h1 { margin: 0; font-size: 20px; }
header .meta { font-size: 12px; opacity: .8; margin-top: 4px; }
nav { position: sticky; top: 0; background: #243140; padding: 8px 24px;
  display: flex; gap: 16px; flex-wrap: wrap; z-index: 10; }
nav a { color: #cfe0f0; text-decoration: none; font-size: 13px; }
nav a:hover { color: #fff; }
main { max-width: 1100px; margin: 0 auto; padding: 24px; }
section { background: #fff; border: 1px solid #e2e6ea; border-radius: 8px;
  padding: 20px; margin-bottom: 24px; }
section > h2 { margin-top: 0; border-bottom: 2px solid #eef1f4; padding-bottom: 8px; }
/* Anchored items must clear the sticky nav when scrolled to. */
section, details.box, .box[id], [id^="actor-"] { scroll-margin-top: 52px; }

/* Area boxes: grid of clickable cards that expand in place. */
.box-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px; }
details.box { border: 1px solid #d4dae0; border-radius: 8px; background: #fbfcfd;
  overflow: hidden; }
details.box[open] { grid-column: 1 / -1; background: #fff; border-color: #9db4cc; }
details.box > summary { list-style: none; cursor: pointer; padding: 14px 16px;
  font-weight: 600; display: flex; align-items: baseline; justify-content: space-between; }
details.box > summary::-webkit-details-marker { display: none; }
details.box > summary:hover { background: #eef3f8; }
details.box .sum-name { font-size: 15px; }
details.box .sum-id { color: #8b95a1; font-size: 12px; font-weight: 400; }
details.box .body { padding: 0 16px 16px; border-top: 1px solid #eef1f4; }

.kv { display: grid; grid-template-columns: 160px 1fr; gap: 4px 12px;
  font-size: 14px; margin-top: 10px; }
.kv dt { color: #5a6573; font-weight: 600; }
.kv dd { margin: 0; }
.tag { display: inline-block; background: #eef1f4; border-radius: 4px;
  padding: 1px 8px; margin: 2px; font-size: 12px;
  max-width: 100%; overflow-wrap: anywhere; word-break: break-word;
  white-space: normal; vertical-align: top; }
/* Long unbroken tokens (states, table names) must wrap, not overflow. */
.brk { overflow-wrap: anywhere; word-break: break-word; }
td { overflow-wrap: anywhere; }
.tag.area { background: #e5eefc; }
.tag.tagchip { background: #efe7fb; color: #5b3aa6; }
.tag.val { background: #eef3f7; }
h3.grp { margin: 18px 0 8px; font-size: 14px; color: #41506a;
  border-bottom: 1px solid #e7ebf0; padding-bottom: 4px; }
h3.grp a { color: #2563eb; text-decoration: none; }
.tag-filter { display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
  margin: 8px 0 14px; }
.tagchip.filter { cursor: pointer; border: 1px solid transparent; }
.tagchip.filter:hover { border-color: #5b3aa6; }
.tagchip.filter.active { background: #5b3aa6; color: #fff; }
.tag.concept { background: #e9f5ea; }
.tag.phys { background: #f3eee2; font-family: ui-monospace, monospace; }
.conf-high { color: #1a7f37; } .conf-medium { color: #9a6700; }
.conf-low { color: #cf222e; font-weight: 700; }
.low-note { background: #fff5f5; border-left: 3px solid #cf222e;
  padding: 6px 10px; font-size: 13px; margin-top: 8px; }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
th, td { border: 1px solid #e2e6ea; padding: 6px 8px; text-align: left; vertical-align: top; }
th { background: #f0f3f6; }
.crud { font-family: ui-monospace, monospace; letter-spacing: 1px; }
.crud .on { color: #1a7f37; font-weight: 700; }
.crud .off { color: #cbd2d9; }
code { background: #f0f3f6; padding: 1px 4px; border-radius: 3px; font-size: 12px; }
.muted { color: #8b95a1; }

/* Inline review pins: a small + on each reviewable item. */
.rv-pin { border: 1px solid #c4ccd4; background: #fff; color: #2563eb;
  border-radius: 50%; width: 18px; height: 18px; line-height: 15px;
  font-size: 13px; padding: 0; margin-left: 6px; cursor: pointer;
  vertical-align: middle; }
.rv-pin:hover { background: #2563eb; color: #fff; border-color: #2563eb; }

.subtabs { display: flex; gap: 8px; margin-bottom: 12px; }
.subtabs label { font-size: 13px; padding: 4px 12px; border: 1px solid #c4ccd4;
  border-radius: 6px; cursor: pointer; background: #fff; }
.subtabs input { display: none; }
.subtabs input:checked + label { background: #2563eb; color: #fff; border-color: #2563eb; }
/* CSS-only toggle between the two CRUD views. */
#crud-by-area, #crud-by-concept { display: none; }
#crud-pick-area:checked ~ #crud-by-area { display: block; }
#crud-pick-concept:checked ~ #crud-by-concept { display: block; }
"""


def e(s) -> str:
    return html.escape(str(s)) if s is not None else ""


def tags(items, cls: str = "") -> str:
    if not items:
        return '<span class="muted">—</span>'
    c = f"tag {cls}".strip()
    return "".join(f'<span class="{c}">{e(i)}</span>' for i in items)


def conf_badge(cat: Catalog, level: str) -> str:
    if not level:
        return ""
    return f'<span class="conf-{e(level)}">{e(cat.t(f"confidence.{level}"))}</span>'


def pin(target_type: str, target_id: str, target_name: str,
        field: str = "", field_label: str = "") -> str:
    """A small inline button to attach a review finding to an item.

    Clicking it postMessages the parent app (the dramaturgy UI), which opens
    the inline finding popover. Harmless (no-op) when the HTML is opened
    standalone outside the app.

    ``field`` pins a comment to a specific element/row within the item (e.g.
    "purpose", "crud:order", an actor action). ``field_label`` is the
    human-readable thing being commented on. Both are optional; without them
    the pin targets the whole item.
    """
    attrs = (f' data-rv-type="{e(target_type)}"'
             f' data-rv-id="{e(target_id)}"'
             f' data-rv-name="{e(target_name)}"')
    if field:
        attrs += f' data-rv-field="{e(field)}"'
    if field_label:
        attrs += f' data-rv-field-label="{e(field_label)}"'
    return f'<button class="rv-pin" title="review"{attrs}>+</button>'


def crud_cells(ops) -> str:
    """Render C R U D as colored letters (present = on).

    Accepts ops as a string ("CRU") or a list (["C","R","U"]).
    """
    if isinstance(ops, (list, tuple)):
        ops = "".join(ops)
    ops = str(ops or "").upper()
    out = []
    for ch in "CRUD":
        cls = "on" if ch in ops else "off"
        out.append(f'<span class="{cls}">{ch}</span>')
    return f'<span class="crud">{"".join(out)}</span>'


def _concept_name(concepts: dict, cid: str) -> str:
    c = concepts.get(cid)
    return c.get("name") if c and c.get("name") else cid


def _area_name(areas: dict, aid: str) -> str:
    a = areas.get(aid)
    return a.get("name") if a and a.get("name") else aid


def render_area_box(cat: Catalog, area: dict, concepts: dict) -> str:
    aid, aname = area.get("id"), area.get("name")

    def apin(field, label):
        return pin("area", aid, aname, field, label)

    # The concepts this area touches, with its CRUD ops (area-side view).
    # Each row is individually commentable.
    crud_rows = ""
    for entry in area.get("concept_crud", []) or []:
        cid = entry.get("concept_id")
        cname = _concept_name(concepts, cid)
        crud_rows += (f"<tr><td>{e(cname)}"
                      f"{apin('crud:' + str(cid), 'CRUD / ' + cname)}</td>"
                      f"<td>{crud_cells(entry.get('ops', ''))}</td></tr>")
    crud_block = (f'<table><tr><th>{e(cat.t("label.concepts"))}</th>'
                  f'<th>CRUD</th></tr>{crud_rows}</table>'
                  if crud_rows else f'<span class="muted">{e(cat.t("empty.none"))}</span>')

    # Each actor's involvement is individually commentable.
    actor_lines = ""
    for a in area.get("actors", []) or []:
        actor_id = a.get("actor_id")
        acts = a.get("actions", [])
        acts = ", ".join(acts) if isinstance(acts, list) else str(acts)
        actor_lines += (f"<li><b>{e(actor_id)}</b>: {e(acts)}"
                        f"{apin('actor:' + str(actor_id), str(actor_id))}</li>")
    flows = ""
    for f in area.get("flows", []) or []:
        name = f.get("name") if isinstance(f, dict) else f
        flows += f"<li>{e(name)}{apin('flow:' + str(name), str(name))}</li>"

    # (field key, label, rendered value) — every field gets its own pin.
    rows = [
        ("purpose", cat.t("label.purpose"), e(area.get("purpose")) or "—"),
        ("parent", cat.t("label.parent"), e(area.get("parent_area_id")) or "—"),
        ("children", cat.t("label.children"), tags(area.get("child_area_ids"), "area")),
        ("related", cat.t("label.related"), tags(area.get("related_area_ids"), "area")),
        ("actors", cat.t("label.actors"), f"<ul>{actor_lines}</ul>" if actor_lines else "—"),
        ("crud", cat.t("label.crud"), crud_block),
        ("flows", cat.t("label.flows"), f"<ul>{flows}</ul>" if flows else "—"),
        ("apis", cat.t("label.apis"), tags(area.get("apis"))),
        ("screens", cat.t("label.screens"), tags(area.get("screens"))),
        ("code_refs", cat.t("label.code_refs"),
         " ".join(f"<code>{e(r)}</code>" for r in area.get("code_refs", [])) or "—"),
        ("risk_points", cat.t("label.risk_points"), tags(area.get("risk_points"))),
        ("open_questions", cat.t("label.open_questions"), tags(area.get("open_questions"))),
        ("confidence", cat.t("label.confidence"), conf_badge(cat, area.get("confidence"))),
    ]
    kv = "".join(
        f"<dt>{k}{apin(fkey, k)}</dt><dd>{v}</dd>" for fkey, k, v in rows)
    low = (f'<div class="low-note">{e(cat.t("note.low_confidence"))}</div>'
           if area.get("confidence") == "low" else "")
    return (
        f'<details class="box" id="area-{e(aid)}">'
        f'<summary><span class="sum-name">{e(aname)}'
        f'{apin("", aname)}</span>'
        f'<span class="sum-id">{e(aid)}</span></summary>'
        f'<div class="body"><p>{e(area.get("one_liner"))}'
        f'{apin("one_liner", cat.t("label.one_liner"))}</p>'
        f'<dl class="kv">{kv}</dl>{low}</div></details>')


def render_areas(cat: Catalog, areas: list, concepts: dict) -> str:
    if not areas:
        return f'<p class="muted">{e(cat.t("empty.none"))}</p>'
    boxes = "".join(render_area_box(cat, a, concepts) for a in areas)
    return (f'<p class="muted">{e(cat.t("areas.hint"))}</p>'
            f'<div class="box-grid">{boxes}</div>')


def tag_chips(tag_list, *, clickable: bool = False) -> str:
    if not tag_list:
        return '<span class="muted">—</span>'
    out = []
    for tg in tag_list:
        attr = f' data-tag="{e(tg)}"' if clickable else ""
        cls = "tag tagchip" + (" filter" if clickable else "")
        out.append(f'<span class="{cls}"{attr}>{e(tg)}</span>')
    return "".join(out)


def render_concept_tables(cat: Catalog, concepts: list, areas: dict) -> str:
    if not concepts:
        return f'<p class="muted">{e(cat.t("empty.none"))}</p>'

    # System-specific tag vocabulary present across the concepts → filter bar.
    all_tags = sorted({tg for c in concepts for tg in (c.get("tags") or [])})

    rows = ""
    for c in concepts:
        cid, cname = c.get("id"), c.get("name")
        ctags = c.get("tags") or []

        def cpin(field, label):
            return pin("concept", cid, cname, field, label)

        area_links = [_area_name(areas, aid) for aid in c.get("related_areas", [])]
        # data-tags lets the inline filter show/hide rows by tag.
        rows += (
            f'<tr class="concept-row" data-tags="{e(" ".join(ctags))}">'
            f'<td class="brk"><b>{e(cname)}</b>{cpin("", cname)}<br>'
            f"<span class='muted'>{e(c.get('description'))}"
            f"{cpin('description', cat.t('label.concepts'))}</span></td>"
            f'<td class="brk">{tag_chips(ctags)}'
            f"{cpin('tags', cat.t('label.tags_col'))}</td>"
            f'<td class="brk">{tags(c.get("physical_tables"), "phys")}'
            f"{cpin('physical_tables', cat.t('label.physical_tables'))}</td>"
            f'<td>{tags(area_links, "area")}</td>'
            f'<td class="brk">{tags(c.get("states"))}'
            f"{cpin('states', cat.t('label.states'))}</td></tr>")

    filter_bar = ""
    if all_tags:
        filter_bar = (
            f'<div class="tag-filter" id="concept-tag-filter">'
            f'<span class="muted tiny">{e(cat.t("concepts.filter"))}</span>'
            f'<span class="tag tagchip filter active" data-tag="*">'
            f'{e(cat.t("concepts.filter_all"))}</span>'
            f'{tag_chips(all_tags, clickable=True)}</div>')

    return (
        f'<p class="muted">{e(cat.t("concepts.hint"))}</p>'
        f'{filter_bar}'
        f"<table><tr><th>{e(cat.t('label.concept_table'))}</th>"
        f"<th>{e(cat.t('label.tags_col'))}</th>"
        f"<th>{e(cat.t('label.physical_tables'))}</th>"
        f"<th>{e(cat.t('label.related'))}</th>"
        f"<th>{e(cat.t('label.states'))}</th></tr>{rows}</table>")


def render_crud(cat: Catalog, areas: list, concepts: list) -> str:
    """Two views of the same concept-centric CRUD data."""
    area_map = {a["id"]: a for a in areas}
    concept_map = {c["id"]: c for c in concepts}

    # By area: flat table area | concept | CRUD.
    flat_area = ""
    for area in areas:
        for entry in area.get("concept_crud", []) or []:
            cid = entry.get("concept_id")
            flat_area += (f"<tr><td>{e(area.get('name'))}</td>"
                          f"<td>{e(_concept_name(concept_map, cid))}</td>"
                          f"<td>{crud_cells(entry.get('ops', ''))}</td></tr>")
    by_area = (
        f"<table><tr><th>{e(cat.t('nav.areas'))}</th>"
        f"<th>{e(cat.t('label.concept_table'))}</th><th>CRUD</th></tr>"
        f"{flat_area}</table>" if flat_area
        else f'<p class="muted">{e(cat.t("empty.none"))}</p>')

    # By concept: rows = concept | area | CRUD (from crud_by_area).
    flat_concept = ""
    for c in concepts:
        for entry in c.get("crud_by_area", []) or []:
            aid = entry.get("area_id")
            flat_concept += (f"<tr><td>{e(c.get('name'))}</td>"
                             f"<td>{e(_area_name(area_map, aid))}</td>"
                             f"<td>{crud_cells(entry.get('ops', ''))}</td></tr>")
    by_concept = (
        f"<table><tr><th>{e(cat.t('label.concept_table'))}</th>"
        f"<th>{e(cat.t('nav.areas'))}</th><th>CRUD</th></tr>"
        f"{flat_concept}</table>" if flat_concept
        else f'<p class="muted">{e(cat.t("empty.none"))}</p>')

    # CSS-only toggle between the two directions.
    return (
        '<input type="radio" name="crudview" id="crud-pick-area" checked>'
        '<input type="radio" name="crudview" id="crud-pick-concept">'
        '<div class="subtabs">'
        f'<label for="crud-pick-area">{e(cat.t("crud.by_area"))}</label>'
        f'<label for="crud-pick-concept">{e(cat.t("crud.by_concept"))}</label>'
        '</div>'
        f'<div id="crud-by-area">{by_area}</div>'
        f'<div id="crud-by-concept">{by_concept}</div>')


def _actor_card(cat: Catalog, a: dict) -> str:
    aid, aname = a.get("id"), a.get("name")

    def acpin(field, label):
        return pin("actor", aid, aname, field, label)

    actions = ""
    for i, act in enumerate(a.get("actions", [])):
        label = act.get("action") or f"action {i + 1}"
        actions += (
            f"<li>{e(act.get('action'))} "
            f"<span class='muted'>({e(act.get('area_id'))})</span> "
            f"— {e(act.get('description'))}"
            f"{acpin('action:' + str(i), label)}</li>")
    return (
        f'<div class="box" id="actor-{e(aid)}" style="padding:14px;margin-bottom:12px">'
        f'<h3 style="margin:0 0 6px">{e(aname)}{acpin("", aname)}</h3>'
        f'<p class="brk">{e(a.get("description"))}'
        f'{acpin("description", cat.t("label.actors"))}</p>'
        f'<ul>{actions}</ul></div>')


def render_actors(cat: Catalog, actors: list) -> str:
    """Actors grouped by category: business people first, then systems that
    are treated as actors. Pure infrastructure is NOT here (see components)."""
    if not actors:
        return f'<p class="muted">{e(cat.t("empty.none"))}</p>'
    persons = [a for a in actors if a.get("category", "person") != "system"]
    systems = [a for a in actors if a.get("category") == "system"]
    out = ""
    if persons:
        out += f'<h3 class="grp">{e(cat.t("actors.person"))}</h3>'
        out += "".join(_actor_card(cat, a) for a in persons)
    if systems:
        out += f'<h3 class="grp">{e(cat.t("actors.system"))}</h3>'
        out += "".join(_actor_card(cat, a) for a in systems)
    return out


def render_classifications(cat: Catalog, classifications: list,
                           concepts: dict) -> str:
    """Enumerations / code values. Grouped by the concept they detail; those
    with no concept_id are 'business-rule premises'."""
    if not classifications:
        return f'<p class="muted">{e(cat.t("empty.none"))}</p>'

    def cl_card(cl: dict) -> str:
        clid, clname = cl.get("id"), cl.get("name")

        def clpin(field, label):
            return pin("classification", clid, clname, field, label)

        vals = ""
        for v in cl.get("values", []) or []:
            if isinstance(v, dict):
                code, lab = v.get("code", ""), v.get("label", "")
                vals += (f'<span class="tag val"><code>{e(code)}</code> '
                         f'{e(lab)}</span>')
            else:
                vals += f'<span class="tag val">{e(v)}</span>'
        vals = vals or f'<span class="muted">{e(cat.t("empty.none"))}</span>'
        return (
            f'<div class="box" id="classification-{e(clid)}" '
            f'style="padding:12px;margin-bottom:10px">'
            f'<b>{e(clname)}</b>{clpin("", clname)}<br>'
            f'<span class="muted tiny brk">{e(cl.get("description"))}</span>'
            f'<div class="vals brk" style="margin-top:6px">{vals}'
            f'{clpin("values", cat.t("label.values"))}</div></div>')

    # Group by concept_id (None → premises bucket).
    by_concept: dict = {}
    premises: list = []
    for cl in classifications:
        cid = cl.get("concept_id")
        if cid:
            by_concept.setdefault(cid, []).append(cl)
        else:
            premises.append(cl)

    out = f'<p class="muted">{e(cat.t("classifications.hint"))}</p>'
    for cid, items in by_concept.items():
        title = _concept_name(concepts, cid)
        out += (f'<h3 class="grp">{e(cat.t("classifications.of"))} '
                f'<a href="#concept-{e(cid)}">{e(title)}</a></h3>')
        out += "".join(cl_card(c) for c in items)
    if premises:
        out += f'<h3 class="grp">{e(cat.t("classifications.premises"))}</h3>'
        out += "".join(cl_card(c) for c in premises)
    return out


def render_components(cat: Catalog, components: list) -> str:
    """Structural / infrastructure systems (LB, monitoring, middleware) —
    things that are not business actors."""
    if not components:
        return f'<p class="muted">{e(cat.t("empty.none"))}</p>'
    rows = ""
    for c in components:
        cid, cname = c.get("id"), c.get("name")
        refs = " ".join(f"<code>{e(r)}</code>" for r in c.get("code_refs", []))
        rows += (
            f'<tr id="component-{e(cid)}"><td class="brk"><b>{e(cname)}</b>'
            f'{pin("component", cid, cname, "", cname)}</td>'
            f'<td>{e(c.get("kind"))}</td>'
            f'<td class="brk">{e(c.get("description"))}</td>'
            f'<td class="brk">{refs or "—"}</td></tr>')
    return (
        f'<p class="muted">{e(cat.t("components.hint"))}</p>'
        f"<table><tr><th>{e(cat.t('label.component'))}</th>"
        f"<th>kind</th><th>{e(cat.t('label.concepts'))}</th>"
        f"<th>{e(cat.t('label.code_refs'))}</th></tr>{rows}</table>")


def render_dev(cat: Catalog, areas: list) -> str:
    rows = ""
    for area in areas:
        refs = ", ".join(f"<code>{e(r)}</code>" for r in area.get("code_refs", []))
        rows += (f"<tr><td>{e(area.get('name'))}</td>"
                 f"<td>{tags(area.get('apis'))}</td>"
                 f"<td>{refs or '—'}</td></tr>")
    return (f"<table><tr><th>{e(cat.t('nav.areas'))}</th>"
            f"<th>{e(cat.t('label.apis'))}</th>"
            f"<th>{e(cat.t('label.code_refs'))}</th></tr>{rows}</table>")


def render_validation(cat: Catalog, mm: dict) -> str:
    items = mm.get("validations", [])
    report = mm.get("merge_report", {})
    blocks = []
    if report:
        blocks.append(
            f"<pre><code>{e(json.dumps(report, ensure_ascii=False, indent=2))}</code></pre>")
    if items:
        blocks.append("<ul>" + "".join(f"<li>{e(v)}</li>" for v in items) + "</ul>")
    return "".join(blocks) or f'<p class="muted">{e(cat.t("empty.none"))}</p>'


def render_html(mm: dict, ui_lang: str) -> str:
    content_lang = mm.get("content_lang") or ui_lang
    cat = Catalog(ui_lang, domain="html")
    system = mm.get("system", {})

    lang_note = ""
    if content_lang != ui_lang:
        lang_note = (f'<div class="meta">'
                     f'{e(cat.t("note.content_lang", content_lang=content_lang))}</div>')

    # Actors first: that is the usual entry point for review.
    nav_items = [
        ("actors", "nav.actors"), ("concepts", "nav.concepts"),
        ("classifications", "nav.classifications"),
        ("areas", "nav.areas"), ("crud", "nav.crud"),
        ("components", "nav.components"),
        ("dev", "nav.dev"), ("validation", "nav.validation"),
    ]
    nav = "".join(f'<a href="#{anchor}">{e(cat.t(key))}</a>'
                  for anchor, key in nav_items)

    areas = mm.get("areas", [])
    concepts = mm.get("concepts", [])
    concept_map = {c["id"]: c for c in concepts}
    area_map = {a["id"]: a for a in areas}

    sections = [
        f'<section id="actors"><h2>{e(cat.t("nav.actors"))}</h2>'
        f'{render_actors(cat, mm.get("actors", []))}</section>',
        f'<section id="concepts"><h2>{e(cat.t("nav.concepts"))}</h2>'
        f'{render_concept_tables(cat, concepts, area_map)}</section>',
        f'<section id="classifications"><h2>{e(cat.t("nav.classifications"))}</h2>'
        f'{render_classifications(cat, mm.get("classifications", []), concept_map)}</section>',
        f'<section id="areas"><h2>{e(cat.t("nav.areas"))}</h2>'
        f'{render_areas(cat, areas, concept_map)}</section>',
        f'<section id="crud"><h2>{e(cat.t("nav.crud"))}</h2>'
        f'{render_crud(cat, areas, concepts)}</section>',
        f'<section id="components"><h2>{e(cat.t("nav.components"))}</h2>'
        f'{render_components(cat, mm.get("components", []))}</section>',
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
<div class="meta">{e(system.get("summary"))}</div>
<div class="meta">{e(cat.t("footer.generated_at", generated_at=system.get("generated_at","")))}</div>
{lang_note}</header>
<nav>{nav}</nav>
<main>{"".join(sections)}</main>
<script>
// Inline review: clicking a + pin tells the parent app to open the finding
// popover for that item. No-op when opened standalone (no parent listener).
document.addEventListener('click', function (ev) {{
  var b = ev.target.closest('.rv-pin');
  if (!b) return;
  ev.preventDefault();
  var msg = {{ source: 'dramaturgy-review', target_type: b.dataset.rvType,
    target_id: b.dataset.rvId, target_name: b.dataset.rvName,
    field: b.dataset.rvField || '', field_label: b.dataset.rvFieldLabel || '' }};
  if (window.parent && window.parent !== window) window.parent.postMessage(msg, '*');
}});

// Concept tag filter: click a chip to show only matching concept rows.
(function () {{
  var bar = document.getElementById('concept-tag-filter');
  if (!bar) return;
  bar.addEventListener('click', function (ev) {{
    var chip = ev.target.closest('.tagchip.filter');
    if (!chip) return;
    var tag = chip.dataset.tag;
    bar.querySelectorAll('.tagchip.filter').forEach(function (c) {{
      c.classList.toggle('active', c === chip);
    }});
    document.querySelectorAll('.concept-row').forEach(function (row) {{
      var tags = (row.dataset.tags || '').split(' ').filter(Boolean);
      row.style.display = (tag === '*' || tags.indexOf(tag) >= 0) ? '' : 'none';
    }});
  }});
}})();
</script>
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

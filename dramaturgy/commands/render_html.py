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
- Validation.
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
.tiny { font-size: 12px; }
/* Fixed nav height so the sticky lane header can butt right up against it. */
nav { position: sticky; top: 0; background: #243140; padding: 0 24px;
  height: 38px; display: flex; align-items: center; gap: 16px;
  overflow-x: auto; white-space: nowrap; z-index: 10; }
nav a { color: #cfe0f0; text-decoration: none; font-size: 13px; }
nav a:hover { color: #fff; }
main { max-width: 1100px; margin: 0 auto; padding: 24px; }
section { background: #fff; border: 1px solid #e2e6ea; border-radius: 8px;
  padding: 20px; margin-bottom: 24px; }
section > h2 { margin-top: 0; border-bottom: 2px solid #eef1f4; padding-bottom: 8px; }
/* Anchored items must clear the sticky nav when scrolled to. */
section, details.box, .box[id], [id^="actor-"],
[id^="concept-"], [id^="classification-"], [id^="component-"] {
  scroll-margin-top: 40px; }

/* Area boxes: grid of clickable cards that expand in place. */
.box-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px; }
/* No overflow:hidden — it would become the scroll context and break the
   sticky lane header inside an expanded area's swimlane. */
details.box { border: 1px solid #d4dae0; border-radius: 8px; background: #fbfcfd; }
details.box[open] { grid-column: 1 / -1; background: #fff; border-color: #9db4cc; }
details.box > summary { list-style: none; cursor: pointer; padding: 14px 16px;
  font-weight: 600; display: flex; align-items: baseline; justify-content: space-between; }
details.box > summary::-webkit-details-marker { display: none; }
details.box > summary:hover { background: #eef3f8; }
details.box .sum-name { font-size: 15px; }
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
a.tag.area { color: #1f4f9c; text-decoration: none; }
a.tag.area:hover { background: #d3e2fb; }
.tag.tagchip { background: #efe7fb; color: #5b3aa6; }
.tag.val { background: #eef3f7; }

/* Tag legend (groups + tag meanings) */
.tag-legend { margin: 8px 0 12px; border: 1px solid #e2e6ea; border-radius: 8px;
  background: #fbfbfd; }
.tag-legend > summary { cursor: pointer; padding: 8px 12px; font-size: 13px;
  font-weight: 600; color: #41506a; }
.tg-grid { display: grid; grid-template-columns: repeat(auto-fill,minmax(240px,1fr));
  gap: 12px; padding: 8px 12px 12px; }
.tg-block { border: 1px solid #eef1f4; border-radius: 6px; padding: 8px 10px;
  background: #fff; }
.tg-name { font-weight: 600; font-size: 13px; color: #41506a; }
.tg-tags { list-style: none; margin: 6px 0 0; padding: 0; }
.tg-tags li { margin: 3px 0; font-size: 12px; }

/* Overview business flow (swimlane) */
.overview-flow { margin: 12px 0 16px; }
.overview-flow h4 { margin: 0 0 8px; font-size: 13px; color: #41506a; }
/* no overflow:hidden here — it would trap the sticky lane header */
.swimlane { border: 1px solid #e2e6ea; border-radius: 8px; background: #fbfcfd; }
.sl-title { padding: 6px 10px; font-weight: 600; font-size: 13px;
  background: #eef3f8; border-bottom: 1px solid #e2e6ea; border-radius: 8px 8px 0 0; }
/* Lane (actor) header sticks below the page nav while the flow scrolls. */
.sl-head { display: grid; gap: 0; position: sticky; top: 38px; z-index: 5; }
.sl-lane { padding: 6px 8px; font-size: 12px; font-weight: 600; color: #41506a;
  text-align: center; background: #e9eef4; border-right: 1px solid #dde3ea;
  border-bottom: 1px solid #dde3ea; }
.sl-lane:last-child { border-right: 0; }
.sl-row { display: grid; gap: 0; border-top: 1px solid #eef1f4;
  background-image: none; }
/* Boundary between unrelated use cases sharing the same area. */
.sl-divider { border-top: 2px dashed #b9c4d0; background: #f4f6f9;
  padding: 4px 10px; }
.sl-uc-name { font-size: 11px; font-weight: 600; color: #41506a; }
.sl-uc-name.muted { font-weight: 400; color: #8b95a1; }
/* faint lane separators down the rows */
.sl-step { margin: 6px; padding: 6px 8px; font-size: 12px; background: #fff;
  border: 1px solid #cdd6e0; border-radius: 6px; }
.sl-n { display: inline-block; min-width: 16px; height: 16px; line-height: 16px;
  text-align: center; background: #2563eb; color: #fff; border-radius: 50%;
  font-size: 10px; margin-right: 6px; }
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

/* CRUD table controls (sort + filters) */
.crud-controls { display: flex; gap: 16px; flex-wrap: wrap; margin: 8px 0 12px;
  font-size: 13px; color: #41506a; align-items: flex-start; }
/* Make the sort <select> look like the combobox button (resting state). */
.crud-controls select { font-size: 13px; padding: 4px 26px 4px 10px;
  border: 1px solid #c4ccd4; border-radius: 6px; background-color: #fff;
  color: #1c1f23; cursor: pointer; appearance: none; -webkit-appearance: none;
  background-image: url("data:image/svg+xml;charset=utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6' fill='none' stroke='%2341506a' stroke-width='1.5'%3E%3Cpath d='M1 1l4 4 4-4'/%3E%3C/svg%3E");
  background-repeat: no-repeat; background-position: right 9px center;
  background-size: 10px 6px; }
/* Searchable multi-select combobox */
.ms { position: relative; }
.ms-btn { font-size: 13px; padding: 4px 10px; border: 1px solid #c4ccd4;
  border-radius: 6px; background: #fff; cursor: pointer; }
.ms-panel { position: absolute; z-index: 20; top: 100%; left: 0; margin-top: 4px;
  width: 260px; max-width: 80vw; background: #fff; border: 1px solid #c4ccd4;
  border-radius: 8px; box-shadow: 0 6px 20px rgba(0,0,0,.15); padding: 8px; }
.ms-search { width: 100%; font-size: 13px; padding: 5px 8px; margin-bottom: 6px;
  border: 1px solid #c4ccd4; border-radius: 6px; }
.ms-opts { max-height: 240px; overflow: auto; }
.ms-opt { display: block; font-size: 13px; padding: 3px 4px; cursor: pointer;
  white-space: normal; }
.ms-opt:hover { background: #eef3f8; }
.ms-opt input { margin-right: 6px; }
/* Subtle jump link at the end of an area / concept cell. */
a.jump { color: #b6bfca; text-decoration: none; margin-left: 4px; font-size: 11px; }
a.jump:hover { color: #2563eb; }
/* Area reference shown next to an actor's action (links to the area). */
a.area-ref { color: #8b95a1; text-decoration: none; font-size: 12px; }
a.area-ref:hover { color: #2563eb; }
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


def render_swimlane(cat: Catalog, flow: dict, actors: dict) -> str:
    """Render an overview business flow as a swimlane diagram.

    ``flow`` = {title?, lanes: [actor_id, …], steps: [{lane, label}, …]}.
    Lanes are vertical columns (one per actor); steps drop into their lane in
    order, numbered, so someone who has never used the system can follow the
    overall flow top-to-bottom. Pure CSS grid — no JS, works in the iframe.
    """
    lanes = flow.get("lanes") or []
    steps = flow.get("steps") or []
    if not lanes:
        # Fall back to the order the steps mention lanes in.
        seen = []
        for s in steps:
            ln = s.get("lane")
            if ln and ln not in seen:
                seen.append(ln)
        lanes = seen
    if not lanes or not steps:
        return ""

    lane_idx = {ln: i for i, ln in enumerate(lanes)}
    ncols = len(lanes)

    def lane_label(ln):
        a = actors.get(ln)
        return a.get("name") if a and a.get("name") else ln

    # Header row of lane names.
    cells = "".join(f'<div class="sl-lane">{e(lane_label(ln))}</div>'
                    for ln in lanes)
    # Steps may belong to different use cases within the same area (e.g.
    # "master approval" vs. "batch monitoring") that share actors but are not
    # part of one continuous flow. We keep a single swimlane and draw a
    # divider (with the use-case name when present) wherever the use case
    # changes, restarting the step numbering for each use case.
    rows = ""
    _UNSET = object()
    prev_uc = _UNSET
    n = 0
    for s in steps:
        uc = s.get("use_case")
        if uc != prev_uc:
            # Boundary between use cases that share this area but aren't one
            # continuous flow. Draw a divider with the use-case name; skip it
            # only at the very top when the first group is unnamed.
            if rows or uc:
                name = (e(uc) if uc else e(cat.t("flow.other_usecase")))
                cls = "sl-uc-name" + ("" if uc else " muted")
                rows += (f'<div class="sl-divider">'
                         f'<span class="{cls}">{name}</span></div>')
            prev_uc = uc
            n = 0
        n += 1
        ln = s.get("lane")
        col = lane_idx.get(ln, 0) + 1
        label = s.get("label") or s.get("action") or ""
        rows += (
            f'<div class="sl-row" style="grid-template-columns:repeat({ncols},1fr)">'
            f'<div class="sl-step" style="grid-column:{col}">'
            f'<span class="sl-n">{n}</span>{e(label)}</div></div>')
    title = flow.get("title") or flow.get("name") or ""
    title_html = f'<div class="sl-title">{e(title)}</div>' if title else ""
    return (
        f'<div class="swimlane">{title_html}'
        f'<div class="sl-head" style="grid-template-columns:repeat({ncols},1fr)">'
        f'{cells}</div>{rows}</div>')


def render_area_box(cat: Catalog, area: dict, concepts: dict,
                    actors: dict | None = None,
                    area_map: dict | None = None) -> str:
    aid, aname = area.get("id"), area.get("name")
    actors = actors or {}
    area_map = area_map or {}

    def apin(field, label):
        return pin("area", aid, aname, field, label)

    def area_tags(ids):
        # Linked tags showing each related area's display name (not its id).
        if not ids:
            return '<span class="muted">—</span>'
        return "".join(
            f'<a class="tag area" href="#area-{e(i)}">{e(_area_name(area_map, i))}</a>'
            for i in ids)

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

    # Each actor's involvement is individually commentable. Show the actor's
    # display name (from the top-level actors), not its id.
    def actor_label(actor_id):
        ac = actors.get(actor_id)
        return ac.get("name") if ac and ac.get("name") else actor_id

    actor_lines = ""
    for a in area.get("actors", []) or []:
        actor_id = a.get("actor_id")
        name = actor_label(actor_id)
        acts = a.get("actions", [])
        acts = ", ".join(acts) if isinstance(acts, list) else str(acts)
        actor_lines += (f"<li><b>{e(name)}</b>: {e(acts)}"
                        f"{apin('actor:' + str(actor_id), str(name))}</li>")
    flows = ""
    for f in area.get("flows", []) or []:
        name = f.get("name") if isinstance(f, dict) else f
        flows += f"<li>{e(name)}{apin('flow:' + str(name), str(name))}</li>"

    # (field key, label, rendered value) — every field gets its own pin.
    rows = [
        ("purpose", cat.t("label.purpose"), e(area.get("purpose")) or "—"),
        ("parent", cat.t("label.parent"),
         area_tags([area["parent_area_id"]]) if area.get("parent_area_id") else "—"),
        ("children", cat.t("label.children"), area_tags(area.get("child_area_ids"))),
        ("related", cat.t("label.related"), area_tags(area.get("related_area_ids"))),
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

    # Overview business flow (swimlane) — the at-a-glance picture for someone
    # who has never used the system. Shown above the detail fields.
    overview = area.get("overview_flow") or {}
    swim = render_swimlane(cat, overview, actors)
    overview_html = ""
    if swim:
        overview_html = (
            f'<div class="overview-flow"><h4>{e(cat.t("label.overview_flow"))}'
            f'{apin("overview_flow", cat.t("label.overview_flow"))}</h4>'
            f'{swim}</div>')

    return (
        f'<details class="box" id="area-{e(aid)}">'
        f'<summary><span class="sum-name">{e(aname)}'
        f'{apin("", aname)}</span></summary>'
        f'<div class="body"><p>{e(area.get("one_liner"))}'
        f'{apin("one_liner", cat.t("label.one_liner"))}</p>'
        f'{overview_html}'
        f'<dl class="kv">{kv}</dl>{low}</div></details>')


def render_areas(cat: Catalog, areas: list, concepts: dict,
                 actors: dict | None = None) -> str:
    if not areas:
        return f'<p class="muted">{e(cat.t("empty.none"))}</p>'
    area_map = {a["id"]: a for a in areas}
    boxes = "".join(render_area_box(cat, a, concepts, actors, area_map)
                    for a in areas)
    return (f'<p class="muted">{e(cat.t("areas.hint"))}</p>'
            f'<div class="box-grid">{boxes}</div>')


def tag_chips(tag_list, *, clickable: bool = False, vocab: dict | None = None) -> str:
    if not tag_list:
        return '<span class="muted">—</span>'
    vocab = vocab or {}
    out = []
    for tg in tag_list:
        attr = f' data-tag="{e(tg)}"' if clickable else ""
        # Tooltip = the tag's defined meaning (when present in the vocabulary).
        meta = vocab.get(tg) or {}
        desc = meta.get("description") or ""
        title = f' title="{e(desc)}"' if desc else ""
        cls = "tag tagchip" + (" filter" if clickable else "")
        out.append(f'<span class="{cls}"{attr}{title}>{e(tg)}</span>')
    return "".join(out)


def render_tag_legend(cat: Catalog, vocab: dict) -> str:
    """A legend of the tag vocabulary: groups, their tags, and each tag's
    meaning. Helps a reader understand what the tags mean."""
    tags_v = vocab.get("tags") or []
    if not tags_v:
        return ""
    groups = vocab.get("groups") or []
    gdesc = {g["name"]: g.get("description", "") for g in groups}
    # Bucket tags by group (preserve group order, then ungrouped last).
    order = [g["name"] for g in groups]
    buckets: dict = {}
    for t in tags_v:
        buckets.setdefault(t.get("group") or "", []).append(t)
    ordered_keys = [g for g in order if g in buckets] + \
        [k for k in buckets if k and k not in order] + \
        ([""] if "" in buckets else [])

    blocks = ""
    for g in ordered_keys:
        items = "".join(
            f'<li><span class="tag tagchip">{e(t["name"])}</span> '
            f'<span class="muted">{e(t.get("description"))}</span></li>'
            for t in buckets[g])
        if g:
            head = (f'<div class="tg-name">{e(g)}</div>'
                    + (f'<div class="muted tiny">{e(gdesc.get(g, ""))}</div>'
                       if gdesc.get(g) else ""))
        else:
            head = f'<div class="tg-name muted">{e(cat.t("tags.ungrouped"))}</div>'
        blocks += f'<div class="tg-block">{head}<ul class="tg-tags">{items}</ul></div>'
    return (f'<details class="tag-legend"><summary>{e(cat.t("tags.legend"))}</summary>'
            f'<div class="tg-grid">{blocks}</div></details>')


def render_concept_tables(cat: Catalog, concepts: list, areas: dict,
                          vocab: dict | None = None) -> str:
    if not concepts:
        return f'<p class="muted">{e(cat.t("empty.none"))}</p>'

    vocab = vocab or {"tags": [], "groups": []}
    vocab_map = {t["name"]: t for t in vocab.get("tags", [])}

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
        # id="concept-<id>" is the jump target used by CRUD links.
        rows += (
            f'<tr class="concept-row" id="concept-{e(cid)}" '
            f'data-tags="{e(" ".join(ctags))}">'
            f'<td class="brk"><b>{e(cname)}</b>{cpin("", cname)}<br>'
            f"<span class='muted'>{e(c.get('description'))}"
            f"{cpin('description', cat.t('label.concepts'))}</span></td>"
            f'<td class="brk">{tag_chips(ctags, vocab=vocab_map)}'
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
            f'{tag_chips(all_tags, clickable=True, vocab=vocab_map)}</div>')

    legend = render_tag_legend(cat, vocab)

    return (
        f'<p class="muted">{e(cat.t("concepts.hint"))}</p>'
        f'{legend}{filter_bar}'
        f"<table><tr><th>{e(cat.t('label.concept_table'))}</th>"
        f"<th>{e(cat.t('label.tags_col'))}</th>"
        f"<th>{e(cat.t('label.physical_tables'))}</th>"
        f"<th>{e(cat.t('label.related'))}</th>"
        f"<th>{e(cat.t('label.states'))}</th></tr>{rows}</table>")


def render_crud(cat: Catalog, areas: list, concepts: list) -> str:
    """One sortable/filterable table of (area × concept) CRUD rows.

    Each row carries data-area/data-concept (and -order indexes) so the inline
    controls can sort by concept or by area and filter to a chosen concept or
    area. Concept and area cells end with a subtle jump link to their section.
    """
    area_map = {a["id"]: a for a in areas}
    concept_map = {c["id"]: c for c in concepts}
    # Appearance order = index in the canonical lists (stable, == "登場順").
    area_order = {a["id"]: i for i, a in enumerate(areas)}
    concept_order = {c["id"]: i for i, c in enumerate(concepts)}

    def jump(anchor, label):
        return (f'<a class="jump" href="#{e(anchor)}" '
                f'title="{e(label)}">↗</a>')

    rows = ""
    for area in areas:
        aid = area.get("id")
        for entry in area.get("concept_crud", []) or []:
            cid = entry.get("concept_id")
            cname = _concept_name(concept_map, cid)
            p = pin("area", aid, area.get("name"),
                    "crud:" + str(cid), f"CRUD / {cname}")
            rows += (
                f'<tr class="crud-row" data-area="{e(aid)}" data-concept="{e(cid)}" '
                f'data-aorder="{area_order.get(aid, 9999)}" '
                f'data-corder="{concept_order.get(cid, 9999)}">'
                f'<td class="brk">{e(area.get("name"))}'
                f'{jump("area-" + str(aid), area.get("name"))}</td>'
                f'<td class="brk">{e(cname)}{jump("concept-" + str(cid), cname)}</td>'
                f'<td>{crud_cells(entry.get("ops", ""))}{p}</td></tr>')
    if not rows:
        return f'<p class="muted">{e(cat.t("empty.none"))}</p>'

    # Searchable multi-select combobox (checkbox list + search). Empty
    # selection = all. Pure markup; behavior is in the inline script below.
    def multiselect(box_id, label, items, order):
        opts = ""
        for it in sorted(items, key=lambda x: order.get(x["id"], 9999)):
            name = it.get("name") or it["id"]
            opts += (
                f'<label class="ms-opt" data-text="{e(name.lower())}">'
                f'<input type="checkbox" value="{e(it["id"])}"> {e(name)}</label>')
        return (
            f'<div class="ms" id="{box_id}">'
            f'<button type="button" class="ms-btn" data-all="{e(cat.t("crud.all"))}"'
            f' data-selfmt="{e(cat.t("crud.n_selected"))}">'
            f'{e(label)}: <span class="ms-summary">{e(cat.t("crud.all"))}</span> ▾</button>'
            f'<div class="ms-panel" hidden>'
            f'<input type="search" class="ms-search" placeholder="{e(cat.t("crud.search"))}">'
            f'<div class="ms-opts">{opts}</div></div></div>')

    controls = (
        '<div class="crud-controls">'
        f'<label>{e(cat.t("crud.sort_by"))} '
        '<select id="crud-sort">'
        f'<option value="concept">{e(cat.t("label.concept_table"))}</option>'
        f'<option value="area">{e(cat.t("nav.areas"))}</option>'
        '</select></label>'
        f'{multiselect("crud-filter-area", cat.t("nav.areas"), areas, area_order)}'
        f'{multiselect("crud-filter-concept", cat.t("label.concept_table"), concepts, concept_order)}'
        '</div>')

    table = (
        '<table id="crud-table"><thead><tr>'
        f'<th>{e(cat.t("nav.areas"))}</th>'
        f'<th>{e(cat.t("label.concept_table"))}</th>'
        f'<th>CRUD</th></tr></thead>'
        f'<tbody id="crud-tbody">{rows}</tbody></table>')
    return controls + table


def _actor_card(cat: Catalog, a: dict, areas: dict) -> str:
    aid, aname = a.get("id"), a.get("name")

    def acpin(field, label):
        return pin("actor", aid, aname, field, label)

    actions = ""
    for i, act in enumerate(a.get("actions", [])):
        label = act.get("action") or f"action {i + 1}"
        # Show the business area's display name (linked), not its raw id.
        area_id = act.get("area_id")
        area_html = ""
        if area_id:
            area_html = (f' <a class="muted area-ref" href="#area-{e(area_id)}">'
                         f'({e(_area_name(areas, area_id))})</a>')
        actions += (
            f"<li>{e(act.get('action'))}{area_html} "
            f"— {e(act.get('description'))}"
            f"{acpin('action:' + str(i), label)}</li>")
    return (
        f'<div class="box" id="actor-{e(aid)}" style="padding:14px;margin-bottom:12px">'
        f'<h3 style="margin:0 0 6px">{e(aname)}{acpin("", aname)}</h3>'
        f'<p class="brk">{e(a.get("description"))}'
        f'{acpin("description", cat.t("label.actors"))}</p>'
        f'<ul>{actions}</ul></div>')


def render_actors(cat: Catalog, actors: list, areas: dict | None = None) -> str:
    """Actors grouped by category: business people first, then systems that
    are treated as actors. Pure infrastructure is NOT here (see components)."""
    if not actors:
        return f'<p class="muted">{e(cat.t("empty.none"))}</p>'
    areas = areas or {}
    persons = [a for a in actors if a.get("category", "person") != "system"]
    systems = [a for a in actors if a.get("category") == "system"]
    out = ""
    if persons:
        out += f'<h3 class="grp">{e(cat.t("actors.person"))}</h3>'
        out += "".join(_actor_card(cat, a, areas) for a in persons)
    if systems:
        out += f'<h3 class="grp">{e(cat.t("actors.system"))}</h3>'
        out += "".join(_actor_card(cat, a, areas) for a in systems)
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


def render_html(mm: dict, ui_lang: str, vocab: dict | None = None) -> str:
    content_lang = mm.get("content_lang") or ui_lang
    cat = Catalog(ui_lang, domain="html")
    system = mm.get("system", {})
    vocab = vocab or {"tags": [], "groups": []}

    lang_note = ""
    if content_lang != ui_lang:
        lang_note = (f'<p class="muted tiny">'
                     f'{e(cat.t("note.content_lang", content_lang=content_lang))}</p>')

    nav_items = [
        ("actors", "nav.actors"), ("areas", "nav.areas"),
        ("concepts", "nav.concepts"), ("classifications", "nav.classifications"),
        ("crud", "nav.crud"), ("components", "nav.components"),
        ("validation", "nav.validation"),
    ]
    nav = "".join(f'<a href="#{anchor}">{e(cat.t(key))}</a>'
                  for anchor, key in nav_items)

    areas = mm.get("areas", [])
    concepts = mm.get("concepts", [])
    concept_map = {c["id"]: c for c in concepts}
    area_map = {a["id"]: a for a in areas}
    actor_map = {a["id"]: a for a in mm.get("actors", [])}

    sections = [
        f'<section id="actors"><h2>{e(cat.t("nav.actors"))}</h2>'
        f'{render_actors(cat, mm.get("actors", []), area_map)}</section>',
        f'<section id="areas"><h2>{e(cat.t("nav.areas"))}</h2>'
        f'{render_areas(cat, areas, concept_map, actor_map)}</section>',
        f'<section id="concepts"><h2>{e(cat.t("nav.concepts"))}</h2>'
        f'{render_concept_tables(cat, concepts, area_map, vocab)}</section>',
        f'<section id="classifications"><h2>{e(cat.t("nav.classifications"))}</h2>'
        f'{render_classifications(cat, mm.get("classifications", []), concept_map)}</section>',
        f'<section id="crud"><h2>{e(cat.t("nav.crud"))}</h2>'
        f'{render_crud(cat, areas, concepts)}</section>',
        f'<section id="components"><h2>{e(cat.t("nav.components"))}</h2>'
        f'{render_components(cat, mm.get("components", []))}</section>',
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
<nav>{nav}</nav>
<main>{lang_note}{"".join(sections)}</main>
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

// Searchable multi-select combobox: checkbox list + search; empty = all.
function setupMultiSelect(box, onChange) {{
  var btn = box.querySelector('.ms-btn');
  var panel = box.querySelector('.ms-panel');
  var search = box.querySelector('.ms-search');
  var summary = box.querySelector('.ms-summary');
  var allLabel = btn.dataset.all;
  var selFmt = btn.dataset.selfmt;   // e.g. "{{n}} 件選択"

  btn.addEventListener('click', function () {{
    panel.hidden = !panel.hidden;
    if (!panel.hidden) {{ search.value = ''; filter(''); search.focus(); }}
  }});
  document.addEventListener('click', function (ev) {{
    if (!box.contains(ev.target)) panel.hidden = true;
  }});
  function filter(q) {{
    q = q.toLowerCase();
    box.querySelectorAll('.ms-opt').forEach(function (o) {{
      o.style.display = o.dataset.text.indexOf(q) >= 0 ? '' : 'none';
    }});
  }}
  search.addEventListener('input', function () {{ filter(search.value); }});
  box.addEventListener('change', function () {{
    var sel = box.selected();
    summary.textContent = sel.length
      ? selFmt.replace('{{n}}', sel.length) : allLabel;
    onChange();
  }});
  box.selected = function () {{
    return Array.prototype.slice
      .call(box.querySelectorAll('input:checked')).map(function (i) {{ return i.value; }});
  }};
}}

// CRUD table: sort by concept/area, filter by selected areas and/or concepts.
(function () {{
  var tbody = document.getElementById('crud-tbody');
  if (!tbody) return;
  var sortSel = document.getElementById('crud-sort');
  var areaBox = document.getElementById('crud-filter-area');
  var conceptBox = document.getElementById('crud-filter-concept');
  var rows = Array.prototype.slice.call(tbody.querySelectorAll('.crud-row'));

  function apply() {{
    var by = sortSel.value;            // 'concept' | 'area'
    var fa = areaBox.selected(), fc = conceptBox.selected();
    var sorted = rows.slice().sort(function (a, b) {{
      var p = by === 'area'
        ? ['aorder', 'corder'] : ['corder', 'aorder'];
      var d = (+a.dataset[p[0]]) - (+b.dataset[p[0]]);
      return d !== 0 ? d : (+a.dataset[p[1]]) - (+b.dataset[p[1]]);
    }});
    sorted.forEach(function (row) {{
      var ok = (fa.length === 0 || fa.indexOf(row.dataset.area) >= 0) &&
               (fc.length === 0 || fc.indexOf(row.dataset.concept) >= 0);
      row.style.display = ok ? '' : 'none';
      tbody.appendChild(row);   // reorder in place
    }});
  }}
  setupMultiSelect(areaBox, apply);
  setupMultiSelect(conceptBox, apply);
  sortSel.addEventListener('change', apply);
  apply();
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

    try:
        vocab = read_json(ws / "tags.json")
    except FileNotFoundError:
        vocab = {"tags": [], "groups": []}

    out_path = Path(args.out) if args.out else (ws / "meaning-map.html")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_html(mm, rs.ui_lang, vocab), encoding="utf-8")
    print(rs.ui.t("render.done", path=str(out_path)))
    return 0

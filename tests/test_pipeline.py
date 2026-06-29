"""End-to-end and unit tests for the dramaturgy toolchain.

Run with: ``python -m pytest tests/`` or
``python -m unittest discover -s tests`` from the repo root.
Uses only the standard library (unittest) so it runs without extra deps.
Each test drives the CLI through the ``dra`` dispatcher against a temporary
workspace, so it also exercises subcommand routing.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

# Make the repo-root package importable when running from a source checkout.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dramaturgy.cli import COMMANDS, main as dra  # noqa: E402
from dramaturgy.common.config import (  # noqa: E402
    Config, load_config, save_config,
)
from dramaturgy.common.i18n import Catalog, validate_catalogs  # noqa: E402
from dramaturgy.common.prompts import load_prompt  # noqa: E402

SUPPORTED = ("ja", "en")
WORKSPACE = ".dramaturgy"


class _NoopProc:
    """A harmless fake Claude process for tests that auto-run findings but
    don't care about the run's effect."""
    @property
    def stdout(self):
        yield ('{"type":"result","is_error":false,"subtype":"success",'
               '"result":"ok"}\n')

    def wait(self):
        return 0


def _make_sample_repo(root: Path) -> None:
    (root / "app" / "models").mkdir(parents=True)
    (root / "db").mkdir()
    (root / "app" / "models" / "ticket.rb").write_text(
        "class Ticket < ApplicationRecord\n  get '/api/tickets/apply'\nend\n",
        encoding="utf-8")
    (root / "db" / "schema.sql").write_text(
        "CREATE TABLE events (id INT PRIMARY KEY, status ENUM('a','b'));\n"
        "CREATE TABLE tickets (id INT, event_id INT, "
        "FOREIGN KEY (event_id) REFERENCES events(id));\n",
        encoding="utf-8")


class CatalogTests(unittest.TestCase):
    def test_catalogs_consistent(self):
        for domain in ("cli", "html"):
            self.assertEqual(validate_catalogs(domain), [],
                             f"{domain} catalogs drifted")

    def test_prompts_exist_both_langs(self):
        for name in ("area_tree", "area_card", "split_review"):
            for lang in SUPPORTED:
                self.assertTrue(load_prompt(name, lang).strip())

    def test_fallback_to_default(self):
        cat = Catalog("en")
        # A real key resolves; an unknown key returns itself.
        self.assertIn("Done", cat.t("common.done"))
        self.assertEqual(cat.t("no.such.key"), "no.such.key")

    def test_unsupported_lang_rejected(self):
        with self.assertRaises(ValueError):
            Catalog("fr")


class ConfigTests(unittest.TestCase):
    def test_roundtrip_and_mixed_langs(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = Config(ui_lang="ja", content_lang="en",
                         project_name="X", repo_root=d)
            save_config(cfg, d)
            loaded = load_config(d)
            self.assertEqual(loaded.ui_lang, "ja")
            self.assertEqual(loaded.content_lang, "en")

    def test_validate_rejects_bad_lang(self):
        with self.assertRaises(ValueError):
            Config(ui_lang="xx").validate()


class DispatcherTests(unittest.TestCase):
    def test_help_and_version(self):
        self.assertEqual(0, dra(["--help"]))
        self.assertEqual(0, dra(["--version"]))

    def test_unknown_command(self):
        self.assertEqual(2, dra(["definitely-not-a-command"]))

    def test_all_commands_importable(self):
        import importlib
        for _, (module_name, _help) in COMMANDS.items():
            mod = importlib.import_module(
                f"dramaturgy.commands.{module_name}")
            self.assertTrue(hasattr(mod, "main"))


class PipelineTests(unittest.TestCase):
    def test_full_pipeline(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _make_sample_repo(root)
            ws = root / WORKSPACE

            self.assertEqual(0, dra([
                "setup", "--no-input", "--ui-lang", "ja",
                "--content-lang", "ja", "--project-name", "Sample",
                "--repo-root", d]))
            self.assertEqual(0, dra(["analyze-repo", "--repo-root", d]))

            # analyze-repo is inventory-only: files/dirs, no semantic tables.
            index = json.loads((ws / "source-index.json").read_text())
            self.assertIn("directories", index)
            self.assertNotIn("by_role", index)
            self.assertTrue(all("roles" not in f for f in index["files"]))

            # Author a minimal area-tree + area map.
            (ws / "area-tree.json").write_text(json.dumps({
                "content_lang": "ja",
                "system": {"name": "Sample", "summary": "s"},
                "areas": [{
                    "id": "sales", "name": "販売", "one_liner": "x",
                    "source_hints": {"keywords": ["ticket"]},
                    "confidence": "high",
                }],
            }, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(0, dra([
                "pack", "--repo-root", d, "--area-id", "sales"]))

            area_map = {
                "content_lang": "ja",
                "system": {"name": "Sample", "summary": "s",
                           "generated_at": "2026-06-26",
                           "source_summary": {"files": 1, "lines": 3,
                                              "tables": 2}},
                "actors": [{"id": "user", "name": "利用者",
                            "description": "d",
                            "actions": [{"area_id": "sales",
                                         "action": "買う",
                                         "description": "d"}]}],
                "areas": [{
                    "id": "sales", "name": "販売", "one_liner": "x",
                    "purpose": "p", "parent_area_id": None,
                    "child_area_ids": [], "related_area_ids": [],
                    "concepts": ["ticket"], "crud_summary": {"ticket": "CR"},
                    "tables": ["tickets"], "apis": ["/api/tickets/apply"],
                    "screens": [], "code_refs": [], "risk_points": [],
                    "open_questions": [], "confidence": "high",
                }],
                "concepts": [{"id": "ticket", "name": "チケット",
                              "description": "d", "kind": "entity",
                              "related_tables": ["tickets"],
                              "related_areas": ["sales"], "states": [],
                              "confidence": "high"}],
                "flows": [],
            }
            amap = ws / "area-maps" / "sales.json"
            amap.parent.mkdir(parents=True)
            amap.write_text(json.dumps(area_map, ensure_ascii=False),
                            encoding="utf-8")

            self.assertEqual(0, dra(["merge", "--repo-root", d, str(amap)]))
            self.assertEqual(0, dra(["validate", "--repo-root", d]))
            self.assertEqual(0, dra(["render", "--repo-root", d]))
            html = (ws / "meaning-map.html").read_text()
            self.assertIn("販売", html)
            self.assertIn('lang="ja"', html)

    def test_validate_detects_missing_code_ref(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _make_sample_repo(root)
            ws = root / WORKSPACE
            dra(["setup", "--no-input", "--repo-root", d,
                 "--content-lang", "ja"])
            dra(["analyze-repo", "--repo-root", d])
            mm = {
                "content_lang": "ja",
                "system": {"name": "S", "summary": "",
                           "source_summary": {}},
                "actors": [], "concepts": [], "flows": [],
                "areas": [{"id": "a", "name": "A", "tables": ["anything"],
                           "apis": [], "code_refs": ["no/such/file.rb"],
                           "related_area_ids": [], "child_area_ids": [],
                           "confidence": "high"}],
            }
            (ws / "meaning-map.json").write_text(
                json.dumps(mm, ensure_ascii=False), encoding="utf-8")
            # Non-zero exit: the referenced file does not exist. (Tables are
            # no longer checked — Claude discovers those from source.)
            self.assertEqual(1, dra(["validate", "--repo-root", d]))

    def test_mixed_language_html(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ws = root / WORKSPACE
            ws.mkdir(parents=True)
            save_config(Config(ui_lang="en", content_lang="ja", repo_root=d), d)
            (ws / "meaning-map.json").write_text(json.dumps({
                "content_lang": "ja",
                "system": {"name": "S", "summary": "概要",
                           "source_summary": {}},
                "actors": [], "concepts": [], "flows": [], "areas": [],
            }, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(0, dra(["render", "--repo-root", d]))
            html = (ws / "meaning-map.html").read_text()
            # English chrome, content language note present, lang=ja.
            self.assertIn("Concept data", html)   # English nav label
            self.assertIn("Content language: ja", html)
            self.assertIn('lang="ja"', html)


class ConceptCrudTests(unittest.TestCase):
    """The concept table is the canonical home of CRUD; merge aggregates the
    per-area declarations so it can be read from either side, and the HTML
    renders both directions."""

    def _two_area_maps(self):
        sales = {
            "content_lang": "ja", "system": {"name": "S"},
            "areas": [{"id": "sales", "name": "販売", "one_liner": "x",
                       "concepts": ["order", "ticket"],
                       "related_area_ids": [], "child_area_ids": [],
                       "concept_crud": [{"concept_id": "order", "ops": "CRU"},
                                        {"concept_id": "ticket", "ops": "CR"}],
                       "confidence": "high"}],
            "concepts": [
                {"id": "order", "name": "注文", "kind": "entity",
                 "physical_tables": ["orders", "order_items"]},
                {"id": "ticket", "name": "チケット", "kind": "entity",
                 "physical_tables": ["tickets"]}],
            "actors": [], "flows": []}
        admin = {
            "content_lang": "ja", "system": {"name": "S"},
            "areas": [{"id": "admin", "name": "管理", "one_liner": "y",
                       "concepts": ["order"],
                       "related_area_ids": [], "child_area_ids": [],
                       "concept_crud": [{"concept_id": "order",
                                         "ops": ["R", "U", "D"]}],
                       "confidence": "medium"}],
            "concepts": [], "actors": [], "flows": []}
        return sales, admin

    def test_merge_aggregates_concept_crud(self):
        from dramaturgy.commands.merge_maps import merge

        class _UI:
            def t(self, *a, **k):
                return ""

        merged, _ = merge(list(self._two_area_maps()), _UI())
        order = next(c for c in merged["concepts"] if c["id"] == "order")
        # Physical tables preserved; CRUD aggregated from both areas.
        self.assertEqual(order["physical_tables"], ["orders", "order_items"])
        by_area = {e["area_id"]: e["ops"] for e in order["crud_by_area"]}
        self.assertEqual(by_area, {"sales": "CRU", "admin": "RUD"})
        self.assertEqual(sorted(order["related_areas"]), ["admin", "sales"])

    def test_merge_drops_dangling_area_refs(self):
        from dramaturgy.commands.merge_maps import merge

        class _UI:
            def t(self, *a, **k):
                return ""
        # 'a' references a child/related area that was never created.
        maps = [{"content_lang": "ja", "system": {"name": "S"},
                 "areas": [
                     {"id": "a", "name": "A", "concepts": [], "concept_crud": [],
                      "child_area_ids": ["ghost", "b"],
                      "related_area_ids": ["nope"], "parent_area_id": "missing"},
                     {"id": "b", "name": "B", "concepts": [], "concept_crud": [],
                      "child_area_ids": [], "related_area_ids": []}],
                 "concepts": [], "actors": [], "flows": []}]
        merged, _ = merge(maps, _UI())
        a = next(x for x in merged["areas"] if x["id"] == "a")
        # Only real ids survive; dangling ones are dropped and reported.
        self.assertEqual(a["child_area_ids"], ["b"])
        self.assertEqual(a["related_area_ids"], [])
        self.assertIsNone(a["parent_area_id"])
        dropped = merged["merge_report"]["dropped_area_refs"]
        self.assertIn(["a", "child_area_ids", "ghost"], dropped)
        self.assertIn(["a", "related_area_ids", "nope"], dropped)
        self.assertIn(["a", "parent_area_id", "missing"], dropped)

    def test_crud_table_rows_and_jump_links(self):
        from dramaturgy.commands.merge_maps import merge
        from dramaturgy.commands.render_html import render_html

        class _UI:
            def t(self, *a, **k):
                return ""
        merged, _ = merge(list(self._two_area_maps()), _UI())
        html = render_html(merged, "ja")
        crud = html.split('id="crud"')[1].split("</section>")[0]
        # One row per (area, concept) pairing, each carrying sort indexes.
        self.assertEqual(crud.count('class="crud-row"'), 3)
        self.assertIn("data-aorder=", crud)
        self.assertIn("data-corder=", crud)
        # Subtle jump links to the area and concept sections.
        self.assertIn('href="#area-sales"', crud)
        self.assertIn('href="#concept-order"', crud)
        self.assertIn('class="jump"', crud)
        # Both jump targets must actually exist as anchors in the document.
        self.assertIn('id="area-sales"', html)
        self.assertIn('id="concept-order"', html)
        # Filters are searchable multi-select comboboxes (checkbox options).
        self.assertEqual(crud.count('class="ms"'), 2)
        self.assertIn('class="ms-search"', crud)
        self.assertIn('class="ms-opt"', crud)

    def test_render_shows_boxes_concepts_and_dual_crud(self):
        from dramaturgy.commands.merge_maps import merge
        from dramaturgy.commands.render_html import render_html

        class _UI:
            def t(self, *a, **k):
                return ""

        merged, _ = merge(list(self._two_area_maps()), _UI())
        html = render_html(merged, "ja")
        # No overview; areas are expandable boxes.
        self.assertNotIn('id="overview"', html)
        self.assertEqual(html.count('<details class="box"'), 2)
        # Concept-tables section shows physical tables.
        self.assertIn("orders", html)
        self.assertIn("order_items", html)
        # CRUD: a single sortable/filterable table of area×concept rows.
        self.assertIn('id="crud-sort"', html)
        self.assertIn('id="crud-filter-area"', html)
        self.assertIn('id="crud-filter-concept"', html)
        self.assertIn('class="crud-row"', html)


class ClassificationComponentTests(unittest.TestCase):
    """Classifications (enumerations) and components (infrastructure) are
    distinct from concept data and from business actors."""

    class _UI:
        def t(self, *a, **k):
            return ""

    def _map(self):
        return {
            "content_lang": "ja", "system": {"name": "S"},
            "areas": [{"id": "sales", "name": "販売", "concepts": ["order"],
                       "concept_crud": [], "related_area_ids": [],
                       "child_area_ids": []}],
            "concepts": [{"id": "order", "name": "注文", "kind": "entity",
                          "physical_tables": ["orders"]}],
            "actors": [
                {"id": "visitor", "name": "来場者", "category": "person",
                 "description": "d", "actions": []},
                {"id": "pay", "name": "決済代行", "category": "system",
                 "description": "GMO", "actions": []}],
            "classifications": [
                {"id": "point_method", "name": "ポイント方式",
                 "description": "付与/利用", "concept_id": "order",
                 "values": [{"code": "GIVE", "label": "付与"}]},
                {"id": "mail_kind", "name": "メール種別",
                 "description": "前提区分", "concept_id": None,
                 "values": [{"code": "A", "label": "案内"}]}],
            "components": [
                {"id": "lb", "name": "ロードバランサ", "kind": "infrastructure",
                 "description": "LB", "code_refs": ["infra/lb.tf"]}],
            "flows": []}

    def test_merge_keeps_classifications_and_components(self):
        from dramaturgy.commands.merge_maps import merge
        merged, _ = merge([self._map()], self._UI())
        self.assertEqual(len(merged["classifications"]), 2)
        self.assertEqual(len(merged["components"]), 1)

    def test_render_separates_them(self):
        from dramaturgy.commands.merge_maps import merge
        from dramaturgy.commands.render_html import render_html
        merged, _ = merge([self._map()], self._UI())
        html = render_html(merged, "ja")
        # Distinct sections + nav.
        self.assertIn('id="classifications"', html)
        self.assertIn('id="components"', html)
        # Classification value shown; concept link + premises grouping.
        self.assertIn("GIVE", html)
        self.assertIn('href="#concept-order"', html)
        # Actor grouping by category, and components carry their own pins.
        self.assertIn('data-rv-type="classification"', html)
        self.assertIn('data-rv-type="component"', html)

    def test_classifications_reviewable(self):
        import tempfile, json as _json
        from dramaturgy.server.api import Api
        with tempfile.TemporaryDirectory() as d:
            api = Api(d)
            # Findings auto-run; give a harmless spawn so no real claude runs.
            api.spawn = lambda argv: _NoopProc()
            api.put_artifact("meaning-map.json", self._map())
            targets = api.list_review_targets()[1]
            self.assertIn("classifications", targets)
            self.assertIn("components", targets)
            st, f = api.create_finding({
                "target_type": "classification", "target_id": "point_method",
                "kind": "reframe", "comment": "値を増やす"})
            self.assertEqual(st, 201)
            # It auto-runs; wait so the worker isn't writing during cleanup.
            import time as _time
            for _ in range(200):
                cur = next(x for x in api.list_findings()[1]["findings"]
                           if x["id"] == f["id"])
                if cur["status"] in ("done", "error"):
                    break
                _time.sleep(0.02)


class OverviewFlowTests(unittest.TestCase):
    """An area's overview_flow renders as a swimlane (lanes = actors)."""

    def test_swimlane_rendered_in_area(self):
        from dramaturgy.commands.render_html import render_html
        mm = {
            "content_lang": "ja", "system": {"name": "S"},
            "areas": [{"id": "sales", "name": "販売", "one_liner": "x",
                       "concepts": [], "concept_crud": [],
                       "related_area_ids": [], "child_area_ids": [],
                       "overview_flow": {
                           "title": "購入の流れ",
                           "lanes": ["visitor", "system"],
                           "steps": [
                               {"lane": "visitor", "label": "申込"},
                               {"lane": "system", "label": "発券"}]}}],
            "concepts": [], "classifications": [], "components": [],
            "actors": [{"id": "visitor", "name": "来場者", "category": "person"},
                       {"id": "system", "name": "システム", "category": "system"}],
            "flows": []}
        html = render_html(mm, "ja")
        area = html.split('id="area-sales"')[1].split("</details>")[0]
        self.assertIn('class="swimlane"', area)
        # Lanes labeled by actor name, steps numbered, reviewable.
        self.assertIn("来場者", area)
        self.assertIn("申込", area)
        self.assertIn('class="sl-n">1<', area)
        self.assertIn('data-rv-field="overview_flow"', area)
        # Lane headers carry a person/system icon before each actor name.
        head = area[area.index('class="sl-head"'):area.index('class="sl-row"')]
        self.assertIn('actor-icon person', head)
        self.assertIn('actor-icon sys', head)
        self.assertEqual(head.count("<svg"), 2)

    def test_no_flow_no_swimlane(self):
        from dramaturgy.commands.render_html import render_html
        mm = {"content_lang": "ja", "system": {"name": "S"},
              "areas": [{"id": "a", "name": "A", "concepts": [],
                         "concept_crud": [], "related_area_ids": [],
                         "child_area_ids": []}],
              "concepts": [], "classifications": [], "components": [],
              "actors": [], "flows": []}
        html = render_html(mm, "ja")
        self.assertNotIn('class="swimlane"', html)

    def test_unrelated_use_cases_split_by_divider(self):
        from dramaturgy.commands.render_html import render_html
        mm = {
            "content_lang": "ja", "system": {"name": "S"},
            "areas": [{"id": "ops", "name": "運用", "one_liner": "x",
                       "concepts": [], "concept_crud": [],
                       "related_area_ids": [], "child_area_ids": [],
                       "overview_flow": {
                           "lanes": ["admin", "system"],
                           "steps": [
                               {"lane": "admin", "label": "申請",
                                "use_case": "マスタ申請承認"},
                               {"lane": "system", "label": "反映",
                                "use_case": "マスタ申請承認"},
                               {"lane": "system", "label": "実行",
                                "use_case": "バッチ監視"},
                               {"lane": "admin", "label": "対応",
                                "use_case": "バッチ監視"}]}}],
            "concepts": [], "classifications": [], "components": [],
            "actors": [{"id": "admin", "name": "管理者", "category": "person"},
                       {"id": "system", "name": "システム", "category": "system"}],
            "flows": []}
        html = render_html(mm, "ja")
        area = html.split('id="area-ops"')[1].split("</details>")[0]
        # One divider per use case, named, with per-use-case numbering (1,2,1,2).
        self.assertEqual(area.count('class="sl-divider"'), 2)
        self.assertIn("マスタ申請承認", area)
        self.assertIn("バッチ監視", area)
        nums = [s.split("<")[0] for s in area.split('class="sl-n">')[1:]]
        self.assertEqual(nums, ["1", "2", "1", "2"])

    def test_area_actors_show_display_name_not_id(self):
        from dramaturgy.commands.render_html import render_html
        mm = {
            "content_lang": "ja", "system": {"name": "S"},
            "areas": [{"id": "ops", "name": "運用", "concepts": [],
                       "concept_crud": [], "related_area_ids": [],
                       "child_area_ids": [],
                       "actors": [{"actor_id": "operator", "actions": ["設定"]}]}],
            "concepts": [], "classifications": [], "components": [],
            "actors": [{"id": "operator", "name": "営業/運用担当",
                        "category": "person"}],
            "flows": []}
        html = render_html(mm, "ja")
        area = html.split('id="area-ops"')[1].split("</details>")[0]
        self.assertIn("<b>営業/運用担当</b>", area)   # display name
        self.assertNotIn("<b>operator</b>", area)     # not the bare id
        # The review pin still scopes to the actor id.
        self.assertIn('data-rv-field="actor:operator"', area)

    def test_related_areas_show_name_not_id(self):
        from dramaturgy.commands.render_html import render_html
        mm = {
            "content_lang": "ja", "system": {"name": "S"},
            "areas": [
                {"id": "sales", "name": "販売", "concepts": [],
                 "concept_crud": [], "child_area_ids": [],
                 "related_area_ids": ["payment-settlement"]},
                {"id": "payment-settlement", "name": "決済・精算",
                 "concepts": [], "concept_crud": [], "related_area_ids": [],
                 "child_area_ids": []}],
            "concepts": [], "classifications": [], "components": [],
            "actors": [], "flows": []}
        html = render_html(mm, "ja")
        card = html.split('id="area-sales"')[1].split("</details>")[0]
        # Related area shown by name, linked — not the raw id.
        self.assertIn("決済・精算", card)
        self.assertNotIn(">payment-settlement<", card)
        self.assertIn('href="#area-payment-settlement"', card)

    def test_child_area_nested_inside_parent_with_banner(self):
        # A child area (parent_area_id resolves to a real area) renders nested
        # inside the parent's box, under the "sub-areas" section, and carries a
        # banner naming the parent it details — making the parent→child
        # "detailing" relationship structurally obvious.
        from dramaturgy.commands.render_html import render_html
        mm = {
            "content_lang": "ja", "system": {"name": "S"},
            "areas": [
                {"id": "sales", "name": "販売", "concepts": [],
                 "concept_crud": [], "related_area_ids": [],
                 "child_area_ids": ["sales.payment"]},
                {"id": "sales.payment", "name": "決済", "concepts": [],
                 "concept_crud": [], "related_area_ids": [],
                 "parent_area_id": "sales", "child_area_ids": []}],
            "concepts": [], "classifications": [], "components": [],
            "actors": [], "flows": []}
        html = render_html(mm, "ja")
        # The child box is nested inside the parent box (appears before the
        # parent's closing </details>, inside the sub-areas well).
        parent = html.split('id="area-sales"')[1]
        sub = parent.split('class="sub-areas"')[1]
        self.assertIn('id="area-sales.payment"', sub)
        # The child carries a banner that links up to the parent.
        child = html.split('id="area-sales.payment"')[1].split("</details>")[0]
        self.assertIn("parent-of", child)
        self.assertIn('href="#area-sales"', child)
        self.assertIn("販売", child)

    def test_orphan_area_with_dangling_parent_still_rendered(self):
        # An area whose parent_area_id points to a non-existent area must not
        # be hidden — it falls back to the top-level grid.
        from dramaturgy.commands.render_html import render_html
        mm = {
            "content_lang": "ja", "system": {"name": "S"},
            "areas": [
                {"id": "lonely", "name": "孤児", "concepts": [],
                 "concept_crud": [], "related_area_ids": [],
                 "parent_area_id": "ghost", "child_area_ids": []}],
            "concepts": [], "classifications": [], "components": [],
            "actors": [], "flows": []}
        html = render_html(mm, "ja")
        self.assertIn('id="area-lonely"', html)
        # No broken banner link to the missing parent.
        self.assertNotIn('href="#area-ghost"', html)

    def test_actor_action_shows_area_name_not_id(self):
        from dramaturgy.commands.render_html import render_html
        mm = {
            "content_lang": "ja", "system": {"name": "S"},
            "areas": [{"id": "admin-operation", "name": "運用管理",
                       "concepts": [], "concept_crud": [],
                       "related_area_ids": [], "child_area_ids": []}],
            "concepts": [], "classifications": [], "components": [],
            "actors": [{"id": "adm", "name": "管理者", "category": "person",
                        "actions": [{"area_id": "admin-operation",
                                     "action": "承認", "description": "d"}]}],
            "flows": []}
        html = render_html(mm, "ja")
        card = html.split('id="actor-adm"')[1].split("</div>")[0]
        # Area shown by its Japanese name, linked — not the raw id.
        self.assertIn("(運用管理)", card)
        self.assertNotIn("(admin-operation)", card)
        self.assertIn('href="#area-admin-operation"', card)


class ExportPartsTests(unittest.TestCase):
    """The partial-read derivatives: a small index + self-contained per-area
    and per-concept part files, regenerated from the canonical map."""

    def _mm(self):
        return {
            "content_lang": "ja",
            "system": {"name": "S", "purpose": "目的"},
            "actors": [{"id": "u", "name": "利用者", "category": "person"}],
            "areas": [
                {"id": "sales", "name": "販売", "one_liner": "売る",
                 "parent_area_id": None, "child_area_ids": [],
                 "related_area_ids": [],
                 "actors": [{"actor_id": "u", "actions": ["申込"]}],
                 "concept_crud": [{"concept_id": "order", "ops": "CRU"}]}],
            "concepts": [{"id": "order", "name": "注文",
                          "physical_tables": ["orders"], "kind": "entity",
                          "tags": ["transaction"],
                          "crud_by_area": [{"area_id": "sales", "ops": "CRU"}]}],
            "classifications": [{"id": "st", "name": "状態", "concept_id": "order",
                                 "values": [{"code": "1", "label": "新規"}]}],
            "components": [], "flows": []}

    def test_index_and_parts_written(self):
        from dramaturgy.commands.export_parts import export_parts
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            idx = export_parts(self._mm(), out)
            # Index lists areas/concepts with a part path + byte hint.
            self.assertEqual(idx["counts"]["areas"], 1)
            self.assertEqual(idx["system"]["purpose"], "目的")
            self.assertEqual(idx["areas"][0]["part"], "parts/areas/sales.json")
            self.assertIn("bytes", idx["areas"][0])
            self.assertTrue((out / "map-index.json").exists())
            self.assertTrue((out / "parts" / "areas" / "sales.json").exists())
            self.assertTrue((out / "parts" / "concepts" / "order.json").exists())
            self.assertTrue((out / "parts" / "README.md").exists())

    def test_area_part_is_self_contained(self):
        from dramaturgy.commands.export_parts import export_parts
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            export_parts(self._mm(), out)
            part = json.loads(
                (out / "parts" / "areas" / "sales.json").read_text("utf-8"))
            # Concept name + tables resolved inline; actor name resolved; the
            # classification detailing the concept is included.
            res = part["resolved"]
            self.assertEqual(res["concepts"][0]["name"], "注文")
            self.assertEqual(res["concepts"][0]["physical_tables"], ["orders"])
            self.assertEqual(res["actors"][0]["name"], "利用者")
            self.assertEqual(res["classifications"][0]["id"], "st")

    def test_stale_parts_removed_on_regen(self):
        from dramaturgy.commands.export_parts import export_parts
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            export_parts(self._mm(), out)
            # Regenerate from a map without the 'order' concept: its stale part
            # file must be gone.
            mm2 = self._mm()
            mm2["concepts"] = []
            mm2["areas"][0]["concept_crud"] = []
            export_parts(mm2, out)
            self.assertFalse(
                (out / "parts" / "concepts" / "order.json").exists())


class SourceProvenanceTests(unittest.TestCase):
    """A provenance note (repo link + analyzed commit) is shown only for
    public sources, where public is decided by a LICENSE file at analysis."""

    def _mm(self, source):
        return {"content_lang": "ja", "system": {"name": "S", "source": source},
                "areas": [], "concepts": [], "classifications": [],
                "components": [], "actors": [], "flows": []}

    def test_normalize_remote(self):
        from dramaturgy.commands.analyze_repo import _normalize_remote
        self.assertEqual(_normalize_remote("git@github.com:o/r.git"),
                         "https://github.com/o/r")
        self.assertEqual(_normalize_remote("https://github.com/o/r.git"),
                         "https://github.com/o/r")
        self.assertEqual(_normalize_remote("ssh://git@gitlab.com/o/r.git"),
                         "https://gitlab.com/o/r")
        self.assertIsNone(_normalize_remote(None))

    def test_license_decides_public(self):
        from dramaturgy.commands.analyze_repo import _source_meta
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.assertFalse(_source_meta(root)["public"])
            (root / "LICENSE").write_text("MIT", encoding="utf-8")
            self.assertTrue(_source_meta(root)["public"])

    def test_note_shown_for_public_with_links(self):
        from dramaturgy.commands.render_html import render_html
        html = render_html(self._mm({
            "public": True, "repo_url": "https://github.com/o/r",
            "commit": "abc123def4567", "commit_short": "abc123def456"}), "ja")
        note = html[html.index("<main>"):html.index("</main>")]
        self.assertIn('class="source-note"', note)
        # Repo links to the analyzed revision; commit links to that commit.
        self.assertIn('href="https://github.com/o/r/tree/abc123def4567"', note)
        self.assertIn('href="https://github.com/o/r/commit/abc123def4567"', note)
        self.assertIn("abc123def456", note)

    def test_note_omitted_for_private(self):
        from dramaturgy.commands.render_html import render_html
        html = render_html(self._mm({
            "public": False, "repo_url": "https://github.com/o/r",
            "commit": "abc"}), "ja")
        self.assertNotIn('class="source-note"', html)

    def test_note_omitted_when_no_source(self):
        from dramaturgy.commands.render_html import render_html
        mm = {"content_lang": "ja", "system": {"name": "S"}, "areas": [],
              "concepts": [], "classifications": [], "components": [],
              "actors": [], "flows": []}
        self.assertNotIn('class="source-note"', render_html(mm, "ja"))


class DeveloperModeTests(unittest.TestCase):
    """Developer-facing items (code refs / APIs / screens / validation) are
    emitted but marked dev-only, so the app shell can hide them for
    non-developers via CSS without a re-render."""

    def _html(self):
        from dramaturgy.commands.render_html import render_html
        mm = {
            "content_lang": "ja", "system": {"name": "S"},
            "areas": [{"id": "a1", "name": "領域1", "one_liner": "x",
                       "concept_crud": [], "related_area_ids": [],
                       "child_area_ids": [], "apis": ["/api/x"],
                       "screens": ["S1"], "code_refs": ["app/x.rb"]}],
            "concepts": [], "classifications": [], "components": [],
            "actors": [], "flows": [], "validations": ["v1"]}
        return render_html(mm, "ja")

    def test_dev_rows_and_validation_marked_dev_only(self):
        html = self._html()
        # The validation section and its nav link are developer-only.
        self.assertIn('id="validation" class="dev-only"', html)
        self.assertIn('<a href="#validation" class="dev-only"', html)
        # Area dev rows (APIs / screens / code refs) are wrapped dev-only.
        card = html.split('id="area-a1"')[1].split("</details>")[0]
        self.assertIn('<dt class="dev-only">関連API', card)
        self.assertIn('<dt class="dev-only">関連コード', card)
        # Non-dev rows are not wrapped.
        self.assertIn('<dt>目的', card)

    def test_dev_mode_css_and_iframe_toggle_present(self):
        html = self._html()
        # Hidden by default; revealed only when <body> has the dev class.
        self.assertIn(".dev-only { display: none; }", html)
        self.assertIn("body.dev .dev-only { display: revert; }", html)
        # The iframe self-initializes from ?dev=1 and listens for the shell's
        # toggle message.
        self.assertIn("dramaturgy-shell", html)
        self.assertIn("dev=1", html)


class ViewStatePersistenceTests(unittest.TestCase):
    """The app shell reloads the preview iframe after a finding runs. The
    rendered page must remember expanded boxes + scroll position across that
    reload (persisted in sessionStorage, restored on load)."""

    def test_view_state_script_present(self):
        from dramaturgy.commands.render_html import render_html
        mm = {"content_lang": "ja", "system": {"name": "S"},
              "areas": [{"id": "a1", "name": "領域1", "one_liner": "x",
                         "concept_crud": [], "related_area_ids": [],
                         "child_area_ids": []}],
              "concepts": [], "classifications": [], "components": [],
              "actors": [], "flows": []}
        html = render_html(mm, "ja")
        # Persists to sessionStorage, keyed by path (stable across the
        # cache-busting query), tracking open boxes and scroll position.
        self.assertIn("sessionStorage", html)
        self.assertIn("dramaturgy.viewstate", html)
        self.assertIn("location.pathname", html)
        self.assertIn("state.open", html)
        self.assertIn("scrollY", html)
        # Restores by reopening <details> ids and scrolling back.
        self.assertIn("addEventListener('toggle'", html)
        self.assertIn("window.scrollTo", html)


class SystemPurposeTests(unittest.TestCase):
    """The system's overall purpose leads the document (before actors) when
    present, and the whole section is omitted when absent."""

    def _mm(self, purpose=None):
        system = {"name": "My System"}
        if purpose is not None:
            system["purpose"] = purpose
        return {"content_lang": "ja", "system": system,
                "areas": [{"id": "a", "name": "A", "concept_crud": [],
                           "related_area_ids": [], "child_area_ids": []}],
                "concepts": [], "classifications": [], "components": [],
                "actors": [], "flows": []}

    def test_purpose_section_before_actors(self):
        from dramaturgy.commands.render_html import render_html
        html = render_html(
            self._mm("利用者がチケットを買うためのシステム。\n会計が中核。"), "ja")
        self.assertIn('id="purpose"', html)
        self.assertIn('href="#purpose"', html)         # nav link
        self.assertLess(html.index('id="purpose"'), html.index('id="actors"'))
        # Line breaks become separate paragraphs; the system name is shown.
        self.assertIn("会計が中核", html)
        self.assertIn("My System", html)

    def test_no_purpose_no_section(self):
        from dramaturgy.commands.render_html import render_html
        html = render_html(self._mm(), "ja")
        self.assertNotIn('id="purpose"', html)
        self.assertNotIn('href="#purpose"', html)

    def test_purpose_commentable_in_app_not_export(self):
        from dramaturgy.commands.render_html import render_html
        mm = self._mm("目的の文章。")
        self.assertIn('data-rv-type="system"', render_html(mm, "ja"))
        self.assertNotIn('data-rv-type="system"',
                         render_html(mm, "ja", export=True))


class ExportDocumentTests(unittest.TestCase):
    """The export build is a standalone shareable document: same layout/data,
    but no review pins or app coupling, and a single self-contained file."""

    def _mm(self):
        return {
            "content_lang": "ja", "system": {"name": "S"},
            "areas": [{"id": "a1", "name": "領域1", "one_liner": "x",
                       "concept_crud": [{"concept_id": "c1", "ops": "CR"}],
                       "related_area_ids": [], "child_area_ids": [],
                       "apis": ["/api/x"], "code_refs": ["app/x.rb"]}],
            "concepts": [{"id": "c1", "name": "概念1",
                          "physical_tables": ["t"], "tags": [],
                          "crud_by_area": [{"area_id": "a1", "ops": "CR"}]}],
            "classifications": [], "components": [],
            "actors": [{"id": "u", "name": "利用者", "category": "person"}],
            "flows": [], "validations": ["v1"]}

    def test_export_strips_review_and_app_coupling(self):
        from dramaturgy.commands.render_html import render_html
        html = render_html(self._mm(), "ja", export=True)
        # No review pins, no pin/shell postMessage wiring, no app viewstate.
        self.assertNotIn('class="rv-pin"', html)
        self.assertNotIn("dramaturgy-review", html)
        self.assertNotIn("dramaturgy-shell", html)
        self.assertNotIn("dramaturgy.viewstate", html)
        # Self-contained: inline CSS/JS, no external assets.
        self.assertNotIn("<link", html)
        self.assertNotIn("<script src", html)
        # The content itself is preserved.
        self.assertIn("領域1", html)
        self.assertIn("概念1", html)

    def test_export_has_self_contained_dev_toggle(self):
        from dramaturgy.commands.render_html import render_html
        html = render_html(self._mm(), "ja", export=True)
        # Its own developer-details toggle (the shareable file has no app shell).
        self.assertIn('id="dev-toggle"', html)
        self.assertIn("dramaturgy.export.dev", html)
        # Dev items still present but gated by the dev-only mechanism.
        self.assertIn('class="dev-only"', html)
        self.assertIn("body.dev .dev-only", html)

    def test_export_keeps_interactive_crud_and_tag_filter(self):
        from dramaturgy.commands.render_html import render_html
        html = render_html(self._mm(), "ja", export=True)
        # The shared interactive behaviour (CRUD sort/filter + combobox) stays.
        self.assertIn("crud-tbody", html)
        self.assertIn("setupMultiSelect", html)

    def test_default_render_unaffected_and_no_mode_leak(self):
        from dramaturgy.commands.render_html import render_html
        # An export render must not leak its mode into a later normal render.
        render_html(self._mm(), "ja", export=True)
        html = render_html(self._mm(), "ja")
        self.assertIn('class="rv-pin"', html)
        self.assertNotIn('id="dev-toggle"', html)


class SourceHintsRobustnessTests(unittest.TestCase):
    """source_hints may arrive as a dict (normal), a bare list/string, or be
    missing — Claude's output varies. match_files must tolerate all."""

    def test_match_files_tolerates_hint_shapes(self):
        from dramaturgy.common.area_match import match_files
        si = {"files": [{"path": "app/models/order.rb", "lines": 5},
                        {"path": "lib/util.rb", "lines": 3}]}

        def paths(area):
            return [f["path"] for f in match_files(area, si)]

        # dict (normal)
        self.assertEqual(
            paths({"source_hints": {"directories": ["models"]}}),
            ["app/models/order.rb"])
        # bare list -> treated as keywords (the reported crash)
        self.assertEqual(sorted(paths({"source_hints": ["order", "util"]})),
                         ["app/models/order.rb", "lib/util.rb"])
        # bare string
        self.assertEqual(paths({"source_hints": "order"}),
                         ["app/models/order.rb"])
        # missing / wrong-typed elements
        self.assertEqual(paths({"id": "x"}), [])
        self.assertEqual(paths({"source_hints": {"keywords": [123, "order", None]}}),
                         ["app/models/order.rb"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

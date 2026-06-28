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

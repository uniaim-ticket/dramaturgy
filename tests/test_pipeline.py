"""End-to-end and unit tests for the meaning-map toolchain.

Run with: ``python -m pytest tests/`` or ``python tests/test_pipeline.py``.
Uses only the standard library (unittest) so it runs without extra deps.
Each test drives the CLIs against a temporary workspace.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "tools" / "meaning_map"
sys.path.insert(0, str(PKG))

from common.config import Config, load_config, save_config  # noqa: E402
from common.i18n import Catalog, validate_catalogs  # noqa: E402
from common.prompts import load_prompt  # noqa: E402
import analyze_repo  # noqa: E402
import analyze_schema  # noqa: E402
import build_area_pack  # noqa: E402
import merge_maps  # noqa: E402
import render_html  # noqa: E402
import setup as setup_tool  # noqa: E402
import validate_map  # noqa: E402

SUPPORTED = ("ja", "en")


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


class PipelineTests(unittest.TestCase):
    def test_full_pipeline(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _make_sample_repo(root)
            ws = root / ".meaning-map"

            self.assertEqual(0, setup_tool.main([
                "--no-input", "--ui-lang", "ja", "--content-lang", "ja",
                "--project-name", "Sample", "--repo-root", d]))
            self.assertEqual(0, analyze_repo.main(["--repo-root", d]))
            self.assertEqual(0, analyze_schema.main(["--repo-root", d]))

            schema = json.loads((ws / "schema-index.json").read_text())
            names = {t["name"] for t in schema["tables"]}
            self.assertEqual(names, {"events", "tickets"})

            # Author a minimal area-tree + area map.
            (ws / "area-tree.json").write_text(json.dumps({
                "content_lang": "ja",
                "system": {"name": "Sample", "summary": "s"},
                "areas": [{
                    "id": "sales", "name": "販売", "one_liner": "x",
                    "source_hints": {"tables": ["tickets"],
                                     "keywords": ["ticket"]},
                    "confidence": "high",
                }],
            }, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(0, build_area_pack.main([
                "--repo-root", d, "--area-id", "sales"]))

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

            self.assertEqual(0, merge_maps.main(["--repo-root", d, str(amap)]))
            self.assertEqual(0, validate_map.main(["--repo-root", d]))
            self.assertEqual(0, render_html.main(["--repo-root", d]))
            html = (ws / "meaning-map.html").read_text()
            self.assertIn("販売", html)
            self.assertIn('lang="ja"', html)

    def test_validate_detects_bad_table(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _make_sample_repo(root)
            ws = root / ".meaning-map"
            setup_tool.main(["--no-input", "--repo-root", d,
                             "--content-lang", "ja"])
            analyze_repo.main(["--repo-root", d])
            analyze_schema.main(["--repo-root", d])
            mm = {
                "content_lang": "ja",
                "system": {"name": "S", "summary": "",
                           "source_summary": {}},
                "actors": [], "concepts": [], "flows": [],
                "areas": [{"id": "a", "name": "A", "tables": ["ghost"],
                           "apis": [], "code_refs": [],
                           "related_area_ids": [], "child_area_ids": [],
                           "confidence": "high"}],
            }
            (ws / "meaning-map.json").write_text(
                json.dumps(mm, ensure_ascii=False), encoding="utf-8")
            # Non-zero exit because 'ghost' is not a known table.
            self.assertEqual(1, validate_map.main(["--repo-root", d]))

    def test_mixed_language_html(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ws = root / ".meaning-map"
            ws.mkdir(parents=True)
            save_config(Config(ui_lang="en", content_lang="ja", repo_root=d), d)
            (ws / "meaning-map.json").write_text(json.dumps({
                "content_lang": "ja",
                "system": {"name": "S", "summary": "概要",
                           "source_summary": {}},
                "actors": [], "concepts": [], "flows": [], "areas": [],
            }, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(0, render_html.main(["--repo-root", d]))
            html = (ws / "meaning-map.html").read_text()
            # English chrome, content language note present, lang=ja.
            self.assertIn("Overview", html)
            self.assertIn("Content language: ja", html)
            self.assertIn('lang="ja"', html)


if __name__ == "__main__":
    unittest.main(verbosity=2)

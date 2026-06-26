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
            self.assertEqual(0, dra(["analyze-schema", "--repo-root", d]))

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

    def test_validate_detects_bad_table(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _make_sample_repo(root)
            ws = root / WORKSPACE
            dra(["setup", "--no-input", "--repo-root", d,
                 "--content-lang", "ja"])
            dra(["analyze-repo", "--repo-root", d])
            dra(["analyze-schema", "--repo-root", d])
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
            self.assertIn("Overview", html)
            self.assertIn("Content language: ja", html)
            self.assertIn('lang="ja"', html)


if __name__ == "__main__":
    unittest.main(verbosity=2)

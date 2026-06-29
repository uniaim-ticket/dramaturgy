"""Tests for the web server: API layer, HTTP routing, and the Claude runner.

The Claude Code subprocess is mocked (a fake spawn that emits stream-json
and writes the artifact file), so these run without a real ``claude``
binary. Stdlib unittest only.
"""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dramaturgy.server.api import Api  # noqa: E402
from dramaturgy.server.http import serve  # noqa: E402
from dramaturgy.server import claude_runner  # noqa: E402
from dramaturgy.server.jobs import Job  # noqa: E402


def _sample_repo(root: Path) -> None:
    (root / "app").mkdir(parents=True)
    (root / "app" / "t.rb").write_text(
        "class T\n  get '/api/tickets/apply'\nend\n", encoding="utf-8")
    (root / "schema.sql").write_text(
        "CREATE TABLE tickets (id INT, status VARCHAR(20));\n", encoding="utf-8")


class _FakeProc:
    """Minimal Popen stand-in: yields stdout lines, then writes side files."""

    def __init__(self, lines, writes):
        self._lines = lines
        self._writes = writes

    @property
    def stdout(self):
        for ln in self._lines:
            yield ln + "\n"
        for path, content in self._writes:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(content, encoding="utf-8")

    def wait(self):
        return 0


def _fake_spawn_for(ws: Path, area_id: str):
    target = ws / "area-maps" / f"{area_id}.json"
    card = {
        "content_lang": "ja",
        "system": {"name": "S", "source_summary": {}},
        "actors": [], "concepts": [], "flows": [],
        "areas": [{
            "id": area_id, "name": "販売", "one_liner": "x", "tables": [],
            "apis": [], "code_refs": [], "related_area_ids": [],
            "child_area_ids": [], "confidence": "high", "crud_summary": {},
        }],
    }
    lines = [
        json.dumps({"type": "system", "subtype": "init", "session_id": "s1"}),
        json.dumps({"type": "assistant",
                    "message": {"content": [{"type": "tool_use", "name": "Write"}]}}),
        json.dumps({"type": "result", "is_error": False, "result": "ok",
                    "session_id": "s1"}),
    ]

    def spawn(argv):
        return _FakeProc(lines, [(target, json.dumps(card, ensure_ascii=False))])

    return spawn


class InitInstructionsTests(unittest.TestCase):
    def test_persist_and_inject_into_prompts(self):
        from dramaturgy.server.prompt_jobs import area_tree_prompt
        with tempfile.TemporaryDirectory() as d:
            _sample_repo(Path(d))
            api = Api(d)
            api.analyze({})
            self.assertEqual(api.get_init_instructions()[1]["instructions"], "")
            api.put_init_instructions(
                {"instructions": "マスタ・トランザクションの区分をタグ付けして"})
            # Survives a fresh Api instance (same repo) → reused.
            api2 = Api(d)
            text = api2.get_init_instructions()[1]["instructions"]
            self.assertIn("マスタ・トランザクション", text)
            # Injected into the generation prompt as a labeled block.
            prompt = area_tree_prompt(d, "ja", "S",
                                      extra_instructions=text)
            self.assertIn("追加指示", prompt)
            self.assertIn("マスタ・トランザクション", prompt)
            # No block when empty.
            self.assertNotIn("追加指示", area_tree_prompt(d, "ja", "S", ""))

    def test_effort_default_persist_and_validate(self):
        with tempfile.TemporaryDirectory() as d:
            api = Api(d)
            # Defaults to xhigh until set.
            self.assertEqual(api.get_init_instructions()[1]["effort"], "xhigh")
            api.put_init_instructions({"instructions": "x", "effort": "high"})
            # Persists across a fresh Api instance (same repo).
            self.assertEqual(Api(d)._read_effort(), "high")
            # Invalid values are rejected and leave the saved value intact.
            code, _ = api.put_init_instructions(
                {"instructions": "x", "effort": "bogus"})
            self.assertEqual(code, 400)
            self.assertEqual(api._read_effort(), "high")


class ApiTests(unittest.TestCase):
    def test_analyze_and_writeback(self):
        with tempfile.TemporaryDirectory() as d:
            _sample_repo(Path(d))
            api = Api(d)
            _, res = api.analyze({})
            self.assertEqual(res["files"], 2)  # t.rb + schema.sql
            # analyze is inventory-only now: no semantic table extraction.
            self.assertNotIn("tables", res)
            self.assertIn("directories", res)

            tree = {"content_lang": "ja", "system": {"name": "S"},
                    "areas": [{"id": "sales", "name": "販売", "confidence": "high"}]}
            self.assertEqual(200, api.put_artifact("area-tree.json", tree)[0])
            self.assertEqual("ja", api.get_artifact("area-tree.json")[1]["content_lang"])

    def test_merge_attaches_source_provenance(self):
        with tempfile.TemporaryDirectory() as d:
            _sample_repo(Path(d))
            api = Api(d)
            # A source index carrying provenance (as analyze would produce).
            api.put_artifact("source-index.json", {
                "files": [], "source_meta": {
                    "public": True, "repo_url": "https://github.com/o/r",
                    "commit": "abc123", "commit_short": "abc123"}})
            api.put_artifact("area-maps/sales.json", {
                "content_lang": "ja", "system": {"name": "S"},
                "actors": [], "concepts": [], "flows": [],
                "areas": [{"id": "sales", "name": "販売", "concept_crud": [],
                           "related_area_ids": [], "child_area_ids": []}]})
            self.assertEqual(200, api.merge({})[0])
            mm = api.get_artifact("meaning-map.json")[1]
            self.assertEqual(mm["system"]["source"]["repo_url"],
                             "https://github.com/o/r")
            self.assertTrue(mm["system"]["source"]["public"])

    def test_patch_area_writes_back(self):
        with tempfile.TemporaryDirectory() as d:
            api = Api(d)
            mm = {"content_lang": "ja",
                  "system": {"name": "S", "source_summary": {}},
                  "actors": [], "concepts": [], "flows": [],
                  "areas": [{"id": "sales", "name": "販売", "tables": [],
                             "apis": [], "code_refs": [], "related_area_ids": [],
                             "child_area_ids": [], "confidence": "high",
                             "crud_summary": {}}]}
            api.put_artifact("meaning-map.json", mm)
            status, area = api.patch_area("sales", {"one_liner": "申込から"})
            self.assertEqual(status, 200)
            self.assertEqual(area["one_liner"], "申込から")
            # Persisted to disk.
            on_disk = api.get_artifact("meaning-map.json")[1]
            self.assertEqual(on_disk["areas"][0]["one_liner"], "申込から")

    def test_validate_and_render(self):
        with tempfile.TemporaryDirectory() as d:
            _sample_repo(Path(d))
            api = Api(d)
            api.analyze({})
            mm = {"content_lang": "ja",
                  "system": {"name": "S", "summary": "", "source_summary": {}},
                  "actors": [], "concepts": [], "flows": [],
                  "areas": [{"id": "sales", "name": "販売", "tables": ["tickets"],
                             "apis": [], "code_refs": [], "related_area_ids": [],
                             "child_area_ids": [], "confidence": "high",
                             "crud_summary": {}}]}
            api.put_artifact("meaning-map.json", mm)
            self.assertTrue(api.validate()[1]["ok"])
            self.assertEqual(200, api.render()[0])
            self.assertIn("販売", api.render_html_text())
            # The export build holds the same content but drops the review pins.
            exported = api.export_html_text()
            self.assertIn("販売", exported)
            self.assertNotIn('class="rv-pin"', exported)
            self.assertIn('id="dev-toggle"', exported)

    def test_validate_reports_missing_code_ref(self):
        # Tables/APIs are no longer machine-checkable (Claude discovers them
        # by reading source). What stays reliably checkable is code_refs:
        # a reference to a file that does not exist must fail validation.
        with tempfile.TemporaryDirectory() as d:
            _sample_repo(Path(d))
            api = Api(d)
            api.analyze({})
            mm = {"content_lang": "ja",
                  "system": {"name": "S", "summary": "", "source_summary": {}},
                  "actors": [], "concepts": [], "flows": [],
                  "areas": [{"id": "a", "name": "A", "tables": ["whatever"],
                             "apis": [], "code_refs": ["does/not/exist.rb"],
                             "related_area_ids": [], "child_area_ids": [],
                             "confidence": "high", "crud_summary": {}}]}
            api.put_artifact("meaning-map.json", mm)
            self.assertFalse(api.validate()[1]["ok"])


class ClaudeJobTests(unittest.TestCase):
    def test_area_card_job_writes_file(self):
        with tempfile.TemporaryDirectory() as d:
            _sample_repo(Path(d))
            api = Api(d)
            api.analyze({})
            api.put_artifact("area-tree.json", {
                "content_lang": "ja", "system": {"name": "S"},
                "areas": [{"id": "sales", "name": "販売",
                           "source_hints": {"keywords": ["ticket"]},
                           "confidence": "high"}]})
            api.spawn = _fake_spawn_for(api.ws, "sales")

            status, res = api.start_area_card_job({"area_id": "sales"})
            self.assertEqual(status, 202)
            job_id = res["job_id"]
            for _ in range(100):
                job = api.get_job(job_id)[1]
                if job["status"] in ("done", "error", "aborted"):
                    break
                time.sleep(0.02)
            self.assertEqual(job["status"], "done")
            self.assertEqual(job["session_id"], "s1")
            self.assertTrue((api.ws / "area-maps" / "sales.json").exists())
            # Merge picks up the Claude-written card.
            self.assertEqual(api.merge()[1]["areas"], 1)

    def test_init_pipeline_runs_end_to_end(self):
        import re
        with tempfile.TemporaryDirectory() as d:
            _sample_repo(Path(d))
            api = Api(d)
            ws = api.ws

            def pipeline_spawn(argv):
                prompt = argv[argv.index("-p") + 1]
                m = re.search(r'([^\s`]+area-maps[^\s`]*\.json)', prompt)
                if m:
                    path = m.group(1)
                    aid = Path(path).stem
                    card = {"content_lang": "ja",
                            "system": {"name": "S", "source_summary": {}},
                            "actors": [], "concepts": [], "flows": [],
                            "areas": [{"id": aid, "name": aid, "one_liner": "x",
                                       "tables": [], "apis": [], "code_refs": [],
                                       "related_area_ids": [], "child_area_ids": [],
                                       "confidence": "high", "crud_summary": {}}]}
                    writes = [(Path(path), json.dumps(card, ensure_ascii=False))]
                elif "意味地図のサマリ" in prompt:   # system purpose step
                    mm = json.loads((ws / "meaning-map.json").read_text("utf-8"))
                    mm.setdefault("system", {})["purpose"] = "テスト目的。"
                    writes = [(ws / "meaning-map.json",
                               json.dumps(mm, ensure_ascii=False))]
                else:
                    tree = {"content_lang": "ja", "system": {"name": "S"},
                            "areas": [{"id": "sales", "name": "販売",
                                       "source_hints": {"keywords": ["ticket"]},
                                       "confidence": "high"}]}
                    writes = [(ws / "area-tree.json",
                               json.dumps(tree, ensure_ascii=False))]
                lines = [
                    json.dumps({"type": "system", "subtype": "init",
                                "session_id": "s1"}),
                    json.dumps({"type": "result", "is_error": False,
                                "result": "ok", "session_id": "s1"}),
                ]
                return _FakeProc(lines, writes)

            api.spawn = pipeline_spawn
            # force=True so it runs even without a real claude binary present
            status, res = api.start_init_job({"force": True})
            self.assertEqual(status, 202)
            job_id = res["job_id"]
            for _ in range(300):
                job = api.get_job(job_id)[1]
                if job["status"] in ("done", "error", "aborted"):
                    break
                time.sleep(0.02)
            self.assertEqual(job["status"], "done", job.get("error"))
            self.assertTrue((ws / "area-tree.json").exists())
            self.assertTrue((ws / "area-maps" / "sales.json").exists())
            self.assertTrue((ws / "meaning-map.json").exists())
            self.assertTrue((ws / "meaning-map.html").exists())
            self.assertTrue(api.validate()[1]["ok"])
            # The final step writes an overall system purpose into the map.
            mm = json.loads((ws / "meaning-map.json").read_text("utf-8"))
            self.assertTrue(mm["system"].get("purpose"))

    def test_init_pipeline_subdivides_oversized_area(self):
        # The init pipeline has a subdivide review step: when an area warrants
        # child areas, Claude splits it in area-tree.json, the tree expands,
        # cards are generated for the new children, and the parent keeps its
        # child_area_ids in the merged map (overlaid from the tree).
        import re
        with tempfile.TemporaryDirectory() as d:
            _sample_repo(Path(d))
            api = Api(d)
            ws = api.ws

            def spawn(argv):
                prompt = argv[argv.index("-p") + 1]
                m = re.search(r'([^\s`]+area-maps[^\s`]*\.json)', prompt)
                if m:
                    # Area-card prompt: write a card for that area. Detect this
                    # first — the card prompt also mentions area-tree paths.
                    aid = Path(m.group(1)).stem
                    card = {"content_lang": "ja",
                            "system": {"name": "S", "source_summary": {}},
                            "actors": [], "concepts": [], "flows": [],
                            "areas": [{"id": aid, "name": aid, "one_liner": "x",
                                       "concept_crud": [], "related_area_ids": [],
                                       "child_area_ids": [], "confidence": "high"}]}
                    writes = [(Path(m.group(1)),
                               json.dumps(card, ensure_ascii=False))]
                elif "規模ヒント" in prompt:
                    # Subdivide review: split sales into two children (once).
                    tree = json.loads((ws / "area-tree.json").read_text("utf-8"))
                    sales = next(a for a in tree["areas"] if a["id"] == "sales")
                    if "child_area_ids" not in sales:
                        sales["child_area_ids"] = ["sales.apply", "sales.payment"]
                        tree["areas"] += [
                            {"id": "sales.apply", "name": "申込",
                             "parent_area_id": "sales",
                             "source_hints": {"keywords": ["ticket"]}},
                            {"id": "sales.payment", "name": "決済",
                             "parent_area_id": "sales",
                             "source_hints": {"keywords": ["ticket"]}}]
                    writes = [(ws / "area-tree.json",
                               json.dumps(tree, ensure_ascii=False))]
                elif "意味地図のサマリ" in prompt:   # system purpose step
                    mm = json.loads((ws / "meaning-map.json").read_text("utf-8"))
                    mm.setdefault("system", {})["purpose"] = "テスト目的。"
                    writes = [(ws / "meaning-map.json",
                               json.dumps(mm, ensure_ascii=False))]
                else:
                    # Initial area-tree generation: one flat area.
                    tree = {"content_lang": "ja", "system": {"name": "S"},
                            "areas": [{"id": "sales", "name": "販売",
                                       "source_hints": {"keywords": ["ticket"]},
                                       "confidence": "high"}]}
                    writes = [(ws / "area-tree.json",
                               json.dumps(tree, ensure_ascii=False))]
                lines = [
                    json.dumps({"type": "system", "subtype": "init",
                                "session_id": "s1"}),
                    json.dumps({"type": "result", "is_error": False,
                                "result": "ok", "session_id": "s1"}),
                ]
                return _FakeProc(lines, writes)

            api.spawn = spawn
            job_id = api.start_init_job({"force": True})[1]["job_id"]
            for _ in range(500):
                job = api.get_job(job_id)[1]
                if job["status"] in ("done", "error", "aborted"):
                    break
                time.sleep(0.02)
            self.assertEqual(job["status"], "done", job.get("error"))

            # Tree expanded to parent + 2 children.
            tree = json.loads((ws / "area-tree.json").read_text("utf-8"))
            ids = {a["id"] for a in tree["areas"]}
            self.assertEqual(ids, {"sales", "sales.apply", "sales.payment"})

            # Cards generated for every area, including the new children.
            for aid in ("sales", "sales.apply", "sales.payment"):
                self.assertTrue((ws / "area-maps" / f"{aid}.json").exists(), aid)

            # Merged map: parent carries the hierarchy (overlaid from the tree),
            # children point back at the parent, and validation passes.
            mm = json.loads((ws / "meaning-map.json").read_text("utf-8"))
            by_id = {a["id"]: a for a in mm["areas"]}
            self.assertEqual(sorted(by_id["sales"]["child_area_ids"]),
                             ["sales.apply", "sales.payment"])
            self.assertEqual(by_id["sales.apply"]["parent_area_id"], "sales")
            self.assertTrue(api.validate()[1]["ok"])

    def test_runner_reports_nonzero_exit(self):
        job = Job(id="j", kind="area_card", prompt="p")

        class FailProc:
            stdout = iter([])

            def wait(self):
                return 1

        claude_runner.run_job(job, ".", spawn=lambda argv: FailProc())
        self.assertEqual(job.status, "error")

    def test_build_argv_shape(self):
        argv = claude_runner.build_argv(
            "PROMPT", "/repo", resume_session="sess-1")
        self.assertIn("-p", argv)
        self.assertIn("--output-format", argv)
        self.assertIn("stream-json", argv)
        self.assertIn("--permission-mode", argv)
        self.assertIn("acceptEdits", argv)
        self.assertIn("--resume", argv)
        self.assertIn("sess-1", argv)
        # No effort flag unless requested.
        self.assertNotIn("--effort", argv)

    def test_build_argv_effort(self):
        argv = claude_runner.build_argv("P", "/repo", effort="xhigh")
        self.assertIn("--effort", argv)
        self.assertEqual(argv[argv.index("--effort") + 1], "xhigh")

    def test_retry_on_transient_then_success(self):
        # First attempt hits an API error; the retry succeeds. The wrapper
        # must not give up after the transient failure.
        job = Job(id="j", kind="area_card", prompt="p")
        attempts = {"n": 0}

        def spawn(argv):
            attempts["n"] += 1
            if attempts["n"] == 1:
                lines = [
                    json.dumps({"type": "system", "subtype": "init",
                                "session_id": "s1"}),
                    "API Error: unexpected error during processing",
                    json.dumps({"type": "result", "is_error": True,
                                "subtype": "error_during_execution",
                                "result": "API Error", "session_id": "s1"}),
                ]
            else:
                lines = [
                    json.dumps({"type": "system", "subtype": "init",
                                "session_id": "s1"}),
                    json.dumps({"type": "result", "is_error": False,
                                "subtype": "success", "result": "ok",
                                "session_id": "s1"}),
                ]
            return _FakeProc(lines, [])

        ok, err = claude_runner.stream_claude_with_retry(
            job, "p", ".", spawn=spawn, sleep=lambda s: None)
        self.assertTrue(ok, err)
        self.assertEqual(attempts["n"], 2)

    def test_no_retry_on_nontransient(self):
        job = Job(id="j", kind="area_card", prompt="p")
        attempts = {"n": 0}

        def spawn(argv):
            attempts["n"] += 1
            lines = [json.dumps({"type": "result", "is_error": True,
                                 "subtype": "invalid_request",
                                 "result": "bad prompt"})]
            return _FakeProc(lines, [])

        ok, err = claude_runner.stream_claude_with_retry(
            job, "p", ".", spawn=spawn, sleep=lambda s: None)
        self.assertFalse(ok)
        self.assertEqual(attempts["n"], 1)  # not retried

    def test_pipeline_skips_failed_card(self):
        # A persistently-failing area card is skipped; the pipeline still
        # finishes 'done' with a partial map and records the failure.
        import re
        with tempfile.TemporaryDirectory() as d:
            _sample_repo(Path(d))
            api = Api(d)
            ws = api.ws

            def spawn(argv):
                prompt = argv[argv.index("-p") + 1]
                if "area-tree.json" in prompt:
                    tree = {"content_lang": "ja", "system": {"name": "S"},
                            "areas": [
                                {"id": "ok", "name": "OK",
                                 "source_hints": {"keywords": ["t"]},
                                 "confidence": "high"},
                                {"id": "bad", "name": "BAD",
                                 "source_hints": {"keywords": ["t"]},
                                 "confidence": "high"}]}
                    return _FakeProc(
                        [json.dumps({"type": "system", "subtype": "init",
                                     "session_id": "s1"}),
                         json.dumps({"type": "result", "is_error": False,
                                     "subtype": "success", "result": "ok",
                                     "session_id": "s1"})],
                        [(ws / "area-tree.json",
                          json.dumps(tree, ensure_ascii=False))])
                if "意味地図のサマリ" in prompt:   # system purpose step
                    mm = json.loads((ws / "meaning-map.json").read_text("utf-8"))
                    mm.setdefault("system", {})["purpose"] = "テスト目的。"
                    return _FakeProc(
                        [json.dumps({"type": "result", "is_error": False,
                                     "subtype": "success", "result": "ok"})],
                        [(ws / "meaning-map.json",
                          json.dumps(mm, ensure_ascii=False))])
                path = re.search(r'([^\s`]+area-maps[^\s`]*\.json)', prompt).group(1)
                aid = Path(path).stem
                if aid == "bad":
                    return _FakeProc(
                        [json.dumps({"type": "result", "is_error": True,
                                     "subtype": "error_during_execution",
                                     "result": "API Error"})], [])
                card = {"content_lang": "ja",
                        "system": {"name": "S", "source_summary": {}},
                        "actors": [], "concepts": [], "flows": [],
                        "areas": [{"id": aid, "name": aid, "one_liner": "x",
                                   "tables": [], "apis": [], "code_refs": [],
                                   "related_area_ids": [], "child_area_ids": [],
                                   "confidence": "high", "crud_summary": {}}]}
                return _FakeProc(
                    [json.dumps({"type": "result", "is_error": False,
                                 "subtype": "success", "result": "ok"})],
                    [(Path(path), json.dumps(card, ensure_ascii=False))])

            api.spawn = spawn
            # Speed up retries.
            orig = claude_runner.stream_claude_with_retry

            def fast(job, prompt, repo_root, **kw):
                kw.setdefault("sleep", lambda s: None)
                return orig(job, prompt, repo_root, **kw)

            claude_runner.stream_claude_with_retry = fast
            try:
                job_id = api.start_init_job({"force": True})[1]["job_id"]
                for _ in range(400):
                    job = api.get_job(job_id)[1]
                    if job["status"] in ("done", "error", "aborted"):
                        break
                    time.sleep(0.01)
            finally:
                claude_runner.stream_claude_with_retry = orig

            self.assertEqual(job["status"], "done", job.get("error"))
            self.assertEqual(job["meta"].get("failed_areas"), ["bad"])
            self.assertTrue((ws / "area-maps" / "ok.json").exists())
            self.assertFalse((ws / "area-maps" / "bad.json").exists())


class HttpTests(unittest.TestCase):
    def test_http_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            _sample_repo(Path(d))
            httpd = serve(d, port=5994)
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            try:
                base = "http://127.0.0.1:5994"

                def call(method, path, body=None):
                    data = json.dumps(body).encode() if body is not None else None
                    req = urllib.request.Request(
                        base + path, data=data, method=method,
                        headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req) as resp:
                        return resp.status, json.loads(resp.read())

                self.assertFalse(call("GET", "/api/state")[1]["area_tree"])
                self.assertEqual(call("POST", "/api/analyze", {})[1]["files"], 2)
                self.assertEqual(
                    call("PUT", "/api/artifact/area-tree.json",
                         {"content_lang": "en", "areas": []})[0], 200)
                self.assertEqual(
                    call("GET", "/api/artifact/area-tree.json")[1]["content_lang"],
                    "en")

                # Static client is served.
                with urllib.request.urlopen(base + "/app/") as resp:
                    self.assertEqual(resp.status, 200)

                # Export endpoint returns a standalone HTML document.
                api = Api(d)
                api.put_artifact("meaning-map.json", {
                    "content_lang": "en", "system": {"name": "S"},
                    "areas": [{"id": "a", "name": "Area A", "concept_crud": [],
                               "related_area_ids": [], "child_area_ids": []}],
                    "concepts": [], "classifications": [], "components": [],
                    "actors": [], "flows": []})
                with urllib.request.urlopen(base + "/api/export") as resp:
                    self.assertEqual(resp.status, 200)
                    self.assertIn("text/html", resp.headers["Content-Type"])
                    doc = resp.read().decode("utf-8")
                self.assertIn("Area A", doc)
                self.assertNotIn('class="rv-pin"', doc)
            finally:
                httpd.shutdown()


class ReviewTests(unittest.TestCase):
    def _api_with_map(self, d):
        api = Api(d)
        # Default to a harmless spawn so the auto-run worker never invokes a
        # real `claude`; individual tests override api.spawn before creating
        # findings when they care about the run's effect.
        def _noop_spawn(argv):
            return _FakeProc([json.dumps({"type": "result", "is_error": False,
                                          "subtype": "success", "result": "ok"})], [])
        api.spawn = _noop_spawn
        mm = {"content_lang": "ja",
              "system": {"name": "S", "source_summary": {}},
              "actors": [{"id": "user", "name": "利用者", "actions": []}],
              "concepts": [{"id": "order", "name": "注文",
                            "physical_tables": ["orders"], "kind": "entity"}],
              "areas": [{"id": "sales", "name": "販売", "concepts": ["order"],
                         "concept_crud": [{"concept_id": "order", "ops": "CR"}],
                         "related_area_ids": [], "child_area_ids": []}],
              "flows": []}
        api.put_artifact("meaning-map.json", mm)
        return api

    def _wait(self, api, fid):
        """Findings auto-run on creation; wait for this one to finish and
        return its stored record."""
        for _ in range(200):
            f = next((x for x in api.list_findings()[1]["findings"]
                      if x["id"] == fid), None)
            if f and f["status"] in ("done", "error"):
                return f
            time.sleep(0.02)
        return next(x for x in api.list_findings()[1]["findings"] if x["id"] == fid)

    def test_create_validates_and_lists(self):
        with tempfile.TemporaryDirectory() as d:
            api = self._api_with_map(d)
            # actors first in the target listing.
            targets = api.list_review_targets()[1]
            self.assertEqual(list(targets.keys()),
                             ["actors", "concepts", "classifications",
                              "areas", "components"])
            self.assertEqual(400, api.create_finding({"target_type": "bad"})[0])
            st, f = api.create_finding({
                "target_type": "actor", "target_id": "user",
                "kind": "reframe", "comment": "来場者として捉え直す"})
            self.assertEqual(st, 201)
            self.assertEqual(api.list_findings()[1]["findings"][0]["id"], f["id"])
            # It auto-runs; wait so the worker isn't writing during cleanup.
            self._wait(api, f["id"])

    def test_reframe_edits_canonical_map(self):
        with tempfile.TemporaryDirectory() as d:
            api = self._api_with_map(d)
            ws = api.ws

            def spawn(argv):
                m = json.loads((ws / "meaning-map.json").read_text())
                m["actors"][0]["name"] = "来場者"
                lines = [json.dumps({"type": "system", "subtype": "init",
                                     "session_id": "rev1"}),
                         json.dumps({"type": "result", "is_error": False,
                                     "subtype": "success", "result": "ok",
                                     "session_id": "rev1"})]
                return _FakeProc(lines, [(ws / "meaning-map.json",
                                          json.dumps(m, ensure_ascii=False))])
            api.spawn = spawn
            _, f = api.create_finding({"target_type": "actor",
                                       "target_id": "user", "kind": "reframe",
                                       "comment": "来場者へ"})
            stored = self._wait(api, f["id"])
            self.assertEqual(stored["status"], "done")
            mm = api.get_artifact("meaning-map.json")[1]
            self.assertEqual(mm["actors"][0]["name"], "来場者")
            self.assertEqual(stored["session_id"], "rev1")

    def test_audit_writes_result_without_changing_map(self):
        with tempfile.TemporaryDirectory() as d:
            api = self._api_with_map(d)
            ws = api.ws
            before = (ws / "meaning-map.json").read_text()

            def spawn(argv):
                import re
                prompt = argv[argv.index("-p") + 1]
                ap = re.search(r'([^\s`]+audits[^\s`]*\.json)', prompt).group(1)
                payload = {"verdict": "unclear", "contradictions": [],
                           "unexplained_cases": ["再注文"], "evidence": [],
                           "notes": []}
                lines = [json.dumps({"type": "system", "subtype": "init",
                                     "session_id": "a1"}),
                         json.dumps({"type": "result", "is_error": False,
                                     "subtype": "success", "result": "ok"})]
                return _FakeProc(lines, [(Path(ap),
                                          json.dumps(payload, ensure_ascii=False))])
            api.spawn = spawn
            _, f = api.create_finding({"target_type": "concept",
                                       "target_id": "order", "kind": "audit",
                                       "comment": "キャンセルは説明できる?"})
            stored = self._wait(api, f["id"])
            self.assertEqual(stored["status"], "done")
            # Canonical map unchanged.
            self.assertEqual((ws / "meaning-map.json").read_text(), before)
            self.assertEqual(stored["audit_result"]["verdict"], "unclear")

    def test_proposal_writes_separate_file(self):
        with tempfile.TemporaryDirectory() as d:
            api = self._api_with_map(d)
            ws = api.ws

            def spawn(argv):
                import re
                prompt = argv[argv.index("-p") + 1]
                pp = re.search(r'([^\s`]+proposals[^\s`]*\.md)', prompt).group(1)
                lines = [json.dumps({"type": "result", "is_error": False,
                                     "subtype": "success", "result": "ok"})]
                return _FakeProc(lines, [(Path(pp), "# proposal\n…")])
            api.spawn = spawn
            _, f = api.create_finding({"target_type": "area",
                                       "target_id": "sales", "kind": "proposal",
                                       "comment": "サブスク販売を追加"})
            stored = self._wait(api, f["id"])
            self.assertEqual(stored["status"], "done")
            self.assertTrue(stored["proposal_ref"])
            self.assertTrue(Path(stored["proposal_ref"]).exists())

    def test_queue_autoruns_in_order(self):
        # Adding findings auto-runs them, one at a time, without any run call.
        with tempfile.TemporaryDirectory() as d:
            api = self._api_with_map(d)
            order = []

            def spawn(argv):
                prompt = argv[argv.index("-p") + 1]
                order.append(prompt)
                lines = [json.dumps({"type": "system", "subtype": "init",
                                     "session_id": "s1"}),
                         json.dumps({"type": "result", "is_error": False,
                                     "subtype": "success", "result": "ok",
                                     "session_id": "s1"})]
                return _FakeProc(lines, [])
            api.spawn = spawn

            fids = []
            for i in range(3):
                _, f = api.create_finding({
                    "target_type": "actor", "target_id": "user",
                    "kind": "audit", "comment": f"c{i}"})
                fids.append(f["id"])

            for fid in fids:
                self.assertEqual(self._wait(api, fid)["status"], "done")
            # All three ran automatically, each got a job id recorded.
            self.assertEqual(len(order), 3)
            for f in api.list_findings()[1]["findings"]:
                self.assertTrue(f["job_id"])


class TagTests(unittest.TestCase):
    def _api_with_concept(self, d):
        api = Api(d)
        mm = {"content_lang": "ja", "system": {"name": "S", "source_summary": {}},
              "actors": [], "flows": [], "areas": [],
              "concepts": [{"id": "order", "name": "注文", "kind": "entity",
                            "physical_tables": ["orders"]}]}
        api.put_artifact("meaning-map.json", mm)
        return api

    def test_vocab_roundtrip_dedup(self):
        with tempfile.TemporaryDirectory() as d:
            api = self._api_with_concept(d)
            self.assertEqual(api.get_tags()[1], {"tags": [], "groups": []})
            saved = api.put_tags({"tags": [
                {"name": "master", "description": "マスタ"},
                {"name": "transaction"}, "master", "  "]})[1]
            names = [t["name"] for t in saved["tags"]]
            self.assertEqual(names, ["master", "transaction"])
            # Each tag carries name/description/group.
            self.assertEqual(saved["tags"][0],
                             {"name": "master", "description": "マスタ", "group": ""})

    def test_groups_with_meaning(self):
        with tempfile.TemporaryDirectory() as d:
            api = self._api_with_concept(d)
            saved = api.put_tags({
                "groups": [{"name": "データ区分", "description": "マスタ/Tx"},
                           "データ区分"],  # deduped
                "tags": [{"name": "master", "description": "マスタ",
                          "group": "データ区分"}]})[1]
            self.assertEqual(saved["groups"],
                             [{"name": "データ区分", "description": "マスタ/Tx"}])
            self.assertEqual(saved["tags"][0]["group"], "データ区分")
            from dramaturgy.server import tags as _t
            self.assertEqual(_t.group_of(d)["master"], "データ区分")

    def test_patch_concept_tags_normalized_and_persisted(self):
        with tempfile.TemporaryDirectory() as d:
            api = self._api_with_concept(d)
            out = api.patch_concept("order",
                                    {"tags": ["transaction", "transaction", "  ", "新規"]})[1]
            self.assertEqual(out["tags"], ["transaction", "新規"])
            on_disk = api.get_artifact("meaning-map.json")[1]
            self.assertEqual(on_disk["concepts"][0]["tags"], ["transaction", "新規"])

    def test_patch_concept_missing(self):
        with tempfile.TemporaryDirectory() as d:
            api = self._api_with_concept(d)
            self.assertEqual(api.patch_concept("nope", {"tags": []})[0], 404)

    def test_merge_preserves_concept_tags(self):
        from dramaturgy.commands.merge_maps import merge

        class _UI:
            def t(self, *a, **k):
                return ""
        m = {"content_lang": "ja", "system": {"name": "S"},
             "areas": [{"id": "a", "name": "A", "concepts": ["order"],
                        "concept_crud": [{"concept_id": "order", "ops": "R"}],
                        "related_area_ids": [], "child_area_ids": []}],
             "concepts": [{"id": "order", "name": "注文", "kind": "entity",
                           "physical_tables": ["orders"],
                           "tags": ["transaction"]}],
             "actors": [], "flows": []}
        merged, _ = merge([m], _UI())
        order = next(c for c in merged["concepts"] if c["id"] == "order")
        self.assertEqual(order["tags"], ["transaction"])
        # aggregation still happened alongside tags
        self.assertTrue(order.get("crud_by_area"))

    def test_render_shows_tags_and_filter(self):
        from dramaturgy.commands.render_html import render_html
        mm = {"content_lang": "ja", "system": {"name": "S"},
              "actors": [], "flows": [], "areas": [],
              "concepts": [
                  {"id": "order", "name": "注文", "kind": "entity",
                   "physical_tables": ["orders"], "tags": ["transaction"]},
                  {"id": "item", "name": "商品", "kind": "entity",
                   "physical_tables": ["items"], "tags": ["master"]}]}
        html = render_html(mm, "ja")
        self.assertIn('id="concept-tag-filter"', html)
        self.assertIn('data-tag="master"', html)
        self.assertIn('data-tag="transaction"', html)
        self.assertIn('data-rv-field="tags"', html)


if __name__ == "__main__":
    unittest.main(verbosity=2)

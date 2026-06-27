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
                if "area-tree.json" in prompt:
                    tree = {"content_lang": "ja", "system": {"name": "S"},
                            "areas": [{"id": "sales", "name": "販売",
                                       "source_hints": {"keywords": ["ticket"]},
                                       "confidence": "high"}]}
                    writes = [(ws / "area-tree.json",
                               json.dumps(tree, ensure_ascii=False))]
                else:
                    path = re.search(r'([^\s`]+area-maps[^\s`]*\.json)', prompt).group(1)
                    aid = Path(path).stem
                    card = {"content_lang": "ja",
                            "system": {"name": "S", "source_summary": {}},
                            "actors": [], "concepts": [], "flows": [],
                            "areas": [{"id": aid, "name": aid, "one_liner": "x",
                                       "tables": [], "apis": [], "code_refs": [],
                                       "related_area_ids": [], "child_area_ids": [],
                                       "confidence": "high", "crud_summary": {}}]}
                    writes = [(Path(path), json.dumps(card, ensure_ascii=False))]
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
            finally:
                httpd.shutdown()


class ReviewTests(unittest.TestCase):
    def _api_with_map(self, d):
        api = Api(d)
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

    def _run(self, api, fid):
        status, res = api.run_finding(fid, {"continue_session": False})
        self.assertEqual(status, 202)
        for _ in range(100):
            job = api.get_job(res["job_id"])[1]
            if job["status"] in ("done", "error", "aborted"):
                break
            time.sleep(0.02)
        return job

    def test_create_validates_and_lists(self):
        with tempfile.TemporaryDirectory() as d:
            api = self._api_with_map(d)
            # actors first in the target listing.
            targets = api.list_review_targets()[1]
            self.assertEqual(list(targets.keys()), ["actors", "concepts", "areas"])
            self.assertEqual(400, api.create_finding({"target_type": "bad"})[0])
            st, f = api.create_finding({
                "target_type": "actor", "target_id": "user",
                "kind": "reframe", "comment": "来場者として捉え直す"})
            self.assertEqual(st, 201)
            self.assertEqual(api.list_findings()[1]["findings"][0]["id"], f["id"])

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
            job = self._run(api, f["id"])
            self.assertEqual(job["status"], "done")
            mm = api.get_artifact("meaning-map.json")[1]
            self.assertEqual(mm["actors"][0]["name"], "来場者")
            stored = api.list_findings()[1]["findings"][0]
            self.assertEqual(stored["status"], "done")
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
            job = self._run(api, f["id"])
            self.assertEqual(job["status"], "done")
            # Canonical map unchanged.
            self.assertEqual((ws / "meaning-map.json").read_text(), before)
            stored = api.list_findings()[1]["findings"][0]
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
            job = self._run(api, f["id"])
            self.assertEqual(job["status"], "done")
            stored = api.list_findings()[1]["findings"][0]
            self.assertTrue(stored["proposal_ref"])
            self.assertTrue(Path(stored["proposal_ref"]).exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)

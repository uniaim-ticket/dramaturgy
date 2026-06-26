"""HTTP-agnostic API for the dramaturgy web server.

Each method returns ``(status_code, payload)`` where payload is a JSON-able
value. The HTTP handler is a thin adapter over this class, so the API can be
unit-tested without sockets. All semantic generation is delegated to Claude
Code via the job runner; everything here is mechanical (analyze, read/write
JSON, merge, validate, render).
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Callable

from ..common.config import Config, load_config, save_config
from ..common.paths import ensure_workspace, read_json, workspace_dir, write_json
from ..commands.analyze_repo import analyze_repo as run_analyze_repo
from ..commands.analyze_schema import parse_schema
from ..commands.propose_area_candidates import build_candidates
from ..commands.merge_maps import merge as merge_maps
from ..commands.render_html import render_html
from ..commands.validate_map import Report, validate as run_validate
from ..common.i18n import Catalog
from . import claude_runner
from .jobs import JobRegistry
from .prompt_jobs import area_card_prompt, area_tree_prompt


class Api:
    def __init__(
        self,
        repo_root: str,
        *,
        claude_bin: str = "claude",
        spawn: Callable | None = None,
    ):
        self.repo_root = repo_root
        self.claude_bin = claude_bin
        self.spawn = spawn or claude_runner.default_spawn
        self.jobs = JobRegistry()
        ensure_workspace(repo_root)

    # ---- helpers -------------------------------------------------------
    @property
    def ws(self) -> Path:
        return workspace_dir(self.repo_root)

    def _config(self) -> Config:
        return load_config(self.repo_root) or Config(repo_root=self.repo_root)

    def _read_optional(self, name: str):
        try:
            return read_json(self.ws / name)
        except FileNotFoundError:
            return None

    # ---- config & state ------------------------------------------------
    def get_config(self):
        return 200, self._config().to_dict()

    def put_config(self, body: dict):
        try:
            cfg = Config.from_dict(body)
            cfg.repo_root = self.repo_root
            save_config(cfg, self.repo_root)
        except ValueError as exc:
            return 400, {"error": str(exc)}
        return 200, cfg.to_dict()

    def get_state(self):
        """What artifacts exist, so the UI can guide the next step."""
        def exists(name: str) -> bool:
            return (self.ws / name).exists()

        area_maps_dir = self.ws / "area-maps"
        area_maps = (sorted(p.name for p in area_maps_dir.glob("*.json"))
                     if area_maps_dir.exists() else [])
        return 200, {
            "repo_root": self.repo_root,
            "config": self._config().to_dict(),
            "source_index": exists("source-index.json"),
            "schema_index": exists("schema-index.json"),
            "area_candidates": exists("area-candidates.json"),
            "area_tree": exists("area-tree.json"),
            "meaning_map": exists("meaning-map.json"),
            "area_maps": area_maps,
        }

    # ---- mechanical analysis (no Claude) -------------------------------
    def analyze(self, body: dict | None = None):
        body = body or {}
        index = run_analyze_repo(self.repo_root)
        write_json(self.ws / "source-index.json", index)

        # Schema is optional: take an explicit list or scan for *.sql.
        schema_files = body.get("schema_files")
        if schema_files is None:
            schema_files = [str(p) for p in Path(self.repo_root).rglob("*.sql")
                            if ".dramaturgy" not in p.parts]
        schema_index = None
        if schema_files:
            sql = "\n".join(
                Path(p).read_text(encoding="utf-8", errors="replace")
                for p in schema_files if Path(p).exists())
            schema_index = {"sources": schema_files,
                            "summary": {"tables": 0},
                            "tables": parse_schema(sql)}
            schema_index["summary"]["tables"] = len(schema_index["tables"])
            write_json(self.ws / "schema-index.json", schema_index)

        candidates = build_candidates(index, schema_index or {"tables": []})
        write_json(self.ws / "area-candidates.json", candidates)
        return 200, {
            "files": index["summary"]["files"],
            "lines": index["summary"]["lines"],
            "tables": (schema_index or {}).get("summary", {}).get("tables", 0),
        }

    # ---- canonical JSON read/write (write-back) ------------------------
    def get_artifact(self, name: str):
        data = self._read_optional(name)
        if data is None:
            return 404, {"error": f"{name} not found"}
        return 200, data

    def put_artifact(self, name: str, body: Any):
        if not isinstance(body, (dict, list)):
            return 400, {"error": "body must be a JSON object or array"}
        write_json(self.ws / name, body)
        return 200, {"ok": True, "path": str(self.ws / name)}

    def patch_area(self, area_id: str, body: dict):
        """Update a single area inside meaning-map.json in place."""
        mm = self._read_optional("meaning-map.json")
        if mm is None:
            return 404, {"error": "meaning-map.json not found"}
        areas = mm.get("areas", [])
        for i, area in enumerate(areas):
            if area.get("id") == area_id:
                areas[i] = {**area, **body, "id": area_id}
                write_json(self.ws / "meaning-map.json", mm)
                return 200, areas[i]
        return 404, {"error": f"area '{area_id}' not found"}

    # ---- merge / validate / render -------------------------------------
    def merge(self, body: dict | None = None):
        body = body or {}
        amap_dir = self.ws / "area-maps"
        inputs = body.get("inputs")
        if inputs:
            paths = [Path(p) for p in inputs]
        elif amap_dir.exists():
            paths = sorted(amap_dir.glob("*.json"))
        else:
            paths = []
        if not paths:
            return 400, {"error": "no area-maps to merge"}
        ui = Catalog(self._config().ui_lang, domain="cli")
        merged, _ = merge_maps([read_json(p) for p in paths], ui)
        write_json(self.ws / "meaning-map.json", merged)
        return 200, {"areas": len(merged.get("areas", [])),
                     "report": merged.get("merge_report", {})}

    def validate(self):
        mm = self._read_optional("meaning-map.json")
        if mm is None:
            return 404, {"error": "meaning-map.json not found"}
        source_index = self._read_optional("source-index.json") or {"files": []}
        schema_index = self._read_optional("schema-index.json")
        cfg = self._config()
        report = Report(Catalog(cfg.ui_lang, domain="cli"))
        run_validate(mm, source_index, schema_index, cfg, self.repo_root, report)
        ok = not report.errors
        return 200, {"ok": ok, "errors": report.errors,
                     "warnings": report.warnings}

    def render(self):
        mm = self._read_optional("meaning-map.json")
        if mm is None:
            return 404, {"error": "meaning-map.json not found"}
        html = render_html(mm, self._config().ui_lang)
        out = self.ws / "meaning-map.html"
        out.write_text(html, encoding="utf-8")
        return 200, {"ok": True, "path": str(out)}

    def render_html_text(self) -> str | None:
        mm = self._read_optional("meaning-map.json")
        if mm is None:
            return None
        return render_html(mm, self._config().ui_lang)

    # ---- Claude Code jobs ----------------------------------------------
    def preflight(self):
        ok, info = claude_runner.preflight(self.claude_bin)
        return (200 if ok else 503), {"ok": ok, "info": info}

    def _start_job(self, kind: str, prompt: str, meta: dict, resume: str | None):
        job = self.jobs.create(kind, prompt, meta)
        claude_runner.start_job_thread(
            job, self.repo_root,
            claude_bin=self.claude_bin, spawn=self.spawn,
            resume_session=resume)
        return 202, {"job_id": job.id}

    def start_area_tree_job(self, body: dict | None = None):
        body = body or {}
        cfg = self._config()
        try:
            prompt = area_tree_prompt(
                self.repo_root, cfg.content_lang, cfg.project_name)
        except FileNotFoundError as exc:
            return 400, {"error": f"missing input: {exc}. Run analyze first."}
        return self._start_job("area_tree", prompt, {},
                               body.get("resume_session"))

    def start_area_card_job(self, body: dict):
        area_id = body.get("area_id")
        if not area_id:
            return 400, {"error": "area_id is required"}
        cfg = self._config()
        try:
            prompt = area_card_prompt(self.repo_root, cfg.content_lang, area_id)
        except KeyError:
            return 404, {"error": f"area '{area_id}' not in area-tree.json"}
        except FileNotFoundError as exc:
            return 400, {"error": f"missing input: {exc}. Run analyze first."}
        return self._start_job("area_card", prompt, {"area_id": area_id},
                               body.get("resume_session"))

    # ---- one-shot full initialization ---------------------------------
    def start_init_job(self, body: dict | None = None):
        """Run the whole pipeline as a single job:

        analyze -> Claude area tree -> Claude area card per area ->
        merge -> validate -> render.

        Mechanical steps run in-process; the two semantic steps invoke Claude
        Code headlessly, sharing this job's progress log. The individual
        buttons remain usable afterwards for adjustments.
        """
        body = body or {}
        ok, info = claude_runner.preflight(self.claude_bin)
        if not ok and not body.get("force"):
            return 503, {"error": f"Claude Code CLI not available ({info}); "
                                  "cannot run full initialization"}
        job = self.jobs.create("init", "(pipeline)", {})
        threading.Thread(
            target=self._run_init, args=(job,), daemon=True).start()
        return 202, {"job_id": job.id}

    def _run_init(self, job) -> None:
        from .jobs import Job  # local import to avoid cycle at module load
        assert isinstance(job, Job)
        cfg = self._config()
        job.set_status("running")
        try:
            # 1. analyze (mechanical)
            job.append_progress("[1/6] analyze repository")
            res = self.analyze({})[1]
            job.append_progress(
                f"      files={res['files']} tables={res['tables']}")

            # 2. area tree (Claude)
            job.append_progress("[2/6] generate area tree with Claude")
            prompt = area_tree_prompt(
                self.repo_root, cfg.content_lang, cfg.project_name)
            ok, err = claude_runner.stream_claude(
                job, prompt, self.repo_root,
                claude_bin=self.claude_bin, spawn=self.spawn)
            if not ok:
                return self._fail(job, f"area tree: {err}")
            tree = self._read_optional("area-tree.json")
            if not tree or not tree.get("areas"):
                return self._fail(job, "area-tree.json missing or has no areas")

            # 3. area cards (Claude, one invocation per area, resumed)
            areas = tree.get("areas", [])
            job.append_progress(f"[3/6] generate {len(areas)} area cards")
            for i, area in enumerate(areas, 1):
                area_id = area.get("id")
                job.append_progress(f"      ({i}/{len(areas)}) {area_id}")
                card_prompt = area_card_prompt(
                    self.repo_root, cfg.content_lang, area_id)
                ok, err = claude_runner.stream_claude(
                    job, card_prompt, self.repo_root,
                    claude_bin=self.claude_bin, spawn=self.spawn,
                    resume_session=job.session_id)
                if not ok:
                    return self._fail(job, f"area card {area_id}: {err}")

            # 4-6. merge / validate / render (mechanical)
            job.append_progress("[4/6] merge area cards")
            code, merged = self.merge({})
            if code != 200:
                return self._fail(job, f"merge: {merged.get('error')}")
            job.append_progress(f"      merged areas={merged.get('areas')}")
            job.append_progress("[5/6] validate")
            code, v = self.validate()
            if code != 200:
                return self._fail(job, f"validate: {v.get('error')}")
            job.append_progress(
                f"      ok={v['ok']} errors={len(v['errors'])} "
                f"warnings={len(v['warnings'])}")
            job.append_progress("[6/6] render HTML")
            self.render()
            job.result_summary = (
                f"initialized: {len(areas)} areas, validate ok={v['ok']}")
            job.set_status("done")
        except (FileNotFoundError, KeyError, ValueError) as exc:
            self._fail(job, str(exc))

    @staticmethod
    def _fail(job, message: str) -> None:
        job.append_progress(f"ERROR: {message}")
        job.set_status("error", error=message)

    def get_job(self, job_id: str, since: int = 0):
        job = self.jobs.get(job_id)
        if job is None:
            return 404, {"error": "job not found"}
        return 200, job.to_dict(since=since)

    def list_jobs(self):
        return 200, {"jobs": [j.to_dict() for j in self.jobs.list()]}

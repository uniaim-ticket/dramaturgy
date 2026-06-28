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
from ..commands.merge_maps import merge as merge_maps
from ..commands.render_html import render_html
from ..commands.validate_map import Report, validate as run_validate
from ..common.i18n import Catalog
from . import claude_runner
from . import reviews
from . import tags
from .jobs import JobRegistry
from .prompt_jobs import (
    area_card_prompt, area_tree_prompt, review_prompt, subdivide_review_prompt,
    system_purpose_prompt,
)


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
        # Review queue auto-runs: a single background worker drains open
        # findings one at a time, in order. Users don't start/stop runs.
        self._review_lock = threading.Lock()
        self._review_worker: threading.Thread | None = None
        self._recover_and_start_worker()

    def _recover_and_start_worker(self) -> None:
        """Re-queue findings left 'running' by a previous process, then start
        the worker if there is anything open."""
        data = reviews.load_reviews(self.repo_root)
        changed = False
        for f in data["findings"]:
            if f.get("status") == "running":
                f["status"] = "open"
                f["job_id"] = None
                changed = True
        if changed:
            reviews.save_reviews(self.repo_root, data)
        if any(f.get("status") == "open" for f in data["findings"]):
            self._ensure_review_worker()

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

    # ---- init instructions (repo-specific, reused across init runs) -----
    @property
    def _instructions_path(self) -> Path:
        return self.ws / "init-instructions.txt"

    def _read_instructions(self) -> str:
        try:
            return self._instructions_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""

    def get_init_instructions(self):
        return 200, {"instructions": self._read_instructions()}

    def put_init_instructions(self, body: dict):
        text = (body or {}).get("instructions", "")
        if not isinstance(text, str):
            return 400, {"error": "instructions must be a string"}
        self._instructions_path.parent.mkdir(parents=True, exist_ok=True)
        self._instructions_path.write_text(text, encoding="utf-8")
        return 200, {"instructions": text}

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
            "area_tree": exists("area-tree.json"),
            "meaning_map": exists("meaning-map.json"),
            "area_maps": area_maps,
        }

    # ---- mechanical analysis (no Claude) -------------------------------
    def analyze(self, body: dict | None = None):
        """Inventory files/directories only. Tables/entities/APIs are NOT
        extracted here — Claude discovers those by reading the source."""
        index = run_analyze_repo(self.repo_root)
        write_json(self.ws / "source-index.json", index)
        return 200, {
            "files": index["summary"]["files"],
            "lines": index["summary"]["lines"],
            "directories": len(index.get("directories", [])),
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

    def patch_concept(self, concept_id: str, body: dict):
        """Update a single concept (e.g. its tags) in meaning-map.json.

        ``tags`` is normalized to a deduped list of non-empty strings.
        """
        mm = self._read_optional("meaning-map.json")
        if mm is None:
            return 404, {"error": "meaning-map.json not found"}
        if "tags" in body:
            seen, norm = set(), []
            for tg in body["tags"] or []:
                tg = str(tg).strip()
                if tg and tg not in seen:
                    seen.add(tg)
                    norm.append(tg)
            body = {**body, "tags": norm}
        concepts = mm.get("concepts", [])
        for i, c in enumerate(concepts):
            if c.get("id") == concept_id:
                concepts[i] = {**c, **body, "id": concept_id}
                write_json(self.ws / "meaning-map.json", mm)
                return 200, concepts[i]
        return 404, {"error": f"concept '{concept_id}' not found"}

    # ---- tag vocabulary (system-specific) ------------------------------
    def get_tags(self):
        return 200, tags.load_vocab(self.repo_root)

    def put_tags(self, body: dict):
        return 200, tags.save_vocab(self.repo_root, body or {})

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
        cfg = self._config()
        report = Report(Catalog(cfg.ui_lang, domain="cli"))
        run_validate(mm, source_index, cfg, self.repo_root, report)
        ok = not report.errors
        return 200, {"ok": ok, "errors": report.errors,
                     "warnings": report.warnings}

    def render(self):
        mm = self._read_optional("meaning-map.json")
        if mm is None:
            return 404, {"error": "meaning-map.json not found"}
        html = render_html(mm, self._config().ui_lang,
                           tags.load_vocab(self.repo_root))
        out = self.ws / "meaning-map.html"
        out.write_text(html, encoding="utf-8")
        return 200, {"ok": True, "path": str(out)}

    def render_html_text(self) -> str | None:
        mm = self._read_optional("meaning-map.json")
        if mm is None:
            return None
        return render_html(mm, self._config().ui_lang,
                           tags.load_vocab(self.repo_root))

    def export_html_text(self) -> str | None:
        """A standalone shareable document: the same map, rendered without the
        review pins / app coupling, as a single self-contained HTML file."""
        mm = self._read_optional("meaning-map.json")
        if mm is None:
            return None
        return render_html(mm, self._config().ui_lang,
                           tags.load_vocab(self.repo_root), export=True)

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
        extra = self._read_instructions()
        try:
            prompt = area_tree_prompt(
                self.repo_root, cfg.content_lang, cfg.project_name,
                extra_instructions=extra)
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
            prompt = area_card_prompt(self.repo_root, cfg.content_lang, area_id,
                                      extra_instructions=self._read_instructions())
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
        # An "instructions" field in the request both persists (for reuse) and
        # is applied to this run; otherwise the saved instructions are used.
        if "instructions" in body:
            self.put_init_instructions({"instructions": body["instructions"]})
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
        extra = self._read_instructions()
        job.set_status("running")
        try:
            # 1. analyze (mechanical)
            job.append_progress("[1/8] analyze repository")
            res = self.analyze({})[1]
            job.append_progress(
                f"      files={res['files']} lines={res['lines']}")
            if extra.strip():
                job.append_progress("      (applying saved init instructions)")

            # 2. area tree (Claude, with retry on transient errors)
            job.append_progress("[2/8] generate area tree with Claude")
            prompt = area_tree_prompt(
                self.repo_root, cfg.content_lang, cfg.project_name,
                extra_instructions=extra)
            ok, err = claude_runner.stream_claude_with_retry(
                job, prompt, self.repo_root,
                claude_bin=self.claude_bin, spawn=self.spawn)
            if not ok:
                # The tree is a hard prerequisite — without it there is
                # nothing to card. Stop, but leave the job re-runnable.
                return self._fail(job, f"area tree: {err}")
            tree = self._read_optional("area-tree.json")
            if not tree or not tree.get("areas"):
                return self._fail(job, "area-tree.json missing or has no areas")

            # 3. subdivide review (Claude) — split only the areas that warrant
            # child areas, expanding area-tree.json. Best-effort: a failure
            # here just leaves the flat tree (cards still run).
            n_before = len(tree.get("areas", []))
            job.append_progress("[3/8] review for sub-areas")
            sub_prompt = subdivide_review_prompt(
                self.repo_root, cfg.content_lang, extra_instructions=extra)
            ok, err = claude_runner.stream_claude_with_retry(
                job, sub_prompt, self.repo_root,
                claude_bin=self.claude_bin, spawn=self.spawn,
                resume_session=job.session_id)
            if ok:
                tree = self._read_optional("area-tree.json") or tree
                n_after = len(tree.get("areas", []))
                if n_after > n_before:
                    job.append_progress(
                        f"      split into {n_after - n_before} new sub-area(s)")
                else:
                    job.append_progress("      no sub-areas needed")
            else:
                job.append_progress(f"      ! subdivide skipped: {err}")

            # 4. area cards (Claude) for every area in the (possibly expanded)
            # tree. A card that fails (e.g. a transient API error that
            # survives retries) is recorded and SKIPPED — the run continues so
            # the user still gets a partial map and can regenerate later.
            areas = tree.get("areas", [])
            job.append_progress(f"[4/8] generate {len(areas)} area cards")
            failed: list[str] = []
            for i, area in enumerate(areas, 1):
                area_id = area.get("id")
                job.append_progress(f"      ({i}/{len(areas)}) {area_id}")
                try:
                    card_prompt = area_card_prompt(
                        self.repo_root, cfg.content_lang, area_id,
                        extra_instructions=extra)
                except (FileNotFoundError, KeyError) as exc:
                    failed.append(area_id)
                    job.append_progress(f"      ! skipped {area_id}: {exc}")
                    continue
                ok, err = claude_runner.stream_claude_with_retry(
                    job, card_prompt, self.repo_root,
                    claude_bin=self.claude_bin, spawn=self.spawn,
                    resume_session=job.session_id)
                if not ok:
                    failed.append(area_id)
                    job.append_progress(
                        f"      ! failed {area_id}: {err} — continuing")

            # 4-6. merge / validate / render whatever cards we have.
            produced = [p.stem for p in (self.ws / "area-maps").glob("*.json")] \
                if (self.ws / "area-maps").exists() else []
            if not produced:
                return self._fail(
                    job, "no area cards were produced; "
                         f"all {len(areas)} areas failed: {failed}")

            job.append_progress("[5/8] merge area cards")
            code, merged = self.merge({})
            if code != 200:
                return self._fail(job, f"merge: {merged.get('error')}")
            # The area tree is authoritative for the hierarchy; overlay
            # parent/child onto the merged map so subdivisions are reflected
            # even if a card omitted them.
            self._apply_tree_hierarchy(tree)
            job.append_progress(f"      merged areas={merged.get('areas')}")
            job.append_progress("[6/8] validate")
            code, v = self.validate()
            if code != 200:
                return self._fail(job, f"validate: {v.get('error')}")
            job.append_progress(
                f"      ok={v['ok']} errors={len(v['errors'])} "
                f"warnings={len(v['warnings'])}")

            # 7. system purpose (Claude) — the finishing touch: a concise
            # overall purpose for the whole system, written last so it can
            # draw on the complete map. Best-effort: a failure just leaves the
            # map without a purpose (the section is then omitted).
            job.append_progress("[7/8] write system purpose")
            purpose_prompt = system_purpose_prompt(
                self.repo_root, cfg.content_lang, extra_instructions=extra)
            ok, err = claude_runner.stream_claude_with_retry(
                job, purpose_prompt, self.repo_root,
                claude_bin=self.claude_bin, spawn=self.spawn,
                resume_session=job.session_id)
            if ok:
                job.append_progress("      purpose written")
            else:
                job.append_progress(f"      ! purpose skipped: {err}")

            job.append_progress("[8/8] render HTML")
            self.render()

            if failed:
                job.append_progress(
                    f"NOTE: {len(failed)} area(s) failed and were skipped: "
                    f"{', '.join(failed)}. Regenerate them individually.")
                job.meta["failed_areas"] = failed
            job.result_summary = (
                f"initialized: {len(produced)}/{len(areas)} areas, "
                f"validate ok={v['ok']}"
                + (f", {len(failed)} failed" if failed else ""))
            # A partial run still 'done' (the user has a usable map); the
            # failed list is surfaced in progress + meta for follow-up.
            job.set_status("done")
        except (FileNotFoundError, KeyError, ValueError) as exc:
            self._fail(job, str(exc))

    def _apply_tree_hierarchy(self, tree: dict) -> None:
        """Copy the authoritative parent/child hierarchy from the area tree
        onto meaning-map.json (cards may omit it). Areas not in the tree are
        left untouched."""
        mm = self._read_optional("meaning-map.json")
        if mm is None:
            return
        tree_by_id = {a.get("id"): a for a in tree.get("areas", [])}
        changed = False
        for area in mm.get("areas", []):
            t = tree_by_id.get(area.get("id"))
            if not t:
                continue
            for field in ("parent_area_id", "child_area_ids"):
                if field in t and area.get(field) != t[field]:
                    area[field] = t[field]
                    changed = True
        if changed:
            write_json(self.ws / "meaning-map.json", mm)

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

    # ---- interactive review (3-kind findings) --------------------------
    def list_review_targets(self):
        """Items that can be reviewed, actors first (the usual entry point)."""
        mm = self._read_optional("meaning-map.json")
        if mm is None:
            return 404, {"error": "meaning-map.json not found"}

        def items(key):
            return [{"id": x.get("id"), "name": x.get("name") or x.get("id")}
                    for x in mm.get(key, [])]
        return 200, {
            "actors": items("actors"),
            "concepts": items("concepts"),
            "classifications": items("classifications"),
            "areas": items("areas"),
            "components": items("components"),
        }

    def list_findings(self):
        return 200, reviews.load_reviews(self.repo_root)

    def get_review_settings(self):
        return 200, reviews.load_reviews(self.repo_root)["settings"]

    def put_review_settings(self, body: dict):
        return 200, reviews.set_settings(self.repo_root, body or {})

    def create_finding(self, body: dict):
        err = reviews.validate_new(body or {})
        if err:
            return 400, {"error": err}
        finding = reviews.create_finding(self.repo_root, body)
        # Queued findings auto-run: wake the worker so it drains the queue.
        self._ensure_review_worker()
        return 201, finding

    def update_finding(self, fid: str, body: dict):
        f = reviews.update_finding(self.repo_root, fid, body or {})
        if f is None:
            return 404, {"error": "finding not found"}
        return 200, f

    def delete_finding(self, fid: str):
        if not reviews.delete_finding(self.repo_root, fid):
            return 404, {"error": "finding not found"}
        return 200, {"ok": True}

    def rerun_finding(self, fid: str):
        """Re-queue a finding (set it back to open); the worker picks it up."""
        f = reviews.update_finding(self.repo_root, fid,
                                   {"status": "open", "job_id": None})
        if f is None:
            return 404, {"error": "finding not found"}
        self._ensure_review_worker()
        return 202, f

    # ---- auto-run worker -----------------------------------------------
    def _ensure_review_worker(self) -> None:
        """Start the review worker if it isn't already running."""
        with self._review_lock:
            if self._review_worker and self._review_worker.is_alive():
                return
            self._review_worker = threading.Thread(
                target=self._review_loop, daemon=True)
            self._review_worker.start()

    def _review_loop(self) -> None:
        """Drain open findings one at a time, in order, until none remain."""
        while True:
            finding = reviews.claim_next_open(self.repo_root)
            if finding is None:
                return
            self._run_one_finding(finding)

    def _last_review_session(self) -> str | None:
        sessions = [f.get("session_id")
                    for f in reviews.load_reviews(self.repo_root)["findings"]
                    if f.get("session_id")]
        return sessions[-1] if sessions else None

    def _run_one_finding(self, finding: dict) -> None:
        fid = finding["id"]
        cfg = self._config()
        try:
            prompt, out_path = review_prompt(
                self.repo_root, cfg.content_lang, finding)
        except FileNotFoundError as exc:
            reviews.update_finding(self.repo_root, fid,
                                   {"status": "error",
                                    "result": f"missing template: {exc}"})
            return

        settings = reviews.load_reviews(self.repo_root)["settings"]
        resume = None
        if settings.get("continue_session"):
            resume = finding.get("session_id") or self._last_review_session()

        job = self.jobs.create(f"review:{finding['kind']}", prompt,
                               {"finding_id": fid, "out_path": out_path})
        # Record the job id so the UI can follow progress for this finding.
        reviews.update_finding(self.repo_root, fid, {"job_id": job.id})

        ok, err = claude_runner.stream_claude_with_retry(
            job, job.prompt, self.repo_root,
            claude_bin=self.claude_bin, spawn=self.spawn,
            resume_session=resume)
        patch = {"session_id": job.session_id}
        if ok:
            job.set_status("done")
            patch["status"] = "done"
            patch["result"] = job.result_summary
            if out_path and Path(out_path).exists():
                if job.kind == "review:audit":
                    try:
                        patch["audit_result"] = read_json(out_path)
                    except (FileNotFoundError, ValueError):
                        pass
                elif job.kind == "review:proposal":
                    patch["proposal_ref"] = out_path
        else:
            status = "aborted" if err and "without a result" in err else "error"
            job.set_status(status, error=err)
            patch["status"] = "error"
            patch["result"] = err or ""
        reviews.update_finding(self.repo_root, fid, patch)

"""Thin stdlib HTTP adapter over :class:`~dramaturgy.server.api.Api`.

Routes ``/api/...`` to API methods and serves the browser client from
``dramaturgy/server/static/``. Binds to 127.0.0.1 only — this is a local
single-user tool, not a network service.
"""

from __future__ import annotations

import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .api import Api

STATIC_DIR = Path(__file__).resolve().parent / "static"

_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
}


class Router:
    """Maps (method, path) to handlers, with simple ``<param>`` segments."""

    def __init__(self, api: Api):
        self.api = api
        self.routes: list[tuple[str, re.Pattern, str]] = []
        self._register()

    def _add(self, method: str, pattern: str, fn_name: str):
        regex = re.compile("^" + re.sub(r"<(\w+)>", r"(?P<\1>[^/]+)", pattern) + "$")
        self.routes.append((method, regex, fn_name))

    def _register(self):
        self._add("GET", "/api/state", "h_state")
        self._add("GET", "/api/config", "h_get_config")
        self._add("PUT", "/api/config", "h_put_config")
        self._add("POST", "/api/analyze", "h_analyze")
        self._add("GET", "/api/artifact/<name>", "h_get_artifact")
        self._add("PUT", "/api/artifact/<name>", "h_put_artifact")
        self._add("PATCH", "/api/area/<area_id>", "h_patch_area")
        self._add("PATCH", "/api/concept/<concept_id>", "h_patch_concept")
        self._add("GET", "/api/tags", "h_get_tags")
        self._add("PUT", "/api/tags", "h_put_tags")
        self._add("POST", "/api/merge", "h_merge")
        self._add("GET", "/api/validate", "h_validate")
        self._add("POST", "/api/render", "h_render")
        self._add("GET", "/api/view", "h_view_html")
        self._add("GET", "/api/preflight", "h_preflight")
        self._add("POST", "/api/jobs/init", "h_job_init")
        self._add("POST", "/api/jobs/area-tree", "h_job_area_tree")
        self._add("POST", "/api/jobs/area-card", "h_job_area_card")
        self._add("GET", "/api/jobs/<job_id>", "h_get_job")
        self._add("GET", "/api/jobs", "h_list_jobs")
        # Interactive review (3-kind findings).
        self._add("GET", "/api/review/targets", "h_review_targets")
        self._add("GET", "/api/review/findings", "h_list_findings")
        self._add("POST", "/api/review/findings", "h_create_finding")
        self._add("PATCH", "/api/review/findings/<fid>", "h_update_finding")
        self._add("DELETE", "/api/review/findings/<fid>", "h_delete_finding")
        self._add("POST", "/api/review/findings/<fid>/run", "h_run_finding")

    def resolve(self, method: str, path: str):
        for m, regex, fn_name in self.routes:
            if m != method:
                continue
            match = regex.match(path)
            if match:
                return getattr(self, fn_name), match.groupdict()
        return None, None

    # ---- handlers: return (status, payload) or (status, payload, ctype) -
    def h_state(self, params, body, query):
        return self.api.get_state()

    def h_get_config(self, params, body, query):
        return self.api.get_config()

    def h_put_config(self, params, body, query):
        return self.api.put_config(body or {})

    def h_analyze(self, params, body, query):
        return self.api.analyze(body or {})

    def h_get_artifact(self, params, body, query):
        return self.api.get_artifact(params["name"])

    def h_put_artifact(self, params, body, query):
        return self.api.put_artifact(params["name"], body)

    def h_patch_area(self, params, body, query):
        return self.api.patch_area(params["area_id"], body or {})

    def h_patch_concept(self, params, body, query):
        return self.api.patch_concept(params["concept_id"], body or {})

    def h_get_tags(self, params, body, query):
        return self.api.get_tags()

    def h_put_tags(self, params, body, query):
        return self.api.put_tags(body or {})

    def h_merge(self, params, body, query):
        return self.api.merge(body or {})

    def h_validate(self, params, body, query):
        return self.api.validate()

    def h_render(self, params, body, query):
        return self.api.render()

    def h_view_html(self, params, body, query):
        html = self.api.render_html_text()
        if html is None:
            return 404, "<h1>meaning-map.json not found</h1>", "text/html; charset=utf-8"
        return 200, html, "text/html; charset=utf-8"

    def h_preflight(self, params, body, query):
        return self.api.preflight()

    def h_job_init(self, params, body, query):
        return self.api.start_init_job(body or {})

    def h_job_area_tree(self, params, body, query):
        return self.api.start_area_tree_job(body or {})

    def h_job_area_card(self, params, body, query):
        return self.api.start_area_card_job(body or {})

    def h_get_job(self, params, body, query):
        since = int((query.get("since") or ["0"])[0])
        return self.api.get_job(params["job_id"], since)

    def h_list_jobs(self, params, body, query):
        return self.api.list_jobs()

    # ---- review handlers ----
    def h_review_targets(self, params, body, query):
        return self.api.list_review_targets()

    def h_list_findings(self, params, body, query):
        return self.api.list_findings()

    def h_create_finding(self, params, body, query):
        return self.api.create_finding(body or {})

    def h_update_finding(self, params, body, query):
        return self.api.update_finding(params["fid"], body or {})

    def h_delete_finding(self, params, body, query):
        return self.api.delete_finding(params["fid"])

    def h_run_finding(self, params, body, query):
        return self.api.run_finding(params["fid"], body or {})


def make_handler(api: Api):
    router = Router(api)

    class Handler(BaseHTTPRequestHandler):
        server_version = "dramaturgy/0.1"

        def log_message(self, *args):  # quiet by default
            pass

        # -- dispatch -----------------------------------------------------
        def _dispatch(self, method: str):
            parsed = urlparse(self.path)
            path = parsed.path
            query = parse_qs(parsed.query)

            if path.startswith("/api/"):
                fn, params = router.resolve(method, path)
                if fn is None:
                    return self._send_json(404, {"error": "no such endpoint"})
                body = self._read_body() if method in ("POST", "PUT", "PATCH") else None
                if body is _BAD_JSON:
                    return self._send_json(400, {"error": "invalid JSON body"})
                result = fn(params, body, query)
                if len(result) == 3:
                    status, payload, ctype = result
                    return self._send_raw(status, payload, ctype)
                status, payload = result
                return self._send_json(status, payload)

            if method == "GET":
                return self._serve_static(path)
            return self._send_json(405, {"error": "method not allowed"})

        def do_GET(self):
            self._dispatch("GET")

        def do_POST(self):
            self._dispatch("POST")

        def do_PUT(self):
            self._dispatch("PUT")

        def do_PATCH(self):
            self._dispatch("PATCH")

        def do_DELETE(self):
            self._dispatch("DELETE")

        # -- helpers ------------------------------------------------------
        def _read_body(self):
            length = int(self.headers.get("Content-Length", 0) or 0)
            if length == 0:
                return None
            raw = self.rfile.read(length)
            try:
                return json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return _BAD_JSON

        def _send_json(self, status, payload):
            data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self._send_raw(status, data, "application/json; charset=utf-8")

        def _send_raw(self, status, payload, ctype):
            if isinstance(payload, str):
                payload = payload.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _serve_static(self, path: str):
            # The client uses relative asset/API paths, so it must be served
            # from a URL ending in "app/". Redirect "/" and "/app" there with
            # a RELATIVE Location, so it works behind a proxy sub-path.
            if path in ("/", "/app"):
                self.send_response(302)
                self.send_header("Location", "app/")
                self.end_headers()
                return
            rel = "app/index.html" if path == "/app/" else path.lstrip("/")
            target = (STATIC_DIR / rel).resolve()
            if not str(target).startswith(str(STATIC_DIR.resolve())) or not target.is_file():
                return self._send_raw(404, "not found", "text/plain; charset=utf-8")
            ctype = _CONTENT_TYPES.get(target.suffix, "application/octet-stream")
            self._send_raw(200, target.read_bytes(), ctype)

    return Handler


_BAD_JSON = object()


def serve(repo_root: str, host: str = "127.0.0.1", port: int = 5178,
          *, claude_bin: str = "claude") -> ThreadingHTTPServer:
    api = Api(repo_root, claude_bin=claude_bin)
    handler = make_handler(api)
    httpd = ThreadingHTTPServer((host, port), handler)
    return httpd

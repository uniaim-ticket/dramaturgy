"""serve — start the local web UI and (optionally) open the browser.

This is the primary way to use dramaturgy: the browser UI views and edits
the meaning map and triggers Claude Code (headless) to do the semantic
work. The CLI here just starts the server; everything else happens in the
UI or in Claude Code.

    dra serve                 # start on 127.0.0.1:5178 and open the browser
    dra serve --no-open       # don't open a browser
    dra serve --port 6000

The server binds to localhost only.
"""

from __future__ import annotations

import argparse
import sys
import threading
import webbrowser

from ..common.config import load_config, Config
from ..common.paths import ensure_workspace
from ..server.claude_runner import preflight
from ..server.http import serve as make_server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start the dramaturgy web UI")
    parser.add_argument("--repo-root", default=None,
                        help="repository root (defaults to config.json or '.')")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5178)
    parser.add_argument("--no-open", action="store_true",
                        help="do not open a browser")
    parser.add_argument("--claude-bin", default="claude",
                        help="Claude Code CLI binary (default: claude)")
    args = parser.parse_args(argv)

    repo_root = args.repo_root or (
        (load_config(".") or Config()).repo_root if load_config(".") else ".")
    ensure_workspace(repo_root)

    ok, info = preflight(args.claude_bin)
    if ok:
        print(f"Claude Code: {info}")
    else:
        # Not fatal — analyze/edit/validate work without Claude; only the
        # "Generate with Claude" buttons need it.
        print(f"warning: Claude Code preflight failed: {info}", file=sys.stderr)
        print("         (mechanical steps still work; generation buttons won't)",
              file=sys.stderr)

    httpd = make_server(repo_root, host=args.host, port=args.port,
                        claude_bin=args.claude_bin)
    url = f"http://{args.host}:{args.port}/app/"
    print(f"dramaturgy serving {repo_root} at {url}")
    print("press Ctrl+C to stop")

    if not args.no_open:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping…")
        httpd.shutdown()
    return 0

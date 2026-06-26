"""Local web server for dramaturgy.

The server hosts a browser UI that views and edits the meaning map, and
triggers Claude Code (headless CLI subprocess) to do the semantic work
(generate the area tree, refine area cards). The canonical artifacts stay
``area-tree.json`` / ``meaning-map.json``; the UI writes edits back to them
and the HTML view is regenerated from JSON.

This mirrors the requirements-reviewer (rr) model: an HTML/JSON artifact
stays central, humans edit/annotate in the browser, and Claude Code is
invoked as a subprocess to apply the heavier changes.

Stdlib only — no Node/React build step, no third-party Python deps.
"""

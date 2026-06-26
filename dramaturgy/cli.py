"""``dra`` / ``dramaturgy`` command dispatcher.

A single entry point routes to the subcommand modules in
``dramaturgy.commands``. Each subcommand module exposes ``main(argv)`` and
parses its own arguments, so ``dra <sub> --help`` shows that subcommand's
options. The dispatcher only owns the subcommand list and the top-level
``--help`` / ``--version`` behavior.

Both ``dra`` and ``dramaturgy`` resolve here (see pyproject scripts); ``dra``
is the short alias.
"""

from __future__ import annotations

import importlib
import sys

from . import __version__

# subcommand name -> (module under dramaturgy.commands, one-line help)
# Primary flow is: setup -> serve (the web UI drives everything else and
# invokes Claude Code). The remaining commands are the mechanical steps the
# UI calls internally, exposed for scripting / Claude-Code custom commands.
COMMANDS: dict[str, tuple[str, str]] = {
    # primary
    "setup":       ("setup_cmd", "initialize .dramaturgy/config.json (languages + project)"),
    "serve":       ("serve", "start the web UI; edit the map and drive Claude Code"),
    # mechanical (also used by the server and by scripts/Claude Code)
    "analyze-repo": ("analyze_repo", "index source files, roles, routes, table hints"),
    "analyze-schema": ("analyze_schema", "parse SQL DDL into tables / FKs / status columns"),
    "candidates":  ("propose_area_candidates", "assemble area-grouping material for Claude"),
    "tree-prompt": ("build_area_tree_prompt", "render the content_lang area-tree prompt"),
    "pack":        ("build_area_pack", "gather one area's files/tables/APIs (warns if large)"),
    "subdivide":   ("suggest_subdivision", "propose natural sub-areas (never auto-splits)"),
    "merge":       ("merge_maps", "merge per-area maps into meaning-map.json"),
    "validate":    ("validate_map", "mechanical consistency + language invariants"),
    "render":      ("render_html", "render meaning-map.json to a self-contained HTML"),
}

PRIMARY = ("setup", "serve")


def _print_help() -> None:
    print("dramaturgy (dra) — generate a meaning map of a large system\n")
    print("usage: dra <command> [options]\n")
    width = max(len(name) for name in COMMANDS)
    print("primary:")
    for name in PRIMARY:
        print(f"  {name:<{width}}  {COMMANDS[name][1]}")
    print("\nmechanical steps (the web UI runs these for you; also scriptable):")
    for name, (_, help_text) in COMMANDS.items():
        if name in PRIMARY:
            continue
        print(f"  {name:<{width}}  {help_text}")
    print("\nrun 'dra <command> --help' for command-specific options.")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv or argv[0] in ("-h", "--help", "help"):
        _print_help()
        return 0
    if argv[0] in ("-V", "--version", "version"):
        print(f"dramaturgy {__version__}")
        return 0

    name = argv[0]
    if name not in COMMANDS:
        print(f"dra: unknown command '{name}'\n", file=sys.stderr)
        _print_help()
        return 2

    module_name, _ = COMMANDS[name]
    module = importlib.import_module(f".commands.{module_name}", __package__)
    # Make each subcommand's argparse usage read "dra <command> ..." rather
    # than the dispatcher's own argv[0].
    saved = sys.argv[0]
    sys.argv[0] = f"dra {name}"
    try:
        return module.main(argv[1:])
    finally:
        sys.argv[0] = saved


if __name__ == "__main__":
    raise SystemExit(main())

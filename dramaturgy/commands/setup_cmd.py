#!/usr/bin/env python3
"""setup.py — initialize ``.dramaturgy/config.json``.

Sets ``ui_lang`` (CLI/HTML chrome language) and ``content_lang`` (language
of the generated meaning map) plus project metadata. Both languages are
independent and may be mixed (e.g. ui_lang=ja, content_lang=en).

Values come from CLI args; any value not supplied is asked interactively
(unless --no-input). An existing config is respected and only missing
fields are filled.

Examples
--------
    python tools/meaning_map/setup.py \
      --ui-lang ja --content-lang ja \
      --project-name "My System" --repo-root .
"""

from __future__ import annotations

import argparse
import sys


from ..common import DEFAULT_LANG, SUPPORTED_LANGS  # noqa: E402
from ..common.config import Config, load_config, save_config  # noqa: E402
from ..common.i18n import Catalog  # noqa: E402


def _prompt(cat: Catalog, key: str, default: str, no_input: bool, **fmt) -> str:
    if no_input:
        return default
    raw = input(cat.t(key, default=default, **fmt)).strip()
    return raw or default


def _prompt_lang(cat: Catalog, key: str, default: str, no_input: bool) -> str:
    choices = "/".join(SUPPORTED_LANGS)
    while True:
        val = _prompt(cat, key, default, no_input, choices=choices)
        if val in SUPPORTED_LANGS:
            return val
        print(cat.t("setup.invalid_lang", lang=val, choices=choices))
        if no_input:
            return default


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Initialize meaning-map config")
    parser.add_argument("--ui-lang", choices=SUPPORTED_LANGS, default=None)
    parser.add_argument("--content-lang", choices=SUPPORTED_LANGS, default=None)
    parser.add_argument("--project-name", default=None)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument(
        "--no-input", action="store_true",
        help="do not prompt; use args/existing/defaults only",
    )
    args = parser.parse_args(argv)

    repo_root = args.repo_root
    existing = load_config(repo_root)
    # Bootstrap catalog uses the best-known ui_lang so even the setup
    # prompts are localized: arg > existing config > default.
    boot_ui = args.ui_lang or (existing.ui_lang if existing else DEFAULT_LANG)
    cat = Catalog(boot_ui, domain="cli")

    print(cat.t("setup.start"))
    if existing:
        print(cat.t("setup.exists"))

    base = existing or Config(repo_root=repo_root)

    ui_lang = args.ui_lang or _prompt_lang(
        cat, "setup.prompt_ui_lang", base.ui_lang, args.no_input
    )
    # Re-localize remaining prompts to the chosen ui_lang.
    cat = Catalog(ui_lang, domain="cli")
    content_lang = args.content_lang or _prompt_lang(
        cat, "setup.prompt_content_lang", base.content_lang, args.no_input
    )
    project_name = args.project_name or _prompt(
        cat, "setup.prompt_project_name", base.project_name, args.no_input
    )
    repo_root = _prompt(
        cat, "setup.prompt_repo_root", base.repo_root or repo_root, args.no_input
    )

    cfg = Config(
        ui_lang=ui_lang,
        content_lang=content_lang,
        project_name=project_name,
        repo_root=repo_root,
    )
    try:
        path = save_config(cfg, repo_root)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(cat.t("setup.created", path=str(path)))
    print(cat.t("setup.summary",
                ui_lang=ui_lang, content_lang=content_lang, name=project_name))
    return 0

"""Read/write ``.meaning-map/config.json`` and resolve language settings.

The config is the source of truth for ``ui_lang`` / ``content_lang`` and
project metadata. Every CLI accepts ``--ui-lang`` / ``--content-lang`` to
override per-invocation; resolution order is:

    explicit CLI arg  >  config.json value  >  built-in default

This module also wires up a :class:`~common.i18n.Catalog` from the
resolved ``ui_lang`` so a tool can grab localized strings in one call.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import DEFAULT_LANG, SUPPORTED_LANGS
from .i18n import Catalog
from .paths import config_path, read_json, write_json

SCHEMA_VERSION = 1


@dataclass
class Config:
    ui_lang: str = DEFAULT_LANG
    content_lang: str = DEFAULT_LANG
    project_name: str = ""
    repo_root: str = "."
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "ui_lang": self.ui_lang,
            "content_lang": self.content_lang,
            "project": {
                "name": self.project_name,
                "repo_root": self.repo_root,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Config":
        project = data.get("project", {}) or {}
        return cls(
            ui_lang=data.get("ui_lang", DEFAULT_LANG),
            content_lang=data.get("content_lang", DEFAULT_LANG),
            project_name=project.get("name", ""),
            repo_root=project.get("repo_root", "."),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
        )

    def validate(self) -> None:
        for label, lang in (("ui_lang", self.ui_lang), ("content_lang", self.content_lang)):
            if lang not in SUPPORTED_LANGS:
                raise ValueError(
                    f"unsupported {label}={lang!r}; supported: {SUPPORTED_LANGS}"
                )


def load_config(repo_root: str | Path = ".") -> Config | None:
    path = config_path(repo_root)
    if not path.exists():
        return None
    return Config.from_dict(read_json(path))


def save_config(cfg: Config, repo_root: str | Path = ".") -> Path:
    cfg.validate()
    path = config_path(repo_root)
    write_json(path, cfg.to_dict())
    return path


@dataclass
class Resolved:
    """Resolved runtime settings for a single CLI invocation."""

    ui_lang: str
    content_lang: str
    config: Config
    ui: Catalog = field(init=False)

    def __post_init__(self):
        self.ui = Catalog(self.ui_lang, domain="cli")


def add_lang_args(parser: argparse.ArgumentParser, *, content: bool = True) -> None:
    """Attach the standard language override flags to a parser."""
    parser.add_argument(
        "--ui-lang", choices=SUPPORTED_LANGS, default=None,
        help="language for CLI/HTML chrome (defaults to config.json)",
    )
    parser.add_argument(
        "--repo-root", default=None,
        help="repository root (defaults to config.json or '.')",
    )
    if content:
        parser.add_argument(
            "--content-lang", choices=SUPPORTED_LANGS, default=None,
            help="language of the generated meaning-map content "
                 "(defaults to config.json)",
        )


def resolve(args: argparse.Namespace) -> Resolved:
    """Resolve languages from CLI args + config, with built-in fallback."""
    repo_root = getattr(args, "repo_root", None) or "."
    cfg = load_config(repo_root) or Config(repo_root=repo_root)
    # repo_root precedence: explicit arg > config value > "."
    if getattr(args, "repo_root", None):
        cfg.repo_root = args.repo_root
    ui_lang = getattr(args, "ui_lang", None) or cfg.ui_lang
    content_lang = getattr(args, "content_lang", None) or cfg.content_lang
    resolved = Resolved(ui_lang=ui_lang, content_lang=content_lang, config=cfg)
    return resolved

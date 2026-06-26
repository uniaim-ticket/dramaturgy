"""Message-catalog loader for UI/CLI strings.

UI/CLI text is never hard-coded in tool logic. Each supported language has
a flat ``key -> string`` catalog under ``catalogs/cli/<lang>.json``. Tools
resolve strings through :class:`Catalog`, which formats with ``str.format``.

The HTML chrome catalog lives under ``catalogs/html/<lang>.json`` and is
loaded the same way (``domain="html"``).

Adding a new language = adding catalog files; no code change needed.
``validate_catalogs`` checks that every language has the same key set as
the reference language so translations can't silently drift.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import DEFAULT_LANG, SUPPORTED_LANGS

CATALOG_ROOT = Path(__file__).resolve().parent.parent / "catalogs"


class Catalog:
    """Resolves message keys for one language and domain (cli|html)."""

    def __init__(self, lang: str, domain: str = "cli"):
        if lang not in SUPPORTED_LANGS:
            raise ValueError(
                f"unsupported lang {lang!r}; supported: {SUPPORTED_LANGS}"
            )
        self.lang = lang
        self.domain = domain
        self._messages = _load_catalog(lang, domain)
        # Fall back to the default language for any missing key so a
        # partial translation degrades gracefully instead of crashing.
        self._fallback = (
            _load_catalog(DEFAULT_LANG, domain) if lang != DEFAULT_LANG else {}
        )

    def t(self, key: str, **kwargs) -> str:
        msg = self._messages.get(key)
        if msg is None:
            msg = self._fallback.get(key, key)
        try:
            return msg.format(**kwargs) if kwargs else msg
        except (KeyError, IndexError):
            # A malformed placeholder should not crash a CLI run.
            return msg

    # Convenience alias.
    __call__ = t

    def as_dict(self) -> dict[str, str]:
        return dict(self._messages)


def _catalog_file(lang: str, domain: str) -> Path:
    return CATALOG_ROOT / domain / f"{lang}.json"


def _load_catalog(lang: str, domain: str) -> dict[str, str]:
    path = _catalog_file(lang, domain)
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def validate_catalogs(domain: str = "cli") -> list[str]:
    """Return a list of human-readable problems with the catalogs.

    Checks, against the default language as the reference key set:
    - missing keys per language
    - extra keys per language
    An empty list means the catalogs are consistent.
    """
    problems: list[str] = []
    reference = _load_catalog(DEFAULT_LANG, domain)
    if not reference:
        problems.append(
            f"[{domain}] reference catalog for '{DEFAULT_LANG}' is missing or empty"
        )
        return problems
    ref_keys = set(reference)
    for lang in SUPPORTED_LANGS:
        if lang == DEFAULT_LANG:
            continue
        cat = _load_catalog(lang, domain)
        if not cat:
            problems.append(f"[{domain}] catalog for '{lang}' is missing or empty")
            continue
        keys = set(cat)
        for k in sorted(ref_keys - keys):
            problems.append(f"[{domain}/{lang}] missing key: {k}")
        for k in sorted(keys - ref_keys):
            problems.append(f"[{domain}/{lang}] extra key: {k}")
    return problems

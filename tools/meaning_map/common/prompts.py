"""Load language-specific prompt templates.

Templates live under ``prompts/<name>.<content_lang>.md`` and use
``str.format``-style ``{placeholder}`` slots. Templates are maintained per
language at equal instruction density (see rfp.md); a missing template is
an error rather than a silent fallback, so a half-translated prompt set is
caught early.
"""

from __future__ import annotations

from pathlib import Path

PROMPT_ROOT = Path(__file__).resolve().parent.parent / "prompts"


def prompt_path(name: str, content_lang: str) -> Path:
    return PROMPT_ROOT / f"{name}.{content_lang}.md"


def load_prompt(name: str, content_lang: str) -> str:
    path = prompt_path(name, content_lang)
    if not path.exists():
        raise FileNotFoundError(str(path))
    return path.read_text(encoding="utf-8")


def render_prompt(name: str, content_lang: str, **slots) -> str:
    template = load_prompt(name, content_lang)
    # Use a defaultdict-like format so missing slots become empty rather
    # than raising; callers pass everything they have.
    class _Safe(dict):
        def __missing__(self, key):  # noqa: D401
            return "{" + key + "}"

    return template.format_map(_Safe(slots))

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
    # Substitute ONLY the known ``{slot}`` placeholders via literal
    # replacement. We intentionally do NOT use str.format, because the
    # templates contain literal JSON examples with their own ``{ }`` that
    # must pass through untouched (str.format would try to parse them).
    for key, value in slots.items():
        template = template.replace("{" + key + "}", str(value))
    return template

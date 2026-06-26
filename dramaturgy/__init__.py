"""dramaturgy — generate a compact, human-readable meaning map of a large
system, driven from inside Claude Code.

CLIs gather material and run mechanical checks; Claude makes the semantic
judgments. Bilingual by design: ``ui_lang`` (CLI/HTML chrome) and
``content_lang`` (generated content + prompts) are independent and may be
mixed. See README.md / rfp.md.
"""

__version__ = "0.1.0"

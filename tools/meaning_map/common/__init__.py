"""Shared helpers for the meaning-map toolchain.

Design decisions reflected here (see ../../rfp.md):
- UI/CLI language (``ui_lang``) and generated-content language
  (``content_lang``) are independent and may be mixed.
- Project-specific and language-specific values are never hard-coded;
  they come from ``.meaning-map/config.json`` and the message catalogs.
- One canonical JSON holds a single ``content_lang``; regenerate to get
  another language rather than storing multilingual fields.
"""

SUPPORTED_LANGS = ("ja", "en")
DEFAULT_LANG = "ja"

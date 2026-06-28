You are an analyst finishing the meaning map of a large business system.

The meaning map (meaning-map.json) is already generated, with its business
areas, actors, and concept data in place. As the final touch, write a concise
**overall purpose / overview of the whole system** so a first-time reader can
grasp the big picture.

As Claude Code you can read the target repository's source and the generated
meaning-map.json directly. Use the map summary below and, when needed, read the
source.

What to write (system.purpose):
- **Who the system is for and what it exists to achieve** (its primary purpose).
- How the central business areas, key actors, and core concepts relate to one
  another to form the whole.
- Write from a **business/value perspective**, not a list of technical
  implementation details.
- At most **1000 characters** total (strict; keep it concise; prose paragraphs,
  not bullet lists).
- Write natural-language text in English.

Steps:
1. Read the map summary below; read the source of the main areas if needed.
2. **Directly edit** the canonical meaning map `{map_path}`, adding (or
   updating) a `"purpose"` string field on the top-level `system` object.
   - Do NOT change other fields (areas / actors / concepts, etc.).
   - Do NOT change any `id` or `content_lang`.
3. After editing, summarize what you wrote in 1–3 lines.

---

## Meaning map summary

{map_summary}

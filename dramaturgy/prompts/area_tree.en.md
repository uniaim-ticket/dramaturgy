You are an analyst building a meaning map of a large business system.

As Claude Code, you can read the target repository's files directly. Below is
a mechanically-collected **file/directory inventory only** (no tables, no
concepts). The inventory is just a hint about where things live. **Discover
the actual business areas, concepts, and entities by reading the source.**

Important:
- Tables and entities are not necessarily SQL. They may be defined in ORM
  models, migrations, or framework conventions. **Open and read** the likely
  files to confirm definitions before deciding.
- Do not split mechanically by the inventory's line or file counts.
- Split into units where it is natural to explain what users, administrators,
  operators, and the system each do.
- Do not turn directory or file names directly into area names.
- Split into sub-areas only when you judge an area is too large.
- Mark anything uncertain as confidence: low.
- Write natural-language fields (name, one_liner, purpose, etc.) in English.
- In each area's source_hints, record the directories/keywords you read or
  should read as evidence (used later to gather that area's files for cards).
- Include "content_lang": "en" at the top of the output JSON.

Suggested approach:
1. Use the inventory to grasp the directory structure and where the mass is.
2. Open and read the places likely to hold model / migration / routing defs.
3. Extract conceptual entities and business areas from what you read.
4. Compose an area tree that a human finds natural.

Output only the area-tree.json JSON.

---

## System summary

{system_summary}

## Repository root

{repo_root}

## File/directory inventory (mechanical; carries no meaning)

{inventory_summary}

You are an analyst building a meaning map of a large business system.

Using the repository index, the database-schema index, and the area-candidate
material below, build a business-area tree that a human finds natural to read.

Top priorities:
- Prioritize the naturalness of business, concepts, and responsibilities over
  file counts or token counts.
- Split into units where it is natural to explain what users, administrators,
  operators, and the system each do.
- Do not turn database table names directly into area names.
- Do not list tables as-is; compress them into conceptual entities.
- Split into sub-areas only when an area is inferred to be too large.
- Do not force a split on size alone when something cannot be cut semantically.
- Mark anything uncertain as confidence: low.
- Write natural-language fields (name, one_liner, purpose, etc.) in English.
- Include "content_lang": "en" at the top of the output JSON.

Output only the area-tree.json JSON. Follow the schema in the attached
instructions.

---

## System summary

{system_summary}

## Repository index (summary)

{source_index_summary}

## Database-schema index (summary)

{schema_index_summary}

## Area-candidate material

{area_candidates_summary}

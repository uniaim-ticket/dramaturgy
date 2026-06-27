You are an analyst building a meaning map of an existing business system.

The following is an area that has already been carved out as a unit that is
natural in business and conceptual terms.

For this area, generate an area card that is easy for both users and
developers to understand.

The goal is not to write a detailed specification.
A human should be able to grasp the meaning of this area quickly and, when
needed, drill down into the code, database, and APIs.

As Claude Code, you can read the target repository's files directly. The
analysis pack below is **a list of files likely related to this area** (tables
and APIs are NOT pre-extracted). **Open and read the listed files** to confirm
the tables/entities, APIs, screens, flows, and state transitions. Tables are
not necessarily SQL — they may be defined in ORM models, migrations, or
framework conventions, so judge from the file contents.

Always organize the following:

- Area name
- One-liner
- Purpose
- Actions per actor
- Key concepts
- Key flows
- CRUD summary
- Related database tables
- Related APIs
- Related screens
- Related code
- State transitions
- Risk points
- open_questions
- confidence

Notes:
- Do not cram too much implementation detail into the body.
- However, keep references to the supporting code, database, and APIs.
- Separate inference from evidence.
- Write natural-language fields in English and include "content_lang": "en".
- Output JSON only.

---

## Target area

{area_summary}

## Analysis pack

{area_pack}

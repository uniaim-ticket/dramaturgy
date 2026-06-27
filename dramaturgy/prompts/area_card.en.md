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

Concept data (important):
- Do not list physical tables (real DB tables / ORM models) directly.
  Compress them into **concept data** by business meaning (e.g. physical
  `orders` + `order_items` + `order_status_histories` → concept "Order").
- For each concept, list the supporting **physical table names in
  physical_tables**.
- Declare what this area does to each concept as **concept_crud** (ops is a
  subset of "C"/"R"/"U"/"D", e.g. "CRU"). CRUD is expressed per concept data.
- Add system-specific **tags** to each concept (e.g. the master vs.
  transaction distinction). Prefer the tag vocabulary below if present; add new
  tags when useful.

Tag vocabulary (system-specific):
{tag_vocabulary}

Classifications (important):
- Sets of allowed values like "point-grant method", "mail kind", "cancel
  code" are NOT concept data — putting them in `concepts` bloats it. Put them
  in **classifications** instead.
- If a classification is a detail of a concept (an attribute's value set),
  link it via `concept_id`. If it is a standalone premise of business logic,
  set `concept_id` to null.
- List representative `values: [{code, label}]` (need not be exhaustive).

Actors vs. components (important):
- Give each actor a **category**:
  - `person`: a business actor (visitor, operator, shop staff …; include
    things that aren't strictly people but are natural to treat as actors in
    the business flow);
  - `system`: an external system/terminal treated as an actor in the flow
    (payment provider, external member system, gate terminal, vending
    machine …).
- Structural pieces that are NOT business actors — load balancers, monitoring,
  cross-cutting middleware — go in **components**, not actors.

Overview business flow (important):
- Give the area one **overview-level business flow that someone who has never
  used the system can follow**. Omit detailed branches/exceptions; show only
  the main path in ~5–9 steps.
- Use a **swimlane** shape: `lanes` is the ordered list of involved actors
  (vertical lanes, by actor_id); each `steps` entry is
  `{lane: <actor_id>, label: "short action"}`, in the order things happen.
- Lanes must use actor ids (people/actors, not components).
- Detailed step lists can still go in `flows`; overview_flow is the summary.

Output area-map JSON shape (for this area):

```json
{
  "content_lang": "en",
  "areas": [{
    "id": "<this area id>",
    "name": "", "one_liner": "", "purpose": "",
    "parent_area_id": null, "child_area_ids": [], "related_area_ids": [],
    "actors": [{"actor_id": "", "actions": [""]}],
    "concepts": ["<concept_id>"],
    "concept_crud": [{"concept_id": "<concept_id>", "ops": "CRUD"}],
    "overview_flow": {
      "title": "<name of this area's overview flow>",
      "lanes": ["<actor_id>", "<actor_id>"],
      "steps": [{"lane": "<actor_id>", "label": "<short action>"}]
    },
    "flows": [{"name": "", "steps": [""]}],
    "apis": [""], "screens": [""], "code_refs": ["path/to/file"],
    "risk_points": [""], "open_questions": [""],
    "confidence": "high|medium|low"
  }],
  "concepts": [{
    "id": "<concept_id>", "name": "", "description": "", "kind": "entity|state|event|value_object|external_system",
    "physical_tables": ["<physical table/model name>"],
    "tags": ["<system-specific tag>"],
    "states": [""], "code_refs": [""], "confidence": "high|medium|low"
  }],
  "classifications": [{
    "id": "<classification_id>", "name": "", "description": "",
    "concept_id": "<related concept id, or null>",
    "values": [{"code": "", "label": ""}],
    "code_refs": [""], "confidence": "high|medium|low"
  }],
  "actors": [{"id": "", "name": "", "description": "", "category": "person|system",
    "actions": [{"area_id": "", "action": "", "description": ""}]}],
  "components": [{
    "id": "", "name": "", "description": "", "kind": "infrastructure|middleware|external",
    "code_refs": [""], "confidence": "high|medium|low"
  }],
  "flows": []
}
```

Notes:
- Do not cram too much implementation detail into the body.
- However, keep references to the supporting code/tables (physical_tables,
  code_refs).
- Separate inference from evidence.
- crud_by_area / related_areas are generated automatically on merge, so you
  need not write them — only get this area's concept_crud right.
- Write natural-language fields in English and include "content_lang": "en".
- Output JSON only.

---

## Target area

{area_summary}

## Analysis pack

{area_pack}

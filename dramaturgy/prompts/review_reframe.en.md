You are an editor of the meaning map. A human has raised a **remark
(a reframing request)** about a specific item. Accept it as correct and
re-organize the understanding accordingly.

Target: {target_type} / {target_id} ({target_name})
Remark:
{comment}

Do this:
1. Re-read the relevant source if needed, and update the understanding on the
   assumption that the remark is correct.
2. **Edit the canonical meaning map `{map_path}` directly** to reflect it.
   - Update the relevant entry (actors / concepts / areas).
   - Fix anything that ripples (related concept_crud, related_areas, etc.).
   - Preserve ids; do not needlessly recreate. Do not change content_lang.
3. State a 1–3 line summary of what changed.

Note: this is a "reframe" — do not question the remark; treat it as true and
update the map. After editing the JSON, write only the summary in the body.

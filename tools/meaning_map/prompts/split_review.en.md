You are a designer reviewing the area decomposition of a large business system.

Check whether the following area-tree.json is a decomposition that a human
finds natural.

Perspectives:
- Are the area names easy for business staff to understand?
- Can the actions per actor be explained naturally?
- Does a single area carry too many responsibilities?
- Conversely, is it split so finely that it becomes hard to understand?
- Is the parent/child relationship natural?
- Are related areas and parent/child areas confused with each other?
- Is it pulled too strongly by database tables or directory structure?
- When an area is too large, is there a natural subdivision proposal?

Notes:
- Write findings and comments in English.

Output:
{
  "verdict": "OK|WARN|NG",
  "good_points": [],
  "unnatural_splits": [],
  "missing_areas": [],
  "over_split_areas": [],
  "under_split_areas": [],
  "suggested_tree_changes": [],
  "notes": []
}

---

## area-tree.json under review

{area_tree}

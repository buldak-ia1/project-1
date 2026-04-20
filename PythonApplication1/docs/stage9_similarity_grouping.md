# MetaSort Stage 9 Similarity Grouping

## Scope

- Group images inside the same non-similarity category path.
- Detect `exact_duplicate`, `near_duplicate`, and `unique` groups.
- Select a representative image for each group.

## Current Behavior

- Images are bucketed by the classification path excluding the `similarity` axis.
- `exact_duplicate` groups are based on identical `sha256`.
- `near_duplicate` groups are built from perceptual hash and difference hash Hamming distance.
- `unique` is assigned when an image does not join a duplicate cluster.
- Representative images prefer fewer issues, larger resolution, and larger file size.
- If the policy contains a `similarity` axis, its category label is updated with the group label.
- Stage-level counts are saved to `ProjectRun.summary["grouping"]`.

## Demo Notes

- The two sample PNG files currently fall into the same near-duplicate group because their pHash and dHash match.
- `report.csv` now includes `group_id`, `group_type`, and `representative_image_id`.

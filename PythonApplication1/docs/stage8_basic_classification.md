# MetaSort Stage 8 Basic Classification

## Scope

- Apply the configured policy axes to each image.
- Implement baseline classifiers for safety, character, and model.
- Save per-image classification results for later grouping and folder organization.

## Current Behavior

- `safety` uses prompt and negative-prompt keyword matching to assign `SFW` or `NSFW`.
- `character` uses configured prompt keyword groups such as `Miku`.
- `model` uses normalized model metadata with optional alias mapping.
- `resolution`, `prompt_family`, and `similarity` produce deterministic placeholder categories when selected as policy axes.
- Per-image results are stored in `ImageFile.category_results`.
- Stage-level counts are saved to `ProjectRun.summary["classification"]`.

## Demo Notes

- The default policy still uses `safety -> character -> similarity`, so the demo now emits three category results per valid image.
- `report.csv` now includes `category_path` and `category_results` columns.

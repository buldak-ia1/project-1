# MetaSort Stage 1 Data Model

## Core Entities

- `ProjectRun`: one execution record that owns the policy, scanned images, generated groups, logs, and summary.
- `ClassificationPolicy`: run-time sorting policy containing execution mode, thresholds, handling rules, and ordered classification axes.
- `ImageFile`: canonical record for each discovered image file.
- `RawMetadata`: original metadata extracted from PNG text, EXIF, or other containers.
- `NormalizedMetadata`: standardized metadata used by later classifiers.
- `ImageFeature`: perceptual hashes and optional embedding-based features.
- `ImageCategoryResult`: per-axis classification output for an image.
- `ImageGroup`: grouped result inside a classified category path.
- `GroupMember`: membership record for an image inside a group.
- `OutputLog`: execution log entry with optional image-level context.

## Relationship Summary

- `ProjectRun` 1:N `ImageFile`
- `ProjectRun` 1:1 `ClassificationPolicy`
- `ProjectRun` 1:N `ImageGroup`
- `ProjectRun` 1:N `OutputLog`
- `ImageFile` 1:0..1 `RawMetadata`
- `ImageFile` 1:0..1 `NormalizedMetadata`
- `ImageFile` 1:0..1 `ImageFeature`
- `ImageFile` 1:N `ImageCategoryResult`
- `ImageGroup` 1:N `GroupMember`

## Stage 1 Design Decisions

- Raw metadata is stored separately from normalized metadata so extraction logic can evolve without data loss.
- Classification is modeled as ordered axes so the future organizer can build nested folder paths from the same structure.
- Grouping is independent from file records so multiple grouping strategies can be swapped in later.
- `ProjectRun.to_dict()` serializes dataclasses, `datetime`, and path-like values into JSON-safe data for reports and manifests.

# MetaSort Stage 10 Output Organization

## Scope

- Create the final `Sorted/` folder structure from category and group labels.
- Copy files into organized folders when the execution mode is `copy`.
- Save an output manifest that records source and destination paths.

## Current Behavior

- Images are written to `demo_output/Sorted/<axis1>/<axis2>/<axis3>/filename.ext`.
- `copy` mode performs filesystem copies with metadata preservation via `copy2`.
- `analyze_only` mode skips file writes but still records planned output paths in `manifest.json`.
- `move` mode is deferred to stage 11 and is logged without moving files.
- `manifest.json` is created in the output root with one record per image.
- Stage-level counts are saved to `ProjectRun.summary["organization"]`.

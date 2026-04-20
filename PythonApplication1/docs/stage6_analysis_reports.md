# MetaSort Stage 6 Analysis Reports

## Scope

- Export analysis results into human-readable report files.
- Generate a CSV table for per-image inspection.
- Generate a JSON summary file for run-level statistics and stage summaries.

## Current Behavior

- `report.csv` is written to the configured `output_root`.
- `summary.json` is written to the configured `output_root`.
- CSV rows include scan info, normalized metadata, feature hashes, and issue flags.
- JSON summary includes run metadata, image/group counts, extension counts, issue counts, and accumulated stage summaries.
- Generated report paths are saved to `ProjectRun.summary["reports"]`.

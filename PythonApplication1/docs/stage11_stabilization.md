# MetaSort Stage 11 Stabilization

## Scope

- Support `move` mode in the organizer.
- Save `run.log` alongside the CSV and JSON reports.
- Improve output-stage resilience for file operation failures and name collisions.

## Current Behavior

- `copy`, `move`, and `analyze_only` are now handled in the organizer.
- Existing `Sorted/` output is cleared safely before a new run to avoid stale files.
- File name collisions inside the same output folder are renamed with numeric suffixes and logged.
- File operation failures are recorded per image in both `issues` and `manifest.json`.
- `run.log` contains the chronological execution log with structured context payloads.
- The demo dataset intentionally creates a collision case with two `miku_001.png` files.

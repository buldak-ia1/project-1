# MetaSort Stage 7 Policy Configuration

## Scope

- Load classification policy from an external JSON file.
- Support configuration of up to three ordered classification axes.
- Configure execution mode, thresholds, and unknown-handling rules outside the code.

## Current Behavior

- `config/classification_policy.json` is the default policy source.
- The policy manager creates the file automatically if it is missing.
- Enabled axes must have consecutive priorities starting at `1`.
- A maximum of three enabled axes is supported.
- Duplicate enabled criteria are rejected.
- `execution_mode`, `unclassified_handling`, and `metadata_missing_handling` are validated against enum values.

## Demo Notes

- The main script now loads the policy file before building `ProjectRun`.
- You can change axis order, thresholds, or handling rules by editing the JSON config directly.

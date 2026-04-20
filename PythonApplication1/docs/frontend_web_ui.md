# MetaSort Frontend Web UI

## Scope

- Provide a browser-based local control panel for MetaSort.
- Allow users to trigger runs, inspect summaries, and preview outputs without editing Python code.

## Current Behavior

- `MetaSortWeb.py` starts a local HTTP server on `127.0.0.1:8765`.
- The frontend supports source/output/policy path input, an execution-mode selector, and a demo-input toggle.
- Demo mode always regenerates the project-local `demo_input` tree and ignores any typed `Source Root`.
- `POST /api/run` executes the full MetaSort pipeline and returns run data as JSON.
- Risky path combinations such as identical or nested source/output roots are rejected with a 4xx response.
- `GET /api/state` loads the latest in-memory run or the existing `demo_output` snapshot.
- The page renders summary metrics, classification breakdown, grouping stats, manifest preview, run log preview, and a CSV preview table.

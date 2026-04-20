# MetaSort External Model Integration

## Scope

- Add an optional external image-embedding backend.
- Fall back to the local heuristic embedding when the external runtime is unavailable.

## Current Behavior

- `extra_rules.external_model` controls whether an external backend is requested.
- Supported provider in the current implementation is `transformers_clip` with `auto` selection.
- If `torch`, `transformers`, and `PIL` are installed, MetaSort can load `model_id` and use image embeddings from the external model.
- If the runtime or model is unavailable, MetaSort logs a warning and keeps using the local heuristic embedding.
- Feature summary now reports requested provider, active backend, and how many embeddings came from external vs local sources.

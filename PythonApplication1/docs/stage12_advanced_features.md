# MetaSort Stage 12 Advanced Features

## Scope

- Add style classification support.
- Extract lightweight visual embedding vectors for richer similarity checks.
- Extend grouping beyond near-duplicate detection.

## Current Behavior

- The classifier now supports the `style` criterion through configurable prompt keywords and feature tags.
- Feature extraction now stores an 8-dimensional embedding vector plus scene/style tags.
- Similarity grouping now recognizes `same_prompt_family`, `same_model_series`, and `visual_similar` in addition to existing duplicate groups.
- CSV reports expose `embedding_dimensions` so embedding availability is visible in exports.
- Policy `extra_rules` includes `style_keywords`, `prompt_family_threshold`, and `visual_similarity_threshold`.

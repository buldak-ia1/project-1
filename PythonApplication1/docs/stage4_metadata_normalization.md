# MetaSort Stage 4 Metadata Normalization

## Scope

- Convert `RawMetadata` into a standard `NormalizedMetadata` structure.
- Populate common fields such as prompt, negative prompt, seed, sampler, steps, CFG scale, model, software, width, and height.
- Preserve context that does not map cleanly into standard fields in `NormalizedMetadata.extra`.

## Current Behavior

- Text values from PNG text and EXIF are flattened into a common lookup map.
- `parameters`-style strings are parsed heuristically for prompt and `Negative prompt`.
- Inline labels such as `Steps`, `Sampler`, `CFG scale`, `Seed`, and `Model` are extracted from text.
- Image width and height from the scan stage are copied into normalized metadata.
- Stage-level counters are saved to `ProjectRun.summary["normalization"]`.

## Demo Notes

- Demo PNG metadata now includes structured `parameters` text so normalized fields can be seen directly in the JSON output.

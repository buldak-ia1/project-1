# Style and Character Classification

## Behavior

- The default policy now organizes images by `Style -> Character -> Similarity`.
- Style classification first uses normalized `artist` metadata.
- If `artist` is missing or `null`, MetaSort clusters similar style prompt tokens into `StyleFamily_###`.
- Character classification still honors configured character keywords first.
- Character classification reads normalized character prompts such as `char_caption`, `char_prompts`, `character_prompt`, and nested NovelAI v4 `char_captions`.
- If no configured character keyword matches, MetaSort clusters similar character prompt tokens and names the folder with a natural Korean descriptor such as `은발푸른눈소녀`; it falls back to the main prompt only when character prompts are missing.

## Safety

- This feature only changes category labels and output folder paths.
- It does not modify source images.
- First-run execution mode remains `analyze_only`.

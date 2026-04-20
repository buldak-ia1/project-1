from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from .models import NormalizedMetadata, OutputLog, ProjectRun, RawMetadata

FLOAT_PATTERN = r"[-+]?\d+(?:\.\d+)?"
INT_PATTERN = r"[-+]?\d+"


@dataclass(slots=True)
class NormalizationStats:
    normalized_images: int = 0
    skipped_without_raw_metadata: int = 0
    prompt_images: int = 0
    model_images: int = 0
    software_images: int = 0
    artist_images: int = 0
    character_prompt_images: int = 0


class MetadataNormalizer:
    def normalize(self, project_run: ProjectRun) -> ProjectRun:
        stats = NormalizationStats()

        for image in project_run.images:
            if image.raw_metadata is None:
                stats.skipped_without_raw_metadata += 1
                continue

            normalized = self._normalize_metadata(image.raw_metadata, image.width, image.height)
            image.normalized_metadata = normalized
            stats.normalized_images += 1
            if normalized.prompt:
                stats.prompt_images += 1
            if normalized.model:
                stats.model_images += 1
            if normalized.software:
                stats.software_images += 1
            if normalized.artist:
                stats.artist_images += 1
            if normalized.character_prompts:
                stats.character_prompt_images += 1

        project_run.summary["normalization"] = {
            "normalized_images": stats.normalized_images,
            "skipped_without_raw_metadata": stats.skipped_without_raw_metadata,
            "prompt_images": stats.prompt_images,
            "model_images": stats.model_images,
            "software_images": stats.software_images,
            "artist_images": stats.artist_images,
            "character_prompt_images": stats.character_prompt_images,
        }
        project_run.logs.append(
            OutputLog(
                timestamp=project_run.started_at,
                level="INFO",
                message="Metadata normalization stage completed.",
                context=project_run.summary["normalization"],
            )
        )
        return project_run

    def _normalize_metadata(
        self, raw_metadata: RawMetadata, width: int | None, height: int | None
    ) -> NormalizedMetadata:
        text_map = self._flatten_text_map(raw_metadata)
        parameters_text = self._pick_first_value(
            text_map,
            "parameters",
            "prompt",
            "description",
            "imagedescription",
            "usercomment",
        )
        comment_text = self._pick_first_value(
            text_map,
            "comment",
            "xpcomment",
            "notes",
        )

        prompt, negative_prompt = self._extract_prompt_and_negative(parameters_text)
        character_prompts = self._extract_character_prompts(text_map, parameters_text, comment_text)
        software = self._pick_first_value(text_map, "software")
        model = self._pick_first_value(text_map, "model")
        sampler = self._pick_first_value(text_map, "sampler")

        steps = self._parse_int_from_sources(
            ("steps",),
            text_map,
            parameters_text,
            comment_text,
        )
        seed = self._parse_int_from_sources(
            ("seed",),
            text_map,
            parameters_text,
            comment_text,
        )
        cfg_scale = self._parse_float_from_sources(
            ("cfg scale", "cfg_scale", "cfg"),
            text_map,
            parameters_text,
            comment_text,
        )

        if sampler is None:
            sampler = self._parse_string_from_sources(
                ("sampler",),
                text_map,
                parameters_text,
                comment_text,
            )
        if model is None:
            model = self._parse_string_from_sources(
                ("model",),
                text_map,
                parameters_text,
                comment_text,
            )
        if software is None:
            software = self._parse_string_from_sources(
                ("software",),
                text_map,
                parameters_text,
                comment_text,
            )
        raw_artist = self._parse_string_from_sources(
            ("artist", "artists"),
            text_map,
            parameters_text,
            comment_text,
        )
        artist = self._clean_artist_value(raw_artist)

        extra = {
            "source_format": raw_metadata.source_format,
            "raw_text_keys": sorted(raw_metadata.raw_text.keys()),
        }
        if comment_text:
            extra["comment"] = comment_text
        if raw_artist is not None:
            extra["artist_raw"] = raw_artist
            extra["artist_is_null"] = artist is None
        style_signature = self._build_style_signature(prompt, artist)
        if style_signature:
            extra["style_signature"] = style_signature

        return NormalizedMetadata(
            prompt=prompt,
            negative_prompt=negative_prompt,
            character_prompts=character_prompts,
            seed=seed,
            sampler=sampler,
            steps=steps,
            cfg_scale=cfg_scale,
            model=model,
            software=software,
            artist=artist,
            width=width,
            height=height,
            extra=extra,
        )

    def _flatten_text_map(self, raw_metadata: RawMetadata) -> dict[str, str]:
        text_map: dict[str, str] = {}
        for source in (raw_metadata.raw_text, raw_metadata.png_text):
            for key, value in source.items():
                if isinstance(value, str) and value.strip():
                    text_map[key.lower()] = value.strip()

        self._collect_exif_text(raw_metadata.exif, text_map)
        return text_map

    def _collect_exif_text(self, source: dict[str, Any], output: dict[str, str]) -> None:
        for key, value in source.items():
            if isinstance(value, dict):
                self._collect_exif_text(value, output)
            elif isinstance(value, str) and value.strip():
                output[key.lower()] = value.strip()

    def _pick_first_value(self, text_map: dict[str, str], *keys: str) -> str | None:
        for key in keys:
            value = text_map.get(key.lower())
            if value:
                return value
        return None

    def _extract_prompt_and_negative(self, parameters_text: str | None) -> tuple[str | None, str | None]:
        if not parameters_text:
            return None, None

        text = parameters_text.strip()
        negative_match = re.search(
            r"Negative prompt:\s*(.*?)(?:\n(?:Steps|Sampler|CFG scale|Seed|Model|Size):|\Z)",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        negative_prompt = negative_match.group(1).strip() if negative_match else None

        prompt = text
        if negative_match:
            prompt = text[: negative_match.start()].strip()
        prompt = re.sub(
            r"\n?(?:Steps|Sampler|CFG scale|Seed|Model|Size):.*\Z",
            "",
            prompt,
            flags=re.IGNORECASE | re.DOTALL,
        ).strip()

        return (prompt or None, negative_prompt)

    def _extract_character_prompts(
        self,
        text_map: dict[str, str],
        *texts: str | None,
    ) -> list[str]:
        prompts: list[str] = []
        direct_keys = (
            "character_prompt",
            "character prompts",
            "character_prompts",
            "char_prompt",
            "char_prompts",
            "char_caption",
            "char_captions",
        )

        for key in direct_keys:
            direct_value = self._pick_first_value(text_map, key)
            if direct_value:
                self._append_prompt_value(prompts, direct_value)

        for value in list(text_map.values()) + [text for text in texts if text]:
            for payload in self._parse_json_candidates(value):
                self._collect_character_prompts_from_json(payload, prompts)

        return self._dedupe_prompts(prompts)

    def _parse_int_from_sources(
        self,
        labels: tuple[str, ...],
        text_map: dict[str, str],
        *texts: str | None,
    ) -> int | None:
        direct = self._pick_first_value(text_map, *labels)
        if direct is not None:
            parsed = self._coerce_int(direct)
            if parsed is not None:
                return parsed

        for text in texts:
            parsed = self._search_numeric_label(labels, text, as_float=False)
            if parsed is not None:
                return int(parsed)
        return None

    def _parse_float_from_sources(
        self,
        labels: tuple[str, ...],
        text_map: dict[str, str],
        *texts: str | None,
    ) -> float | None:
        direct = self._pick_first_value(text_map, *labels)
        if direct is not None:
            parsed = self._coerce_float(direct)
            if parsed is not None:
                return parsed

        for text in texts:
            parsed = self._search_numeric_label(labels, text, as_float=True)
            if parsed is not None:
                return parsed
        return None

    def _parse_string_from_sources(
        self,
        labels: tuple[str, ...],
        text_map: dict[str, str],
        *texts: str | None,
    ) -> str | None:
        direct = self._pick_first_value(text_map, *labels)
        if direct is not None:
            return direct

        for text in texts:
            parsed = self._search_string_label(labels, text)
            if parsed is not None:
                return parsed
        return None

    def _search_numeric_label(
        self,
        labels: tuple[str, ...],
        text: str | None,
        *,
        as_float: bool,
    ) -> float | None:
        if not text:
            return None

        number_pattern = FLOAT_PATTERN if as_float else INT_PATTERN
        for label in labels:
            pattern = re.compile(
                rf"{re.escape(label)}\s*[:=]\s*({number_pattern})",
                flags=re.IGNORECASE,
            )
            match = pattern.search(text)
            if match:
                return float(match.group(1))
        return None

    def _search_string_label(self, labels: tuple[str, ...], text: str | None) -> str | None:
        if not text:
            return None

        for label in labels:
            pattern = re.compile(
                rf"{re.escape(label)}\s*[:=]\s*([^\n,]+)",
                flags=re.IGNORECASE,
            )
            match = pattern.search(text)
            if match:
                return match.group(1).strip()
        return None

    def _coerce_int(self, value: str) -> int | None:
        match = re.search(INT_PATTERN, value)
        return int(match.group(0)) if match else None

    def _coerce_float(self, value: str) -> float | None:
        match = re.search(FLOAT_PATTERN, value)
        return float(match.group(0)) if match else None

    def _parse_json_candidates(self, text: str | None) -> list[Any]:
        if not text:
            return []
        stripped = text.strip()
        candidates = [stripped]
        first_object = stripped.find("{")
        last_object = stripped.rfind("}")
        if 0 <= first_object < last_object:
            candidates.append(stripped[first_object : last_object + 1])
        first_array = stripped.find("[")
        last_array = stripped.rfind("]")
        if 0 <= first_array < last_array:
            candidates.append(stripped[first_array : last_array + 1])

        payloads: list[Any] = []
        seen: set[str] = set()
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            try:
                payloads.append(json.loads(candidate))
            except json.JSONDecodeError:
                continue
        return payloads

    def _collect_character_prompts_from_json(self, value: Any, output: list[str]) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                normalized_key = key.lower().replace("-", "_").replace(" ", "_")
                if normalized_key in {
                    "char_caption",
                    "char_captions",
                    "char_prompt",
                    "char_prompts",
                    "character_prompt",
                    "character_prompts",
                }:
                    self._append_prompt_value(output, item)
                else:
                    self._collect_character_prompts_from_json(item, output)
        elif isinstance(value, list):
            for item in value:
                self._collect_character_prompts_from_json(item, output)

    def _append_prompt_value(self, output: list[str], value: Any) -> None:
        if isinstance(value, str):
            for prompt in re.split(r"\n+|\s*\|\s*", value):
                cleaned = re.sub(r"\s+", " ", prompt.strip(" ,;"))
                if cleaned:
                    output.append(cleaned)
        elif isinstance(value, dict):
            self._collect_character_prompts_from_json(value, output)
        elif isinstance(value, list):
            for item in value:
                self._append_prompt_value(output, item)

    def _dedupe_prompts(self, prompts: list[str]) -> list[str]:
        seen: set[str] = set()
        deduped: list[str] = []
        for prompt in prompts:
            key = prompt.casefold()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(prompt)
        return deduped

    def _clean_artist_value(self, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().strip("\"'[]{} ")
        if not cleaned or cleaned.lower() in {"null", "none", "unknown", "n/a"}:
            return None
        return re.sub(r"\s+", " ", cleaned)

    def _build_style_signature(self, prompt: str | None, artist: str | None) -> str | None:
        if artist:
            return f"artist:{artist.lower()}"
        if not prompt:
            return None
        tokens = re.findall(r"[a-z0-9_]+", prompt.lower())
        stopwords = {
            "best",
            "quality",
            "masterpiece",
            "high",
            "low",
            "girl",
            "boy",
            "solo",
            "portrait",
            "character",
        }
        signature_tokens = [token for token in tokens if len(token) > 2 and token not in stopwords]
        return " ".join(signature_tokens) or None

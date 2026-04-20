from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from .enums import ClassificationCriterion
from .models import ImageCategoryResult, OutputLog, PolicyAxis, ProjectRun


@dataclass(slots=True)
class ClassificationStats:
    processed_images: int = 0
    classified_images: int = 0


class CategoryClassifier:
    def classify(self, project_run: ProjectRun) -> ProjectRun:
        stats = ClassificationStats()
        criterion_counts: dict[str, Counter[str]] = defaultdict(Counter)
        context = self._build_classification_context(project_run)

        enabled_axes = sorted(
            (axis for axis in project_run.policy.axes if axis.enabled),
            key=lambda axis: axis.priority,
        )

        for image in project_run.images:
            stats.processed_images += 1
            image.category_results = []

            for axis in enabled_axes:
                result = self._classify_axis(axis, image, project_run, context)
                image.category_results.append(result)
                criterion_counts[axis.criterion.value][result.category_label] += 1

            if image.category_results:
                stats.classified_images += 1

        project_run.summary["classification"] = {
            "processed_images": stats.processed_images,
            "classified_images": stats.classified_images,
            "by_criterion": {
                criterion: dict(sorted(counter.items()))
                for criterion, counter in sorted(criterion_counts.items())
            },
            "auto_style_families": len(set(context["style_families"].values())),
            "auto_character_families": len(set(context["character_families"].values())),
        }
        project_run.logs.append(
            OutputLog(
                timestamp=project_run.started_at,
                level="INFO",
                message="Category classification stage completed.",
                context=project_run.summary["classification"],
            )
        )
        return project_run

    def _classify_axis(
        self,
        axis: PolicyAxis,
        image,
        project_run: ProjectRun,
        context: dict[str, dict[str, str]],
    ) -> ImageCategoryResult:
        if axis.criterion == ClassificationCriterion.SAFETY:
            return self._classify_safety(axis, image, project_run)
        if axis.criterion == ClassificationCriterion.CHARACTER:
            return self._classify_character(axis, image, project_run, context)
        if axis.criterion == ClassificationCriterion.STYLE:
            return self._classify_style(axis, image, project_run, context)
        if axis.criterion == ClassificationCriterion.MODEL:
            return self._classify_model(axis, image, project_run)
        if axis.criterion == ClassificationCriterion.RESOLUTION:
            return self._classify_resolution(axis, image)
        if axis.criterion == ClassificationCriterion.PROMPT_FAMILY:
            return self._classify_prompt_family(axis, image)
        if axis.criterion == ClassificationCriterion.SIMILARITY:
            return self._classify_similarity(axis, image)
        return self._build_result(
            axis=axis,
            category_label=axis.unknown_label,
            confidence=0.0,
            reason=f"{axis.criterion.value} classifier is not implemented in stage 8.",
        )

    def _classify_safety(self, axis: PolicyAxis, image, project_run: ProjectRun) -> ImageCategoryResult:
        normalized = image.normalized_metadata
        prompt_text = (normalized.prompt if normalized else "") or ""
        negative_prompt_text = (normalized.negative_prompt if normalized else "") or ""
        if not prompt_text and not negative_prompt_text:
            return self._build_result(
                axis=axis,
                category_label=axis.unknown_label,
                confidence=0.0,
                reason="Prompt metadata is unavailable for safety classification.",
            )

        prompt_lower = prompt_text.lower()
        negative_lower = negative_prompt_text.lower()

        nsfw_keywords = [
            keyword.lower()
            for keyword in project_run.policy.extra_rules.get(
                "nsfw_keywords",
                [
                    "nsfw",
                    "nude",
                    "naked",
                    "breasts",
                    "nipples",
                    "sex",
                    "explicit",
                    "erotic",
                    "lingerie",
                    "underwear",
                ],
            )
        ]
        hits_in_prompt = [keyword for keyword in nsfw_keywords if keyword in prompt_lower]
        hits_in_negative = [keyword for keyword in nsfw_keywords if keyword in negative_lower]

        if hits_in_prompt:
            confidence = min(0.99, 0.7 + 0.08 * len(hits_in_prompt))
            return self._build_result(
                axis=axis,
                category_label="NSFW",
                confidence=confidence,
                reason=f"NSFW keywords matched in prompt: {', '.join(sorted(set(hits_in_prompt)))}",
            )

        if hits_in_negative:
            return self._build_result(
                axis=axis,
                category_label="SFW",
                confidence=0.9,
                reason="NSFW keywords appear only in the negative prompt.",
            )

        return self._build_result(
            axis=axis,
            category_label="SFW",
            confidence=0.85,
            reason="No NSFW keywords detected in prompt metadata.",
        )

    def _classify_character(
        self,
        axis: PolicyAxis,
        image,
        project_run: ProjectRun,
        context: dict[str, dict[str, str]],
    ) -> ImageCategoryResult:
        normalized = image.normalized_metadata
        prompt_text = self._character_prompt_text(image)
        prompt_lower = prompt_text.lower()
        keyword_map = project_run.policy.extra_rules.get("character_keywords", {})

        matched_characters = []
        for character_name, keywords in keyword_map.items():
            lowered_keywords = [keyword.lower() for keyword in keywords]
            if any(keyword in prompt_lower for keyword in lowered_keywords):
                matched_characters.append(character_name)

        if len(matched_characters) == 1:
            character_name = matched_characters[0]
            return self._build_result(
                axis=axis,
                category_label=f"Character_{character_name}",
                confidence=0.9,
                reason=f"Prompt keyword matched '{character_name}'.",
            )

        if len(matched_characters) > 1:
            return self._build_result(
                axis=axis,
                category_label=axis.unknown_label,
                confidence=0.4,
                reason=f"Multiple character groups matched: {', '.join(matched_characters)}",
            )

        prompt_family = context["character_families"].get(image.image_id)
        if prompt_family:
            return self._build_result(
                axis=axis,
                category_label=prompt_family,
                confidence=0.68,
                reason="Character group inferred from similar character prompt tokens.",
            )

        return self._build_result(
            axis=axis,
            category_label=axis.unknown_label,
            confidence=0.2,
            reason="No configured character keywords or prompt-similar character family matched.",
        )

    def _classify_style(
        self,
        axis: PolicyAxis,
        image,
        project_run: ProjectRun,
        context: dict[str, dict[str, str]],
    ) -> ImageCategoryResult:
        normalized = image.normalized_metadata
        prompt_text = (normalized.prompt if normalized else "") or ""
        prompt_lower = prompt_text.lower()
        artist = (normalized.artist if normalized else None) or ""
        if artist:
            return self._build_result(
                axis=axis,
                category_label=f"Style_Artist_{self._label_token(artist)}",
                confidence=0.96,
                reason="Artist metadata extracted from normalized metadata.",
            )

        style_family = context["style_families"].get(image.image_id)
        if style_family:
            return self._build_result(
                axis=axis,
                category_label=style_family,
                confidence=0.72,
                reason="Artist was null or unavailable; style inferred from similar style prompt tokens.",
            )

        style_keywords = project_run.policy.extra_rules.get(
            "style_keywords",
            {
                "Anime": ["anime", "illustration", "cel shading", "lineart"],
                "Realistic": ["photorealistic", "realistic", "photo", "cinematic"],
                "Painterly": ["painterly", "oil painting", "brush", "watercolor"],
                "Chibi": ["chibi", "super deformed"],
            },
        )

        matched_styles = []
        for style_name, keywords in style_keywords.items():
            lowered_keywords = [keyword.lower() for keyword in keywords]
            if any(keyword in prompt_lower for keyword in lowered_keywords):
                matched_styles.append(style_name)

        if len(matched_styles) == 1:
            return self._build_result(
                axis=axis,
                category_label=f"Style_{matched_styles[0]}",
                confidence=0.88,
                reason=f"Prompt keyword matched '{matched_styles[0]}' style.",
            )

        if len(matched_styles) > 1:
            return self._build_result(
                axis=axis,
                category_label=axis.unknown_label,
                confidence=0.35,
                reason=f"Multiple style groups matched: {', '.join(matched_styles)}",
            )

        feature_tags = set((image.feature.dominant_tags if image.feature else []) or [])
        tag_to_style = {
            "style_anime": "Anime",
            "style_realistic": "Realistic",
            "style_painterly": "Painterly",
            "style_chibi": "Chibi",
        }
        matched_tag_styles = [style for tag, style in tag_to_style.items() if tag in feature_tags]
        if len(matched_tag_styles) == 1:
            return self._build_result(
                axis=axis,
                category_label=f"Style_{matched_tag_styles[0]}",
                confidence=0.6,
                reason="Style inferred from extracted feature tags.",
            )

        return self._build_result(
            axis=axis,
            category_label=axis.unknown_label,
            confidence=0.15,
            reason="No configured style keywords matched the prompt or feature tags.",
        )

    def _classify_model(self, axis: PolicyAxis, image, project_run: ProjectRun) -> ImageCategoryResult:
        normalized = image.normalized_metadata
        model_value = (normalized.model if normalized else None) or ""
        model_aliases = project_run.policy.extra_rules.get("model_aliases", {})

        canonical_model = None
        if model_value:
            for model_name, aliases in model_aliases.items():
                alias_set = {model_name.lower(), *(alias.lower() for alias in aliases)}
                if model_value.lower() in alias_set:
                    canonical_model = model_name
                    break
            canonical_model = canonical_model or model_value

        if canonical_model:
            return self._build_result(
                axis=axis,
                category_label=f"Model_{canonical_model}",
                confidence=0.95,
                reason="Model value extracted from normalized metadata.",
            )

        return self._build_result(
            axis=axis,
            category_label=axis.unknown_label,
            confidence=0.1,
            reason="No model metadata was available.",
        )

    def _classify_resolution(self, axis: PolicyAxis, image) -> ImageCategoryResult:
        if image.width and image.height:
            return self._build_result(
                axis=axis,
                category_label=f"Resolution_{image.width}x{image.height}",
                confidence=1.0,
                reason="Resolution derived from scan stage image header.",
            )
        return self._build_result(
            axis=axis,
            category_label=axis.unknown_label,
            confidence=0.0,
            reason="Resolution information is missing.",
        )

    def _classify_prompt_family(self, axis: PolicyAxis, image) -> ImageCategoryResult:
        normalized = image.normalized_metadata
        prompt_text = (normalized.prompt if normalized else None) or ""
        if prompt_text:
            canonical_prompt = re.sub(r"\s+", " ", prompt_text.strip().lower())
            family_key = hashlib.sha1(canonical_prompt.encode("utf-8")).hexdigest()[:8]
            return self._build_result(
                axis=axis,
                category_label=f"PromptFamily_{family_key}",
                confidence=0.75,
                reason="Prompt family derived from normalized prompt text hash.",
            )
        return self._build_result(
            axis=axis,
            category_label=axis.unknown_label,
            confidence=0.0,
            reason="No normalized prompt was available.",
        )

    def _classify_similarity(self, axis: PolicyAxis, image) -> ImageCategoryResult:
        if image.feature and image.feature.perceptual_hash:
            return self._build_result(
                axis=axis,
                category_label=axis.unknown_label,
                confidence=0.3,
                reason="Similarity grouping is deferred to stage 9; placeholder assigned.",
            )
        return self._build_result(
            axis=axis,
            category_label=axis.unknown_label,
            confidence=0.0,
            reason="Feature hash is unavailable for similarity pre-classification.",
        )

    def _build_result(
        self,
        *,
        axis: PolicyAxis,
        category_label: str,
        confidence: float,
        reason: str,
    ) -> ImageCategoryResult:
        return ImageCategoryResult(
            axis_priority=axis.priority,
            criterion=axis.criterion,
            category_key=self._slugify(category_label),
            category_label=category_label,
            confidence=confidence,
            reason=reason,
        )

    def _slugify(self, value: str) -> str:
        value = value.strip().lower()
        value = re.sub(r"[^a-z0-9]+", "_", value)
        return value.strip("_") or "unknown"

    def _build_classification_context(self, project_run: ProjectRun) -> dict[str, dict[str, str]]:
        style_threshold = float(project_run.policy.extra_rules.get("style_artist_similarity_threshold", 0.5))
        character_threshold = float(project_run.policy.extra_rules.get("character_prompt_threshold", 0.42))
        return {
            "style_families": self._build_prompt_family_labels(
                project_run.images,
                lambda image: self._style_tokens(image, project_run),
                threshold=style_threshold,
                prefix="StyleFamily",
            ),
            "character_families": self._build_prompt_family_labels(
                project_run.images,
                lambda image: self._character_tokens(image, project_run),
                threshold=character_threshold,
                prefix="CharacterPrompt",
                label_factory=self._build_natural_character_label,
            ),
        }

    def _build_prompt_family_labels(
        self,
        images,
        token_factory,
        *,
        threshold: float,
        prefix: str,
        label_factory=None,
    ) -> dict[str, str]:
        candidates = [(image, token_factory(image)) for image in images]
        candidates = [(image, tokens) for image, tokens in candidates if tokens]
        if len(candidates) < 2:
            return {}

        parent = {image.image_id: image.image_id for image, _ in candidates}

        def find(image_id: str) -> str:
            while parent[image_id] != image_id:
                parent[image_id] = parent[parent[image_id]]
                image_id = parent[image_id]
            return image_id

        def union(left_id: str, right_id: str) -> None:
            left_root = find(left_id)
            right_root = find(right_id)
            if left_root != right_root:
                parent[right_root] = left_root

        for left_index, (left_image, left_tokens) in enumerate(candidates):
            for right_image, right_tokens in candidates[left_index + 1 :]:
                if self._jaccard(left_tokens, right_tokens) >= threshold:
                    union(left_image.image_id, right_image.image_id)

        clusters: dict[str, list] = defaultdict(list)
        for image, _ in candidates:
            clusters[find(image.image_id)].append(image)

        labels: dict[str, str] = {}
        family_index = 1
        used_labels: Counter[str] = Counter()
        for _, cluster in sorted(clusters.items(), key=lambda item: min(image.file_name.lower() for image in item[1])):
            if len(cluster) < 2:
                continue
            label = label_factory(cluster, family_index) if label_factory else f"{prefix}_{family_index:03d}"
            used_labels[label] += 1
            if used_labels[label] > 1:
                label = f"{label}_{used_labels[label]:02d}"
            family_index += 1
            for image in cluster:
                labels[image.image_id] = label
        return labels

    def _style_tokens(self, image, project_run: ProjectRun) -> set[str]:
        normalized = image.normalized_metadata
        if not normalized:
            return set()
        if normalized.artist:
            return set()
        signature = str(normalized.extra.get("style_signature") or normalized.prompt or "")
        tokens = self._prompt_tokens(signature)
        character_keywords = self._flatten_rule_keywords(project_run.policy.extra_rules.get("character_keywords", {}))
        character_stopwords = {"girl", "boy", "solo", "character", "person", "face", "portrait"}
        return tokens - character_keywords - character_stopwords

    def _character_tokens(self, image, project_run: ProjectRun) -> set[str]:
        normalized = image.normalized_metadata
        if not normalized:
            return set()
        tokens = self._prompt_tokens(self._character_prompt_text(image))
        style_keywords = self._flatten_rule_keywords(project_run.policy.extra_rules.get("style_keywords", {}))
        style_stopwords = {
            "anime",
            "illustration",
            "realistic",
            "photorealistic",
            "cinematic",
            "painterly",
            "painting",
            "watercolor",
            "lineart",
            "style",
            "artist",
        }
        return tokens - style_keywords - style_stopwords

    def _character_prompt_text(self, image) -> str:
        normalized = image.normalized_metadata
        if not normalized:
            return ""
        if normalized.character_prompts:
            return " ".join(normalized.character_prompts)
        return normalized.prompt or ""

    def _prompt_tokens(self, prompt_text: str) -> set[str]:
        stopwords = {
            "best",
            "quality",
            "masterpiece",
            "high",
            "low",
            "very",
            "with",
            "and",
            "the",
            "for",
            "from",
            "null",
        }
        tokens = set(re.findall(r"[a-z0-9_]+", prompt_text.lower()))
        return {token for token in tokens if len(token) > 2 and token not in stopwords}

    def _flatten_rule_keywords(self, keyword_map: dict[str, list[str]]) -> set[str]:
        output: set[str] = set()
        for name, keywords in keyword_map.items():
            output.update(self._prompt_tokens(str(name)))
            for keyword in keywords:
                output.update(self._prompt_tokens(str(keyword)))
        return output

    def _jaccard(self, left: set[str], right: set[str]) -> float:
        if not left or not right:
            return 0.0
        union = left | right
        if not union:
            return 0.0
        return len(left & right) / len(union)

    def _build_natural_character_label(self, cluster, family_index: int) -> str:
        prompt_text = " ".join(self._character_prompt_text(image) for image in cluster).lower()
        descriptor_parts = [
            label
            for label in (
                self._hair_label(prompt_text),
                self._eye_label(prompt_text),
                self._outfit_label(prompt_text),
            )
            if label
        ]
        subject = self._subject_label(prompt_text)

        if descriptor_parts or subject:
            return "".join(descriptor_parts + [subject or "캐릭터"])
        return f"캐릭터그룹_{family_index:03d}"

    def _hair_label(self, prompt_text: str) -> str | None:
        hair_patterns = [
            (("silver hair", "silver-haired", "silver haired", "white hair", "white-haired", "white haired"), "은발"),
            (("blue hair", "blue-haired", "blue haired", "aqua hair", "aqua-haired", "aqua haired"), "푸른머리"),
            (("black hair", "black-haired", "black haired"), "흑발"),
            (("blonde hair", "blond hair", "blonde-haired", "blond-haired", "yellow hair"), "금발"),
            (("brown hair", "brown-haired", "brown haired"), "갈색머리"),
            (("pink hair", "pink-haired", "pink haired"), "분홍머리"),
            (("red hair", "red-haired", "red haired"), "적발"),
            (("green hair", "green-haired", "green haired"), "녹색머리"),
            (("purple hair", "purple-haired", "purple haired"), "보라머리"),
        ]
        return self._first_phrase_label(prompt_text, hair_patterns)

    def _eye_label(self, prompt_text: str) -> str | None:
        eye_patterns = [
            (("blue eyes", "blue-eyed", "aqua eyes", "cyan eyes"), "푸른눈"),
            (("red eyes", "red-eyed", "crimson eyes", "scarlet eyes"), "붉은눈"),
            (("green eyes", "green-eyed", "emerald eyes"), "녹색눈"),
            (("gold eyes", "golden eyes", "yellow eyes", "amber eyes"), "금색눈"),
            (("purple eyes", "violet eyes", "purple-eyed"), "보라눈"),
            (("pink eyes", "pink-eyed"), "분홍눈"),
            (("black eyes", "black-eyed"), "검은눈"),
            (("brown eyes", "brown-eyed"), "갈색눈"),
        ]
        return self._first_phrase_label(prompt_text, eye_patterns)

    def _outfit_label(self, prompt_text: str) -> str | None:
        outfit_patterns = [
            (("black armor", "dark armor"), "검은갑옷"),
            (("white dress",), "하얀드레스"),
            (("school uniform",), "교복"),
            (("maid outfit", "maid dress"), "메이드복"),
            (("idol outfit", "idol costume"), "아이돌복"),
        ]
        return self._first_phrase_label(prompt_text, outfit_patterns)

    def _subject_label(self, prompt_text: str) -> str | None:
        subject_patterns = [
            (("girl", "female", "woman", "lady"), "소녀"),
            (("boy", "male", "man"), "소년"),
            (("knight",), "기사"),
            (("princess",), "공주"),
            (("witch",), "마녀"),
            (("maid",), "메이드"),
            (("dragon",), "용"),
            (("cat girl", "catgirl"), "고양이소녀"),
            (("angel",), "천사"),
            (("demon",), "악마"),
        ]
        return self._first_phrase_label(prompt_text, subject_patterns)

    def _first_phrase_label(self, prompt_text: str, patterns: list[tuple[tuple[str, ...], str]]) -> str | None:
        for phrases, label in patterns:
            if any(phrase in prompt_text for phrase in phrases):
                return label
        return None

    def _label_token(self, value: str) -> str:
        cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", value).strip(" ._")
        cleaned = re.sub(r"\s+", "_", cleaned)
        return cleaned or "Unknown"

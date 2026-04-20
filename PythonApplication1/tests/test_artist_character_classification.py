from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from metasort.category_classifier import CategoryClassifier
from metasort.enums import ClassificationCriterion
from metasort.models import ImageFile, NormalizedMetadata, RawMetadata
from metasort.normalizer import MetadataNormalizer
from metasort.sample_data import build_default_policy, build_project_run


class ArtistCharacterClassificationTests(unittest.TestCase):
    def test_artist_metadata_creates_artist_style_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_run = self._build_run(Path(temp_dir))
            project_run.images = [
                self._image(
                    "img-1",
                    "artist.png",
                    "anime illustration, blue hair, stage lights",
                    artist="sample artist",
                )
            ]

            CategoryClassifier().classify(project_run)

            self.assertEqual(
                self._category_label(project_run.images[0], ClassificationCriterion.STYLE),
                "Style_Artist_sample_artist",
            )

    def test_artist_null_style_and_unknown_character_prompts_are_clustered(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_run = self._build_run(Path(temp_dir))
            project_run.images = [
                self._image(
                    "img-1",
                    "hero_001.png",
                    "anime watercolor, wide landscape, dramatic lighting, artist:null",
                    character_prompts=["silver haired knight, black armor, crimson eyes"],
                ),
                self._image(
                    "img-2",
                    "hero_002.png",
                    "anime watercolor, wide landscape, dramatic pose, artist:null",
                    character_prompts=["silver haired knight, black armor, red eyes"],
                ),
            ]

            CategoryClassifier().classify(project_run)

            style_labels = [
                self._category_label(image, ClassificationCriterion.STYLE)
                for image in project_run.images
            ]
            character_labels = [
                self._category_label(image, ClassificationCriterion.CHARACTER)
                for image in project_run.images
            ]

            self.assertEqual(style_labels, ["StyleFamily_001", "StyleFamily_001"])
            self.assertEqual(character_labels, ["은발붉은눈검은갑옷기사", "은발붉은눈검은갑옷기사"])

    def test_character_prompt_label_uses_natural_korean_descriptor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_run = self._build_run(Path(temp_dir))
            project_run.images = [
                self._image(
                    "img-1",
                    "girl_001.png",
                    "anime city street, artist:null",
                    character_prompts=["silver hair, blue eyes, girl, white dress"],
                ),
                self._image(
                    "img-2",
                    "girl_002.png",
                    "anime school rooftop, artist:null",
                    character_prompts=["silver-haired girl, blue eyes, white dress"],
                ),
            ]

            CategoryClassifier().classify(project_run)

            character_labels = [
                self._category_label(image, ClassificationCriterion.CHARACTER)
                for image in project_run.images
            ]

            self.assertEqual(character_labels, ["은발푸른눈하얀드레스소녀", "은발푸른눈하얀드레스소녀"])

    def test_normalizer_extracts_nested_novelai_character_prompts(self) -> None:
        raw_metadata = RawMetadata(
            source_format="png_text",
            extracted_at=datetime.now(),
            raw_text={
                "Comment": (
                    '{"v4_prompt":{"caption":{"base_caption":"scene only",'
                    '"char_captions":[{"char_caption":"silver haired knight, black armor"},'
                    '{"char_caption":"small dragon companion"}]}}}'
                )
            },
        )

        normalized = MetadataNormalizer()._normalize_metadata(raw_metadata, None, None)

        self.assertEqual(
            normalized.character_prompts,
            [
                "silver haired knight, black armor",
                "small dragon companion",
            ],
        )

    def _build_run(self, project_root: Path):
        policy = build_default_policy()
        policy.extra_rules["character_keywords"] = {}
        return build_project_run(project_root / "input", project_root / "output", policy=policy)

    def _image(
        self,
        image_id: str,
        file_name: str,
        prompt: str,
        *,
        artist: str | None = None,
        character_prompts: list[str] | None = None,
    ) -> ImageFile:
        return ImageFile(
            image_id=image_id,
            file_name=file_name,
            file_path=file_name,
            extension=".png",
            file_size_bytes=100,
            normalized_metadata=NormalizedMetadata(
                prompt=prompt,
                character_prompts=character_prompts or [],
                artist=artist,
                extra={
                    "artist_raw": artist or "null",
                    "artist_is_null": artist is None,
                },
            ),
        )

    def _category_label(self, image: ImageFile, criterion: ClassificationCriterion) -> str:
        for category in image.category_results:
            if category.criterion == criterion:
                return category.category_label
        self.fail(f"Missing {criterion.value} category")


if __name__ == "__main__":
    unittest.main()

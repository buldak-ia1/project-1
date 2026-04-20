from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .enums import (
    ClassificationCriterion,
    ExecutionMode,
    MetadataMissingHandling,
    RunStatus,
    UnclassifiedHandling,
)
from .models import ClassificationPolicy, OutputLog, PolicyAxis, ProjectRun


def build_default_policy() -> ClassificationPolicy:
    return ClassificationPolicy(
        policy_id="policy-mvp-001",
        name="MVP Style -> Character -> Similarity",
        description="그림체 -> 캐릭터 -> 유사도 기준 정책",
        execution_mode=ExecutionMode.ANALYZE_ONLY,
        include_subdirectories=True,
        similarity_threshold=8.0,
        nsfw_threshold=0.7,
        unclassified_handling=UnclassifiedHandling.PLACE_IN_UNCLASSIFIED,
        metadata_missing_handling=MetadataMissingHandling.VISUAL_ONLY,
        axes=[
            PolicyAxis(
                priority=1,
                criterion=ClassificationCriterion.STYLE,
                display_name="Style",
                unknown_label="Style_Unknown",
            ),
            PolicyAxis(
                priority=2,
                criterion=ClassificationCriterion.CHARACTER,
                display_name="Character",
                unknown_label="Character_Unknown",
            ),
            PolicyAxis(
                priority=3,
                criterion=ClassificationCriterion.SIMILARITY,
                display_name="SimilarityGroup",
                unknown_label="unique",
            ),
        ],
        extra_rules={
            "supported_extensions": [".png", ".jpg", ".jpeg", ".webp"],
            "character_keywords": {
                "Miku": ["miku", "hatsune miku"],
            },
            "style_keywords": {
                "Anime": ["anime", "illustration", "cel shading", "lineart"],
                "Realistic": ["photorealistic", "realistic", "photo", "cinematic"],
                "Painterly": ["painterly", "oil painting", "brush", "watercolor"],
                "Chibi": ["chibi", "super deformed"],
            },
            "nsfw_keywords": [
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
            "model_aliases": {
                "nai-diffusion-4": ["nai-diffusion-4", "nai diffusion 4"],
            },
            "style_artist_similarity_threshold": 0.5,
            "character_prompt_threshold": 0.42,
            "prompt_family_threshold": 0.58,
            "visual_similarity_threshold": 0.92,
            "external_model": {
                "enabled": True,
                "provider": "auto",
                "model_id": "openai/clip-vit-base-patch32",
                "device": "cpu",
                "normalize_embeddings": True,
            },
        },
    )


def build_project_run(
    source_root: str | Path,
    output_root: str | Path,
    *,
    policy: ClassificationPolicy | None = None,
    started_at: datetime | None = None,
) -> ProjectRun:
    started_at = started_at or datetime.now()
    return ProjectRun(
        run_id=f"run-{started_at.strftime('%Y%m%d-%H%M%S')}",
        project_name="MetaSort",
        source_root=str(source_root),
        output_root=str(output_root),
        started_at=started_at,
        status=RunStatus.PLANNED,
        policy=policy or build_default_policy(),
        logs=[
            OutputLog(
                timestamp=started_at,
                level="INFO",
                message="Project run created for configured policy.",
            )
        ],
    )

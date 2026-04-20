from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from .enums import ClassificationCriterion, GroupType
from .models import GroupMember, ImageCategoryResult, ImageGroup, OutputLog, ProjectRun


@dataclass(slots=True)
class GroupingStats:
    bucket_count: int = 0
    exact_duplicate_groups: int = 0
    near_duplicate_groups: int = 0
    same_prompt_family_groups: int = 0
    same_model_series_groups: int = 0
    visual_similar_groups: int = 0
    unique_groups: int = 0


class SimilarityGrouper:
    def group(self, project_run: ProjectRun) -> ProjectRun:
        similarity_axis = self._find_similarity_axis(project_run)
        bucket_map = self._bucket_images(project_run)
        stats = GroupingStats(bucket_count=len(bucket_map))
        groups: list[ImageGroup] = []
        group_index = 1
        type_counts: Counter[str] = Counter()

        for category_path, images in sorted(bucket_map.items()):
            group_index = self._build_groups_for_bucket(
                project_run=project_run,
                images=images,
                category_path=list(category_path),
                similarity_axis=similarity_axis,
                groups=groups,
                stats=stats,
                type_counts=type_counts,
                starting_index=group_index,
            )

        project_run.groups = groups
        self._refresh_classification_summary(project_run)
        project_run.summary["grouping"] = {
            "bucket_count": stats.bucket_count,
            "group_count": len(groups),
            "exact_duplicate_groups": stats.exact_duplicate_groups,
            "near_duplicate_groups": stats.near_duplicate_groups,
            "same_prompt_family_groups": stats.same_prompt_family_groups,
            "same_model_series_groups": stats.same_model_series_groups,
            "visual_similar_groups": stats.visual_similar_groups,
            "unique_groups": stats.unique_groups,
            "by_group_type": dict(sorted(type_counts.items())),
        }
        project_run.logs.append(
            OutputLog(
                timestamp=project_run.started_at,
                level="INFO",
                message="Similarity grouping stage completed.",
                context=project_run.summary["grouping"],
            )
        )
        return project_run

    def _refresh_classification_summary(self, project_run: ProjectRun) -> None:
        if "classification" not in project_run.summary:
            return

        criterion_counts: dict[str, Counter[str]] = defaultdict(Counter)
        classified_images = 0
        for image in project_run.images:
            if image.category_results:
                classified_images += 1
            for category in image.category_results:
                criterion_counts[category.criterion.value][category.category_label] += 1

        refreshed_summary = {
            "processed_images": len(project_run.images),
            "classified_images": classified_images,
            "by_criterion": {
                criterion: dict(sorted(counter.items()))
                for criterion, counter in sorted(criterion_counts.items())
            },
        }
        project_run.summary["classification"] = refreshed_summary

        for log in reversed(project_run.logs):
            if log.message == "Category classification stage completed.":
                log.context = refreshed_summary
                break

    def _build_groups_for_bucket(
        self,
        *,
        project_run: ProjectRun,
        images,
        category_path: list[str],
        similarity_axis,
        groups: list[ImageGroup],
        stats: GroupingStats,
        type_counts: Counter[str],
        starting_index: int,
    ) -> int:
        next_index = starting_index
        remaining = sorted(images, key=self._representative_sort_key)

        exact_buckets: dict[str, list] = defaultdict(list)
        for image in remaining:
            if image.checksum_sha256:
                exact_buckets[image.checksum_sha256].append(image)

        consumed_ids: set[str] = set()
        for members in exact_buckets.values():
            if len(members) < 2:
                continue
            next_index = self._append_group(
                groups=groups,
                stats=stats,
                type_counts=type_counts,
                members=members,
                category_path=category_path,
                group_type=GroupType.EXACT_DUPLICATE,
                similarity_axis=similarity_axis,
                next_index=next_index,
            )
            consumed_ids.update(member.image_id for member in members)

        remaining = [image for image in remaining if image.image_id not in consumed_ids]

        grouping_steps = [
            (
                GroupType.NEAR_DUPLICATE,
                lambda left, right: self._is_near_duplicate_pair(left, right, project_run.policy.similarity_threshold),
            ),
            (
                GroupType.SAME_PROMPT_FAMILY,
                lambda left, right: self._is_same_prompt_family_pair(left, right, project_run),
            ),
            (
                GroupType.SAME_MODEL_SERIES,
                lambda left, right: self._is_same_model_series_pair(left, right),
            ),
            (
                GroupType.VISUAL_SIMILAR,
                lambda left, right: self._is_visual_similar_pair(left, right, project_run),
            ),
        ]

        for group_type, predicate in grouping_steps:
            clusters = self._cluster_by_predicate(remaining, predicate)
            grouped_ids = {
                member.image_id
                for cluster in clusters
                if len(cluster) > 1
                for member in cluster
            }
            for cluster in clusters:
                if len(cluster) < 2:
                    continue
                next_index = self._append_group(
                    groups=groups,
                    stats=stats,
                    type_counts=type_counts,
                    members=cluster,
                    category_path=category_path,
                    group_type=group_type,
                    similarity_axis=similarity_axis,
                    next_index=next_index,
                )
            remaining = [image for image in remaining if image.image_id not in grouped_ids]

        if remaining:
            next_index = self._append_group(
                groups=groups,
                stats=stats,
                type_counts=type_counts,
                members=remaining,
                category_path=category_path,
                group_type=GroupType.UNIQUE,
                similarity_axis=similarity_axis,
                next_index=next_index,
            )

        return next_index

    def _append_group(
        self,
        *,
        groups: list[ImageGroup],
        stats: GroupingStats,
        type_counts: Counter[str],
        members,
        category_path: list[str],
        group_type: GroupType,
        similarity_axis,
        next_index: int,
    ) -> int:
        group_label = self._build_group_label(group_type, next_index)
        group = self._build_group(
            members=members,
            category_path=category_path,
            group_type=group_type,
            group_label=group_label,
            similarity_axis=similarity_axis,
        )
        groups.append(group)
        type_counts[group.group_type.value] += 1
        self._increment_group_stat(stats, group_type)
        return next_index + 1

    def _build_group(
        self,
        *,
        members,
        category_path: list[str],
        group_type: GroupType,
        group_label: str,
        similarity_axis,
    ) -> ImageGroup:
        representative = self._select_representative(members)
        member_records: list[GroupMember] = []

        for image in sorted(members, key=self._representative_sort_key):
            member_records.append(
                GroupMember(
                    image_id=image.image_id,
                    relation_score=self._relation_score(group_type, representative, image),
                    is_representative=image.image_id == representative.image_id,
                )
            )
            self._update_similarity_axis(image, similarity_axis, group_label, group_type)

        return ImageGroup(
            group_id=group_label,
            category_path=category_path,
            group_type=group_type,
            representative_image_id=representative.image_id,
            members=member_records,
        )

    def _update_similarity_axis(self, image, similarity_axis, group_label: str, group_type: GroupType) -> None:
        if similarity_axis is None:
            return

        confidence = 1.0 if group_type not in {GroupType.UNIQUE, GroupType.VISUAL_SIMILAR} else 0.92
        if group_type == GroupType.UNIQUE:
            confidence = 0.5

        for category in image.category_results:
            if category.axis_priority == similarity_axis.priority:
                category.category_label = group_label
                category.category_key = group_label
                category.confidence = confidence
                category.reason = f"Assigned by grouping stage as {group_type.value}."
                return

        image.category_results.append(
            ImageCategoryResult(
                axis_priority=similarity_axis.priority,
                criterion=ClassificationCriterion.SIMILARITY,
                category_key=group_label,
                category_label=group_label,
                confidence=confidence,
                reason=f"Assigned by grouping stage as {group_type.value}.",
            )
        )
        image.category_results.sort(key=lambda item: item.axis_priority)

    def _bucket_images(self, project_run: ProjectRun) -> dict[tuple[str, ...], list]:
        bucket_map: dict[tuple[str, ...], list] = defaultdict(list)
        for image in project_run.images:
            category_path = tuple(
                category.category_label
                for category in sorted(image.category_results, key=lambda item: item.axis_priority)
                if category.criterion != ClassificationCriterion.SIMILARITY
            )
            bucket_map[category_path].append(image)
        return bucket_map

    def _find_similarity_axis(self, project_run: ProjectRun):
        for axis in project_run.policy.axes:
            if axis.enabled and axis.criterion == ClassificationCriterion.SIMILARITY:
                return axis
        return None

    def _cluster_by_predicate(self, images, predicate) -> list[list]:
        if not images:
            return []

        parent = {image.image_id: image.image_id for image in images}

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

        for left_index, left in enumerate(images):
            for right in images[left_index + 1 :]:
                if predicate(left, right):
                    union(left.image_id, right.image_id)

        clusters: dict[str, list] = defaultdict(list)
        for image in images:
            clusters[find(image.image_id)].append(image)

        return [
            sorted(cluster, key=self._representative_sort_key)
            for _, cluster in sorted(clusters.items(), key=lambda item: item[0])
        ]

    def _is_near_duplicate_pair(self, left, right, threshold: float) -> bool:
        return self._combined_hash_distance(left, right) <= threshold

    def _is_same_prompt_family_pair(self, left, right, project_run: ProjectRun) -> bool:
        threshold = float(project_run.policy.extra_rules.get("prompt_family_threshold", 0.58))
        return self._prompt_similarity(left, right) >= threshold

    def _is_same_model_series_pair(self, left, right) -> bool:
        left_model = self._model_series(left)
        right_model = self._model_series(right)
        return bool(left_model and right_model and left_model == right_model)

    def _is_visual_similar_pair(self, left, right, project_run: ProjectRun) -> bool:
        threshold = float(project_run.policy.extra_rules.get("visual_similarity_threshold", 0.92))
        return self._visual_similarity(left, right) >= threshold

    def _combined_hash_distance(self, left, right) -> float:
        left_feature = left.feature
        right_feature = right.feature
        if not left_feature or not right_feature:
            return float("inf")

        phash_distance = self._hamming_distance(
            left_feature.perceptual_hash,
            right_feature.perceptual_hash,
        )
        dhash_distance = self._hamming_distance(
            left_feature.difference_hash,
            right_feature.difference_hash,
        )
        return (phash_distance + dhash_distance) / 2

    def _hamming_distance(self, left_hash: str | None, right_hash: str | None) -> int:
        if not left_hash or not right_hash:
            return 64
        return bin(int(left_hash, 16) ^ int(right_hash, 16)).count("1")

    def _relation_score(self, group_type: GroupType, representative, image) -> float | None:
        if group_type == GroupType.EXACT_DUPLICATE:
            return 1.0
        if group_type == GroupType.NEAR_DUPLICATE:
            return self._hash_similarity_score(representative, image)
        if group_type == GroupType.SAME_PROMPT_FAMILY:
            return self._prompt_similarity(representative, image)
        if group_type == GroupType.SAME_MODEL_SERIES:
            return 1.0 if self._is_same_model_series_pair(representative, image) else None
        if group_type == GroupType.VISUAL_SIMILAR:
            return self._visual_similarity(representative, image)
        return None

    def _hash_similarity_score(self, left, right) -> float | None:
        left_feature = left.feature
        right_feature = right.feature
        if not left_feature or not right_feature:
            return None
        distance = self._combined_hash_distance(left, right)
        return round(max(0.0, 1.0 - (distance / 64)), 4)

    def _prompt_similarity(self, left, right) -> float:
        left_prompt = self._tokenize_prompt(left)
        right_prompt = self._tokenize_prompt(right)
        if not left_prompt or not right_prompt:
            return 0.0
        union = left_prompt | right_prompt
        if not union:
            return 0.0
        return round(len(left_prompt & right_prompt) / len(union), 4)

    def _tokenize_prompt(self, image) -> set[str]:
        prompt_text = ""
        if image.normalized_metadata and image.normalized_metadata.prompt:
            prompt_text = image.normalized_metadata.prompt.lower()
        tokens = set(re.findall(r"[a-z0-9_]+", prompt_text))
        stopwords = {"best", "quality", "masterpiece", "high", "low"}
        return {token for token in tokens if len(token) > 2 and token not in stopwords}

    def _model_series(self, image) -> str | None:
        model = ""
        if image.normalized_metadata and image.normalized_metadata.model:
            model = image.normalized_metadata.model.lower()
        if not model:
            return None
        series = re.sub(r"[\W_]+", "-", model)
        series = re.sub(r"-v?\d+(\.\d+)*$", "", series)
        return series.strip("-") or None

    def _visual_similarity(self, left, right) -> float:
        left_feature = left.feature
        right_feature = right.feature
        if not left_feature or not right_feature:
            return 0.0

        embedding_similarity = self._cosine_similarity(
            left_feature.embedding_vector,
            right_feature.embedding_vector,
        )
        hash_similarity = self._hash_similarity_score(left, right) or 0.0
        return round(max(embedding_similarity, hash_similarity), 4)

    def _cosine_similarity(self, left_vector: list[float], right_vector: list[float]) -> float:
        if not left_vector or not right_vector or len(left_vector) != len(right_vector):
            return 0.0

        numerator = sum(left * right for left, right in zip(left_vector, right_vector))
        left_norm = math.sqrt(sum(value * value for value in left_vector))
        right_norm = math.sqrt(sum(value * value for value in right_vector))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return numerator / (left_norm * right_norm)

    def _build_group_label(self, group_type: GroupType, index: int) -> str:
        if group_type == GroupType.UNIQUE:
            return "unique"
        return f"{group_type.value}_{index:03d}"

    def _increment_group_stat(self, stats: GroupingStats, group_type: GroupType) -> None:
        if group_type == GroupType.EXACT_DUPLICATE:
            stats.exact_duplicate_groups += 1
        elif group_type == GroupType.NEAR_DUPLICATE:
            stats.near_duplicate_groups += 1
        elif group_type == GroupType.SAME_PROMPT_FAMILY:
            stats.same_prompt_family_groups += 1
        elif group_type == GroupType.SAME_MODEL_SERIES:
            stats.same_model_series_groups += 1
        elif group_type == GroupType.VISUAL_SIMILAR:
            stats.visual_similar_groups += 1
        elif group_type == GroupType.UNIQUE:
            stats.unique_groups += 1

    def _select_representative(self, members):
        return min(members, key=self._representative_sort_key)

    def _representative_sort_key(self, image):
        area = (image.width or 0) * (image.height or 0)
        return (
            len(image.issues),
            -area,
            -image.file_size_bytes,
            image.file_name.lower(),
            image.image_id,
        )

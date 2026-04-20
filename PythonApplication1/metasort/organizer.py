from __future__ import annotations

import json
import re
import shutil
from collections import Counter
from pathlib import Path

from .enums import ExecutionMode, GroupType
from .models import OutputLog, ProjectRun


class Organizer:
    def organize(self, project_run: ProjectRun) -> ProjectRun:
        output_root = Path(project_run.output_root)
        sorted_root = output_root / "Sorted"
        manifest_path = output_root / "manifest.json"
        output_root.mkdir(parents=True, exist_ok=True)

        group_index = self._build_group_index(project_run)
        existing_paths: set[Path] = self._collect_existing_output_paths(sorted_root)
        reserved_paths: set[Path] = set(existing_paths)
        created_directories: set[Path] = set()
        stats = Counter()
        manifest_entries: list[dict[str, object]] = []

        for image in sorted(project_run.images, key=lambda item: (item.file_name.lower(), item.image_id)):
            destination = sorted_root / self._build_relative_output_path(project_run, image)
            collided_with_existing = destination in existing_paths
            destination, renamed = self._resolve_collision(destination, reserved_paths)
            reserved_paths.add(destination)
            created_directories.add(destination.parent)
            if renamed:
                stats["renamed"] += 1
                if collided_with_existing:
                    stats["preserved_existing"] += 1
                project_run.logs.append(
                    OutputLog(
                        timestamp=project_run.started_at,
                        level="WARNING",
                        message="Destination file name collision resolved without deleting existing output.",
                        image_id=image.image_id,
                        context={
                            "source_path": image.file_path,
                            "resolved_output_path": str(destination),
                            "collided_with_existing_output": collided_with_existing,
                        },
                    )
                )

            action, status, error_message = self._materialize_destination(
                project_run,
                image.file_path,
                destination,
            )
            stats[status] += 1
            if error_message:
                image.issues.append("organization_failed")
                project_run.logs.append(
                    OutputLog(
                        timestamp=project_run.started_at,
                        level="ERROR",
                        message="Failed to materialize organized output.",
                        image_id=image.image_id,
                        context={
                            "source_path": image.file_path,
                            "output_path": str(destination),
                            "error": error_message,
                        },
                    )
                )

            group = group_index.get(image.image_id)
            manifest_entries.append(
                {
                    "image_id": image.image_id,
                    "file_name": image.file_name,
                    "source_path": image.file_path,
                    "output_path": str(destination),
                    "relative_output_path": str(destination.relative_to(output_root)),
                    "action": action,
                    "status": status,
                    "category_path": [
                        category.category_label
                        for category in sorted(image.category_results, key=lambda item: item.axis_priority)
                    ],
                    "group_id": group.group_id if group else None,
                    "group_type": group.group_type.value if group else GroupType.UNIQUE.value,
                    "is_representative": bool(
                        group and group.representative_image_id == image.image_id
                    ),
                    "error": error_message,
                    "issues": list(image.issues),
                }
            )

        self._write_manifest(
            manifest_path=manifest_path,
            project_run=project_run,
            sorted_root=sorted_root,
            entries=manifest_entries,
        )

        project_run.summary["organization"] = {
            "execution_mode": project_run.policy.execution_mode.value,
            "sorted_root": str(sorted_root),
            "manifest_path": str(manifest_path),
            "directories_touched": len(created_directories),
            "copied_files": stats["copied"],
            "moved_files": stats["moved"],
            "analyze_only_files": stats["analyze_only"],
            "failed_files": stats["failed"],
            "collision_renamed_files": stats["renamed"],
            "preserved_existing_files": stats["preserved_existing"],
        }
        project_run.logs.append(
            OutputLog(
                timestamp=project_run.started_at,
                level="INFO",
                message="Output organization stage completed.",
                context=project_run.summary["organization"],
            )
        )
        return project_run

    def _build_group_index(self, project_run: ProjectRun) -> dict[str, object]:
        index: dict[str, object] = {}
        for group in project_run.groups:
            for member in group.members:
                index[member.image_id] = group
        return index

    def _build_relative_output_path(self, project_run: ProjectRun, image) -> Path:
        categories = [
            self._sanitize_segment(category.category_label)
            for category in sorted(image.category_results, key=lambda item: item.axis_priority)
        ]
        if not categories:
            categories = [self._sanitize_segment(project_run.policy.unclassified_handling.value)]

        return Path(*categories) / image.file_name

    def _resolve_collision(self, destination: Path, reserved_paths: set[Path]) -> tuple[Path, bool]:
        if destination not in reserved_paths:
            return destination, False

        stem = destination.stem
        suffix = destination.suffix
        counter = 1
        while True:
            candidate = destination.with_name(f"{stem}_{counter}{suffix}")
            if candidate not in reserved_paths:
                return candidate, True
            counter += 1

    def _collect_existing_output_paths(self, sorted_root: Path) -> set[Path]:
        if not sorted_root.exists():
            return set()
        return {
            file_path
            for file_path in sorted_root.rglob("*")
            if file_path.is_file()
        }

    def _materialize_destination(
        self,
        project_run: ProjectRun,
        source_path: str,
        destination: Path,
    ) -> tuple[str, str, str | None]:
        mode = project_run.policy.execution_mode
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            if mode == ExecutionMode.ANALYZE_ONLY:
                return "analyze_only", "analyze_only", None
            if mode == ExecutionMode.COPY:
                shutil.copy2(source_path, destination)
                return "copy", "copied", None
            if mode == ExecutionMode.MOVE:
                shutil.move(source_path, destination)
                return "move", "moved", None
            return "unknown", "failed", f"Unsupported execution mode: {mode.value}"
        except OSError as error:
            return mode.value, "failed", str(error)

    def _write_manifest(
        self,
        *,
        manifest_path: Path,
        project_run: ProjectRun,
        sorted_root: Path,
        entries: list[dict[str, object]],
    ) -> None:
        payload = {
            "run_id": project_run.run_id,
            "project_name": project_run.project_name,
            "generated_at": project_run.started_at.isoformat(),
            "execution_mode": project_run.policy.execution_mode.value,
            "sorted_root": str(sorted_root),
            "entry_count": len(entries),
            "entries": entries,
        }
        with manifest_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)

    def _sanitize_segment(self, value: str) -> str:
        cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", value).strip(" .")
        return cleaned or "Unknown"

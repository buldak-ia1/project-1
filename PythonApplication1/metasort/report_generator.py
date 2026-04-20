from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from .models import OutputLog, ProjectRun


class ReportGenerator:
    def generate(self, project_run: ProjectRun) -> ProjectRun:
        output_root = Path(project_run.output_root)
        output_root.mkdir(parents=True, exist_ok=True)

        csv_path = output_root / "report.csv"
        summary_path = output_root / "summary.json"
        run_log_path = output_root / "run.log"

        project_run.summary["reports"] = {
            "csv_path": str(csv_path),
            "summary_json_path": str(summary_path),
            "run_log_path": str(run_log_path),
        }
        project_run.logs.append(
            OutputLog(
                timestamp=project_run.started_at,
                level="INFO",
                message="Report generation stage completed.",
                context=project_run.summary["reports"],
            )
        )
        self._write_csv_report(csv_path, project_run)
        self._write_summary_json(summary_path, project_run)
        self._write_run_log(run_log_path, project_run)
        return project_run

    def _write_csv_report(self, csv_path: Path, project_run: ProjectRun) -> None:
        fieldnames = [
            "image_id",
            "file_name",
            "file_path",
            "extension",
            "file_size_bytes",
            "width",
            "height",
            "checksum_sha256",
            "raw_source_format",
            "prompt",
            "negative_prompt",
            "character_prompts",
            "seed",
            "sampler",
            "steps",
            "cfg_scale",
            "model",
            "software",
            "artist",
            "perceptual_hash",
            "difference_hash",
            "embedding_dimensions",
            "aspect_ratio",
            "dominant_tags",
            "category_path",
            "category_results",
            "group_id",
            "group_type",
            "representative_image_id",
            "issues",
        ]

        with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()

            for image in project_run.images:
                normalized = image.normalized_metadata
                feature = image.feature
                raw_metadata = image.raw_metadata
                category_path = "/".join(
                    category.category_label
                    for category in sorted(image.category_results, key=lambda item: item.axis_priority)
                )
                category_results = "|".join(
                    f"{category.criterion.value}:{category.category_label}"
                    for category in sorted(image.category_results, key=lambda item: item.axis_priority)
                )
                group = self._find_group_for_image(project_run, image.image_id)
                writer.writerow(
                    {
                        "image_id": image.image_id,
                        "file_name": image.file_name,
                        "file_path": image.file_path,
                        "extension": image.extension,
                        "file_size_bytes": image.file_size_bytes,
                        "width": image.width,
                        "height": image.height,
                        "checksum_sha256": image.checksum_sha256,
                        "raw_source_format": raw_metadata.source_format if raw_metadata else "",
                        "prompt": normalized.prompt if normalized else "",
                        "negative_prompt": normalized.negative_prompt if normalized else "",
                        "character_prompts": "|".join(normalized.character_prompts) if normalized else "",
                        "seed": normalized.seed if normalized else "",
                        "sampler": normalized.sampler if normalized else "",
                        "steps": normalized.steps if normalized else "",
                        "cfg_scale": normalized.cfg_scale if normalized else "",
                        "model": normalized.model if normalized else "",
                        "software": normalized.software if normalized else "",
                        "artist": normalized.artist if normalized else "",
                        "perceptual_hash": feature.perceptual_hash if feature else "",
                        "difference_hash": feature.difference_hash if feature else "",
                        "embedding_dimensions": len(feature.embedding_vector) if feature else 0,
                        "aspect_ratio": feature.aspect_ratio if feature else "",
                        "dominant_tags": "|".join(feature.dominant_tags) if feature else "",
                        "category_path": category_path,
                        "category_results": category_results,
                        "group_id": group.group_id if group else "",
                        "group_type": group.group_type.value if group else "",
                        "representative_image_id": group.representative_image_id if group else "",
                        "issues": "|".join(image.issues),
                    }
                )

    def _write_summary_json(self, summary_path: Path, project_run: ProjectRun) -> None:
        extension_counts = Counter(image.extension for image in project_run.images)
        issue_counts = Counter(issue for image in project_run.images for issue in image.issues)

        payload = {
            "run_id": project_run.run_id,
            "project_name": project_run.project_name,
            "source_root": project_run.source_root,
            "output_root": project_run.output_root,
            "started_at": project_run.started_at.isoformat(),
            "status": project_run.status.value,
            "image_count": len(project_run.images),
            "group_count": len(project_run.groups),
            "extension_counts": dict(sorted(extension_counts.items())),
            "issue_counts": dict(sorted(issue_counts.items())),
            "summary": project_run.summary,
        }

        with summary_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)

    def _write_run_log(self, log_path: Path, project_run: ProjectRun) -> None:
        with log_path.open("w", encoding="utf-8") as handle:
            for log in project_run.logs:
                line = f"{log.timestamp.isoformat()} [{log.level}] {log.message}"
                if log.image_id:
                    line += f" image_id={log.image_id}"
                if log.context:
                    line += f" context={json.dumps(log.context, ensure_ascii=False, sort_keys=True)}"
                handle.write(f"{line}\n")

    def _find_group_for_image(self, project_run: ProjectRun, image_id: str):
        for group in project_run.groups:
            if any(member.image_id == image_id for member in group.members):
                return group
        return None

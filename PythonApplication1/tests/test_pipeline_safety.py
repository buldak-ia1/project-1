from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from metasort.demo_setup import create_demo_input_tree
from metasort.enums import ExecutionMode
from metasort.pipeline import run_pipeline
from metasort.policy_manager import PolicyManager
from metasort.runtime_paths import workspace_root
from metasort.sample_data import build_default_policy


class PipelineSafetyTests(unittest.TestCase):
    def test_demo_mode_preserves_user_source_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            policy_path = self._write_policy(project_root)
            user_source = project_root / "user_source"
            user_source.mkdir(parents=True, exist_ok=True)
            keep_file = user_source / "keep.txt"
            keep_file.write_text("do not delete", encoding="utf-8")

            project_run = run_pipeline(
                project_root=project_root,
                source_root=user_source,
                output_root=project_root / "output",
                policy_path=policy_path,
                use_demo_input=True,
            )

            self.assertTrue(keep_file.exists())
            self.assertEqual(project_run.source_root, str((project_root / "demo_input").resolve()))

    def test_rejects_same_source_and_output_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            policy_path = self._write_policy(project_root)
            source_root = project_root / "images"
            create_demo_input_tree(source_root)

            with self.assertRaisesRegex(ValueError, "must be different"):
                run_pipeline(
                    project_root=project_root,
                    source_root=source_root,
                    output_root=source_root,
                    policy_path=policy_path,
                )

    def test_requires_source_root_when_demo_mode_is_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            policy_path = self._write_policy(project_root)

            with self.assertRaisesRegex(ValueError, "Source Root is required"):
                run_pipeline(
                    project_root=project_root,
                    source_root="",
                    output_root=project_root / "output",
                    policy_path=policy_path,
                    use_demo_input=False,
                )

    def test_rejects_nested_source_and_output_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            policy_path = self._write_policy(project_root)
            source_root = project_root / "images"
            create_demo_input_tree(source_root)

            with self.assertRaisesRegex(ValueError, "Output Root cannot be inside Source Root"):
                run_pipeline(
                    project_root=project_root,
                    source_root=source_root,
                    output_root=source_root / "nested_output",
                    policy_path=policy_path,
                )

            output_root = project_root / "output"
            output_root.mkdir(parents=True, exist_ok=True)
            nested_source = output_root / "nested_source"
            create_demo_input_tree(nested_source)

            with self.assertRaisesRegex(ValueError, "Source Root cannot be inside Output Root"):
                run_pipeline(
                    project_root=project_root,
                    source_root=nested_source,
                    output_root=output_root,
                    policy_path=policy_path,
                )

    def test_execution_mode_override_is_applied(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            for mode in (ExecutionMode.ANALYZE_ONLY, ExecutionMode.COPY):
                project_root = Path(temp_dir) / mode.value
                policy_path = self._write_policy(project_root)

                project_run = run_pipeline(
                    project_root=project_root,
                    output_root=project_root / "output",
                    policy_path=policy_path,
                    execution_mode=mode,
                    use_demo_input=True,
                )

                self.assertEqual(project_run.policy.execution_mode, mode)
                self.assertEqual(project_run.summary["organization"]["execution_mode"], mode.value)

    def test_move_mode_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            policy_path = self._write_policy(project_root)

            with self.assertRaisesRegex(ValueError, "Move mode is disabled"):
                run_pipeline(
                    project_root=project_root,
                    output_root=project_root / "output",
                    policy_path=policy_path,
                    execution_mode=ExecutionMode.MOVE,
                    use_demo_input=True,
                )

    def test_existing_sorted_outputs_are_preserved_on_copy_rerun(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            policy_path = self._write_policy(project_root)
            output_root = project_root / "output"
            existing_file = output_root / "Sorted" / "StyleFamily_001" / "Character_Miku" / "near_duplicate_001" / "miku_001.png"
            existing_file.parent.mkdir(parents=True, exist_ok=True)
            existing_file.write_text("existing output", encoding="utf-8")

            project_run = run_pipeline(
                project_root=project_root,
                output_root=output_root,
                policy_path=policy_path,
                execution_mode=ExecutionMode.COPY,
                use_demo_input=True,
            )

            self.assertTrue(existing_file.exists())
            self.assertEqual(existing_file.read_text(encoding="utf-8"), "existing output")
            self.assertGreaterEqual(project_run.summary["organization"]["preserved_existing_files"], 1)

    def test_frozen_workspace_uses_local_app_data_not_exe_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            local_app_data = Path(temp_dir) / "LocalAppData"
            fake_exe = Path(temp_dir) / "dist" / "MetaSort" / "MetaSort.exe"

            with patch("sys.frozen", True, create=True), patch("sys.executable", str(fake_exe)), patch.dict("os.environ", {"LOCALAPPDATA": str(local_app_data)}):
                self.assertEqual(workspace_root(), local_app_data / "MetaSort")

    def _write_policy(self, project_root: Path) -> Path:
        policy = build_default_policy()
        policy.extra_rules["external_model"] = {"enabled": False}
        policy_path = project_root / "config" / "classification_policy.json"
        PolicyManager().save(policy_path, policy)
        return policy_path


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from scripts.watch_raven_vnext_training import (
    STATUS_ADAPTER_FOUND_NOT_EVALUATED,
    STATUS_ADAPTER_INVALID,
    STATUS_BLOCKED,
    STATUS_EVAL_COMPLETED,
    STATUS_EVAL_COMPLETED_WITH_LIMITATIONS,
    STATUS_TRAINING_RUNNING,
    STATUS_TRAINING_SUCCEEDED,
    STATUS_TRAINING_TIMEOUT,
    current_status_path,
    watch_raven_vnext_training,
)


class WatchRavenVnextTrainingTests(unittest.TestCase):
    def test_running_status_skips_download_and_eval(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_submit_summary(root)

            result = watch_raven_vnext_training(
                root_path=root,
                cycle_id="raven_vnext_adversarial",
                expected_tar_name="raven_lora_vnext_adversarial.tar.gz",
                once=True,
                poller=lambda **_: {
                    "kaggle_status": "running",
                    "poll_summary": {"final_status": "running"},
                    "last_error": None,
                },
                download_runner=self._unexpected_download,
                eval_runner=self._unexpected_eval,
            )

            self.assertEqual(result["status_payload"]["status"], STATUS_TRAINING_RUNNING)
            self.assertEqual(json.loads(current_status_path(root).read_text(encoding="utf-8"))["status"], STATUS_TRAINING_RUNNING)

    def test_succeeded_with_valid_adapter_runs_eval(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_submit_summary(root)
            tar_path = self._make_adapter_tar(root / "mystic_data" / "cycles" / "raven_vnext_adversarial" / "kaggle_output" / "raven_lora_vnext_adversarial.tar.gz")
            eval_calls: list[Path] = []

            def fake_download_runner(**_: object) -> dict[str, object]:
                summary_path = root / "mystic_data" / "cycles" / "raven_vnext_adversarial" / "kaggle_download_summary.json"
                summary_path.parent.mkdir(parents=True, exist_ok=True)
                payload = {"adapter_tar": str(tar_path), "output_dir": str(tar_path.parent)}
                summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                return payload

            def fake_eval_runner(*, root_path: Path, adapter_tar: Path) -> dict[str, object]:
                eval_calls.append(adapter_tar)
                report_path = root_path / "mystic_data" / "training" / "raven" / "vnext_eval_report.json"
                report_path.parent.mkdir(parents=True, exist_ok=True)
                report = {
                    "after_metrics_unavailable": False,
                    "quality_comparison": {
                        "bad_candidate_refutation_rate": {"after": 1.0},
                        "first_fatal_error_coverage": {"after": 1.0},
                        "valid_overaccept_rate": {"after": 0.0},
                        "deterministic_override_alignment": {"after": 1.0},
                    },
                }
                report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
                return {"report": report}

            result = watch_raven_vnext_training(
                root_path=root,
                cycle_id="raven_vnext_adversarial",
                expected_tar_name="raven_lora_vnext_adversarial.tar.gz",
                once=True,
                poller=lambda **_: {
                    "kaggle_status": "succeeded",
                    "poll_summary": {"final_status": "complete"},
                    "last_error": None,
                },
                download_runner=fake_download_runner,
                eval_runner=fake_eval_runner,
            )

            self.assertEqual(result["status_payload"]["status"], STATUS_EVAL_COMPLETED)
            self.assertEqual(eval_calls, [tar_path.resolve()])

    def test_succeeded_with_missing_adapter_blocks_user_action(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_submit_summary(root)

            result = watch_raven_vnext_training(
                root_path=root,
                cycle_id="raven_vnext_adversarial",
                expected_tar_name="raven_lora_vnext_adversarial.tar.gz",
                once=True,
                poller=lambda **_: {
                    "kaggle_status": "succeeded",
                    "poll_summary": {"final_status": "complete"},
                    "last_error": None,
                },
                download_runner=lambda **_: {"adapter_tar": "", "output_dir": str(root / "missing")},
                eval_runner=self._unexpected_eval,
            )

            self.assertIn(result["status_payload"]["status"], {STATUS_TRAINING_SUCCEEDED, STATUS_BLOCKED})
            self.assertIn("download", result["status_payload"]["next_action"].lower())

    def test_adapter_invalid_skips_eval(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_submit_summary(root)
            tar_path = self._make_adapter_tar(
                root / "mystic_data" / "cycles" / "raven_vnext_adversarial" / "kaggle_output" / "raven_lora_vnext_adversarial.tar.gz",
                include_weights=False,
            )
            eval_called = False

            def fake_eval_runner(**_: object) -> dict[str, object]:
                nonlocal eval_called
                eval_called = True
                return {}

            result = watch_raven_vnext_training(
                root_path=root,
                cycle_id="raven_vnext_adversarial",
                expected_tar_name="raven_lora_vnext_adversarial.tar.gz",
                once=True,
                poller=lambda **_: {
                    "kaggle_status": "succeeded",
                    "poll_summary": {"final_status": "complete"},
                    "last_error": None,
                },
                download_runner=lambda **_: {"adapter_tar": str(tar_path), "output_dir": str(tar_path.parent)},
                eval_runner=fake_eval_runner,
            )

            self.assertEqual(result["status_payload"]["status"], STATUS_ADAPTER_INVALID)
            self.assertFalse(eval_called)
            self.assertIn("adapter_model.safetensors", result["status_payload"]["adapter_missing_files"])

    def test_newer_eval_report_skips_eval_unless_forced(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_submit_summary(root)
            tar_path = self._make_adapter_tar(root / "Downloads" / "raven_lora_vnext_adversarial.tar.gz")
            report_path = root / "mystic_data" / "training" / "raven" / "vnext_eval_report.json"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report = {
                "after_metrics_unavailable": False,
                "quality_comparison": {
                    "bad_candidate_refutation_rate": {"after": 1.0},
                    "first_fatal_error_coverage": {"after": 1.0},
                    "valid_overaccept_rate": {"after": 0.0},
                    "deterministic_override_alignment": {"after": 1.0},
                },
            }
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            newer_time = tar_path.stat().st_mtime + 10
            Path(report_path).touch()
            import os

            os.utime(report_path, (newer_time, newer_time))
            eval_called = False

            def fake_eval_runner(**_: object) -> dict[str, object]:
                nonlocal eval_called
                eval_called = True
                return {"report": report}

            result = watch_raven_vnext_training(
                root_path=root,
                cycle_id="raven_vnext_adversarial",
                expected_tar_name="raven_lora_vnext_adversarial.tar.gz",
                eval_only=True,
                poller=lambda **_: {"kaggle_status": "unknown", "poll_summary": {}, "last_error": None},
                download_runner=self._unexpected_download,
                eval_runner=fake_eval_runner,
            )

            self.assertEqual(result["status_payload"]["status"], STATUS_EVAL_COMPLETED)
            self.assertFalse(eval_called)

    def test_timeout_sets_training_timeout(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_submit_summary(root)

            result = watch_raven_vnext_training(
                root_path=root,
                cycle_id="raven_vnext_adversarial",
                expected_tar_name="raven_lora_vnext_adversarial.tar.gz",
                max_wait_minutes=0,
                poller=lambda **_: {
                    "kaggle_status": "running",
                    "poll_summary": {"final_status": "running"},
                    "last_error": None,
                },
                download_runner=self._unexpected_download,
                eval_runner=self._unexpected_eval,
                sleeper=lambda _: None,
            )

            self.assertEqual(result["status_payload"]["status"], STATUS_TRAINING_TIMEOUT)

    def test_missing_submit_summary_blocks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            result = watch_raven_vnext_training(
                root_path=root,
                cycle_id="raven_vnext_adversarial",
                expected_tar_name="raven_lora_vnext_adversarial.tar.gz",
            )

            self.assertEqual(result["status_payload"]["status"], STATUS_BLOCKED)
            self.assertIn("submit summary", result["status_payload"]["next_action"].lower())

    def test_failed_poll_marks_package_not_found_category(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_submit_summary(root)

            result = watch_raven_vnext_training(
                root_path=root,
                cycle_id="raven_vnext_adversarial",
                expected_tar_name="raven_lora_vnext_adversarial.tar.gz",
                once=True,
                poller=lambda **_: {
                    "kaggle_status": "failed",
                    "poll_summary": {"final_status": "failed"},
                    "last_error": "FileNotFoundError('Package tarball not found under /kaggle/input/foo')",
                },
                download_runner=self._unexpected_download,
                eval_runner=self._unexpected_eval,
            )

            self.assertEqual(result["status_payload"]["status"], "TRAINING_FAILED")
            self.assertEqual(result["status_payload"]["failure_category"], "PACKAGE_NOT_FOUND")
            self.assertIn("intentionally resubmit", result["status_payload"]["next_action"])

    def test_failed_poll_marks_kernel_script_error_category(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_submit_summary(root)

            result = watch_raven_vnext_training(
                root_path=root,
                cycle_id="raven_vnext_adversarial",
                expected_tar_name="raven_lora_vnext_adversarial.tar.gz",
                once=True,
                poller=lambda **_: {
                    "kaggle_status": "failed",
                    "poll_summary": {
                        "final_status": "failed",
                        "failure_output": {
                            "signal_payload": {
                                "error": "KeyError('\"\\'searched_roots\\'\"')",
                                "traceback": "Traceback... train_mystic_raven.py ... find_package ... searched_roots ...",
                            }
                        },
                    },
                    "last_error": "KeyError('\"\\'searched_roots\\'\"')",
                },
                download_runner=self._unexpected_download,
                eval_runner=self._unexpected_eval,
            )

            self.assertEqual(result["status_payload"]["status"], "TRAINING_FAILED")
            self.assertEqual(result["status_payload"]["failure_category"], "KERNEL_SCRIPT_ERROR")
            self.assertIn("formatting bug", result["status_payload"]["next_action"])

    def test_watcher_prefers_latest_quota_blocked_submit_over_stale_poll_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_submit_summary(
                root,
                extra={
                    "kernel_stdout": "Kernel push error: Maximum weekly GPU quota of 30.00 hours reached.",
                    "failure_category": "KAGGLE_GPU_QUOTA_EXCEEDED",
                    "training_started": False,
                    "kernel_push_succeeded": False,
                    "submit_succeeded": False,
                    "kaggle_error": "Kernel push error: Maximum weekly GPU quota of 30.00 hours reached.",
                },
            )
            poll_summary_path = root / "mystic_data" / "cycles" / "raven_vnext_adversarial" / "kaggle_poll_summary.json"
            poll_summary_path.parent.mkdir(parents=True, exist_ok=True)
            poll_summary_path.write_text(
                json.dumps(
                    {
                        "final_status": "failed",
                        "failure_output": {
                            "signal_payload": {
                                "error": "KeyError('\"\\'searched_roots\\'\"')",
                                "traceback": "Traceback... find_package ... searched_roots ...",
                            }
                        },
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = watch_raven_vnext_training(
                root_path=root,
                cycle_id="raven_vnext_adversarial",
                expected_tar_name="raven_lora_vnext_adversarial.tar.gz",
                once=True,
                poller=self._unexpected_poll,
                download_runner=self._unexpected_download,
                eval_runner=self._unexpected_eval,
            )

            self.assertEqual(result["status_payload"]["status"], STATUS_BLOCKED)
            self.assertEqual(result["status_payload"]["failure_category"], "KAGGLE_GPU_QUOTA_EXCEEDED")
            self.assertFalse(result["status_payload"]["training_started"])
            self.assertIn("quota", result["status_payload"]["next_action"].lower())
            self.assertIn("older failed run", " ".join(result["status_payload"]["warnings"]).lower())
            self.assertFalse(result["adapter_found"])
            self.assertIsNone(result["adapter_valid"])

    def test_eval_limitations_status_is_exposed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_submit_summary(root)
            tar_path = self._make_adapter_tar(root / "mystic_data" / "cycles" / "raven_vnext_adversarial" / "kaggle_output" / "raven_lora_vnext_adversarial.tar.gz")

            def fake_download_runner(**_: object) -> dict[str, object]:
                return {"adapter_tar": str(tar_path), "output_dir": str(tar_path.parent)}

            def fake_eval_runner(*, root_path: Path, adapter_tar: Path) -> dict[str, object]:
                report_path = root_path / "mystic_data" / "training" / "raven" / "vnext_eval_report.json"
                report_path.parent.mkdir(parents=True, exist_ok=True)
                report = {"after_metrics_unavailable": True, "quality_comparison": {}}
                report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
                return {"report": report}

            result = watch_raven_vnext_training(
                root_path=root,
                cycle_id="raven_vnext_adversarial",
                expected_tar_name="raven_lora_vnext_adversarial.tar.gz",
                once=True,
                poller=lambda **_: {
                    "kaggle_status": "succeeded",
                    "poll_summary": {"final_status": "complete"},
                    "last_error": None,
                },
                download_runner=fake_download_runner,
                eval_runner=fake_eval_runner,
            )

            self.assertEqual(result["status_payload"]["status"], STATUS_EVAL_COMPLETED_WITH_LIMITATIONS)

    def _write_submit_summary(self, root: Path, extra: dict[str, object] | None = None) -> None:
        summary_path = root / "mystic_data" / "cycles" / "raven_vnext_adversarial" / "kaggle_submit_summary.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "cycle_id": "raven_vnext_adversarial",
            "kaggle_username": "dyrakd",
            "dataset_ref": "dyrakd/mystic-cycle-raven-vnext-adversarial",
            "kernel_ref": "dyrakd/mystic-raven-raven-vnext-adversarial",
            "package_path": str(root / "mystic_gpu_train_package_raven_vnext_adversarial.tar.gz"),
            "output_tar_name": "raven_lora_vnext_adversarial.tar.gz",
        }
        if extra:
            payload.update(extra)
        summary_path.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

    def _make_adapter_tar(self, tar_path: Path, *, include_weights: bool = True) -> Path:
        tar_path.parent.mkdir(parents=True, exist_ok=True)
        source_dir = tar_path.parent / "source"
        adapter_dir = source_dir / "mystic_data" / "adapters" / "raven_lora_vnext_adversarial"
        adapter_dir.mkdir(parents=True, exist_ok=True)
        (adapter_dir / "adapter_config.json").write_text("{}", encoding="utf-8")
        if include_weights:
            (adapter_dir / "adapter_model.safetensors").write_text("weights", encoding="utf-8")
        with tarfile.open(tar_path, "w:gz") as archive:
            archive.add(adapter_dir / "adapter_config.json", arcname="mystic_data/adapters/raven_lora_vnext_adversarial/adapter_config.json")
            if include_weights:
                archive.add(adapter_dir / "adapter_model.safetensors", arcname="mystic_data/adapters/raven_lora_vnext_adversarial/adapter_model.safetensors")
        return tar_path.resolve()

    def _unexpected_download(self, **_: object) -> dict[str, object]:
        raise AssertionError("download should not have been called")

    def _unexpected_eval(self, **_: object) -> dict[str, object]:
        raise AssertionError("eval should not have been called")

    def _unexpected_poll(self, **_: object) -> dict[str, object]:
        raise AssertionError("poll should not have been called")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import argparse
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.run_mystic_cycle import (
    backup_and_clear_processed_ids,
    build_kaggle_commands_md,
    build_kaggle_training_script,
    create_kaggle_package,
    current_adapter_status,
    extract_last_json_object,
    locate_cycle_signal_file,
    locate_downloaded_adapter_tar,
    kaggle_dataset_create_needs_version,
    parse_kaggle_status_output,
    parse_kaggle_dataset_status_output,
    run_finish,
    run_full,
    run_prepare,
    safe_extract_adapter_tar,
    slugify,
    validate_adapter_files,
    wait_for_kaggle_dataset_ready,
    write_json,
)


class RunMysticCycleTests(unittest.TestCase):
    def test_slugify_normalizes_cycle_name(self):
        self.assertEqual(slugify("Cycle 1 / Raven"), "cycle-1-raven")

    def test_extract_last_json_object_parses_final_payload(self):
        payload = extract_last_json_object('line one\n{"processed_count": 3, "ok": true}\n')
        self.assertEqual(payload["processed_count"], 3)
        self.assertTrue(payload["ok"])

    def test_parse_kaggle_status_output(self):
        self.assertEqual(parse_kaggle_status_output("status: running"), "running")
        self.assertEqual(parse_kaggle_status_output("Kernel status: complete"), "complete")
        self.assertEqual(parse_kaggle_status_output("status: failed"), "failed")

    def test_parse_kaggle_dataset_status_output(self):
        self.assertEqual(parse_kaggle_dataset_status_output("ready"), "ready")
        self.assertEqual(parse_kaggle_dataset_status_output("Dataset status: running"), "running")
        self.assertEqual(parse_kaggle_dataset_status_output("Dataset status: failed"), "failed")

    def test_kaggle_dataset_create_needs_version(self):
        self.assertTrue(
            kaggle_dataset_create_needs_version(
                'Dataset creation error: The requested title "Mystic Cycle cycle_1" is already in use by a dataset.',
                "",
            )
        )
        self.assertFalse(kaggle_dataset_create_needs_version("Upload successful", ""))

    def test_validate_adapter_files_rejects_base_model_mismatch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            adapter_dir = Path(temp_dir) / "adapter"
            adapter_dir.mkdir(parents=True, exist_ok=True)
            (adapter_dir / "adapter_config.json").write_text(
                json.dumps({"base_model_name_or_path": "sshleifer/tiny-gpt2"}),
                encoding="utf-8",
            )
            (adapter_dir / "adapter_model.safetensors").write_text("weights", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Adapter/base model mismatch"):
                validate_adapter_files(adapter_dir, "Qwen/Qwen2.5-0.5B-Instruct")

    def test_backup_and_clear_processed_ids_preserves_backup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir) / "mystic_data"
            processed_file = base_dir / "state" / "processed_ids.jsonl"
            processed_file.parent.mkdir(parents=True, exist_ok=True)
            processed_file.write_text('{"sample_id":"s1"}\n{"sample_id":"s2"}\n', encoding="utf-8")

            payload = backup_and_clear_processed_ids(base_dir, "cycle_1")

            self.assertEqual(payload["backed_up_count"], 2)
            self.assertEqual(processed_file.read_text(encoding="utf-8"), "")
            self.assertTrue(Path(payload["backup_path"]).exists())

    def test_create_kaggle_package_skips_appledouble_and_smoke_adapter(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "scripts").mkdir()
            (root / "mystic").mkdir()
            (root / "configs").mkdir()
            (root / "mystic_data" / "train_ready").mkdir(parents=True)
            (root / "mystic_data" / "eval_holdout").mkdir(parents=True)
            (root / "mystic_data" / "metadata").mkdir(parents=True)
            (root / "mystic_data" / "adapters" / "raven_lora_tiny_gpt2_smoke").mkdir(parents=True)
            (root / "README.md").write_text("README", encoding="utf-8")
            (root / "requirements-training.txt").write_text("torch\n", encoding="utf-8")
            (root / "scripts" / "one.py").write_text("print(1)\n", encoding="utf-8")
            (root / "scripts" / "._junk").write_text("ignore\n", encoding="utf-8")
            (root / "mystic" / "two.py").write_text("print(2)\n", encoding="utf-8")
            (root / "configs" / "models.json").write_text("{}", encoding="utf-8")
            (root / "mystic_data" / "train_ready" / "raven_train.jsonl").write_text("x\n", encoding="utf-8")
            (root / "mystic_data" / "eval_holdout" / "raven_eval.jsonl").write_text("y\n", encoding="utf-8")
            (root / "mystic_data" / "metadata" / "model_versions.json").write_text('{"models":[]}', encoding="utf-8")
            (root / "mystic_data" / "adapters" / "raven_lora_tiny_gpt2_smoke" / "adapter_config.json").write_text("{}", encoding="utf-8")

            tar_path = root / "bundle.tar.gz"
            create_kaggle_package(root, tar_path)

            with tarfile.open(tar_path, "r:gz") as archive:
                names = archive.getnames()
            self.assertIn("scripts/one.py", names)
            self.assertNotIn("scripts/._junk", names)
            self.assertNotIn("mystic_data/adapters/raven_lora_tiny_gpt2_smoke/adapter_config.json", names)

    def test_build_kaggle_commands_md_contains_full_command(self):
        text = build_kaggle_commands_md(
            cycle_id="cycle_1",
            package_path=Path("/tmp/mystic_gpu_train_package_cycle_1.tar.gz"),
            adapter_path="mystic_data/adapters/raven_lora_v1",
            output_tar_name="raven_lora_v1_qwen.tar.gz",
            learning_rate=0.00015,
        )
        self.assertIn("run_mystic_cycle.py full", text)
        self.assertIn("raven_lora_v1_qwen.tar.gz", text)
        self.assertIn("--learning-rate 0.00015", text)

    def test_build_kaggle_training_script_contains_expected_steps(self):
        script = build_kaggle_training_script(
            dataset_slug="mystic-cycle-cycle-1",
            package_filename="mystic_gpu_train_package_cycle_1.tar.gz",
            base_model="Qwen/Qwen2.5-0.5B-Instruct",
            adapter_dirname="raven_lora_v0",
            output_tar_name="raven_lora_v0_qwen.tar.gz",
            learning_rate=0.00015,
            epochs=1,
            batch_size=1,
            max_length=2048,
        )
        self.assertIn("scripts/train_raven_lora.py", script)
        self.assertIn("scripts/evaluate_raven_lora.py", script)
        self.assertIn("raven_lora_v0_qwen.tar.gz", script)
        self.assertIn("mystic_cycle_signal.json", script)
        self.assertIn("cycle_done", script)
        self.assertIn("cycle_error", script)
        self.assertIn("Path(__file__).resolve().parent / PACKAGE_FILENAME", script)
        self.assertIn("Path('/kaggle/src') / PACKAGE_FILENAME", script)

    def test_safe_extract_adapter_tar_ignores_appledouble(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "src"
            source.mkdir()
            adapter_dir = source / "mystic_data" / "adapters" / "raven_lora_v1"
            adapter_dir.mkdir(parents=True)
            (adapter_dir / "adapter_config.json").write_text("{}", encoding="utf-8")
            (adapter_dir / "adapter_model.safetensors").write_text("x", encoding="utf-8")
            apple_double = source / "mystic_data" / "adapters" / "._raven_lora_v1"
            apple_double.write_text("ignore", encoding="utf-8")
            tar_path = root / "adapter.tar.gz"
            with tarfile.open(tar_path, "w:gz") as archive:
                archive.add(adapter_dir / "adapter_config.json", arcname="mystic_data/adapters/raven_lora_v1/adapter_config.json")
                archive.add(adapter_dir / "adapter_model.safetensors", arcname="mystic_data/adapters/raven_lora_v1/adapter_model.safetensors")
                archive.add(apple_double, arcname="mystic_data/adapters/._raven_lora_v1")

            extracted = safe_extract_adapter_tar(tar_path, root)
            self.assertEqual(len(extracted), 2)
            self.assertFalse((root / "mystic_data" / "adapters" / "._raven_lora_v1").exists())

    def test_locate_downloaded_adapter_tar_prefers_expected_name(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            other = output_dir / "other.tar.gz"
            expected = output_dir / "raven_lora_v0_qwen.tar.gz"
            other.write_text("x", encoding="utf-8")
            expected.write_text("y", encoding="utf-8")
            located = locate_downloaded_adapter_tar(output_dir, "raven_lora_v0_qwen.tar.gz")
            self.assertEqual(located, expected)

    def test_locate_cycle_signal_file_finds_signal(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            signal = output_dir / "mystic_cycle_signal.json"
            signal.write_text('{"status":"cycle_done"}\n', encoding="utf-8")
            located = locate_cycle_signal_file(output_dir)
            self.assertEqual(located, signal)

    def test_wait_for_kaggle_dataset_ready(self):
        responses = [
            type("Result", (), {"stdout": "running", "stderr": ""})(),
            type("Result", (), {"stdout": "ready", "stderr": ""})(),
        ]
        with patch("scripts.run_mystic_cycle.run_raw_command", side_effect=responses), patch(
            "scripts.run_mystic_cycle.time.sleep",
            return_value=None,
        ):
            payload = wait_for_kaggle_dataset_ready(
                kaggle_cmd=["python", "-m", "kaggle"],
                dataset_ref="dyrakd/mystic-cycle-cycle-1",
                cwd=Path("/tmp"),
                poll_seconds=0,
                timeout_minutes=1,
            )
        self.assertEqual(payload["final_status"], "ready")
        self.assertEqual(len(payload["checks"]), 2)

    def test_run_finish_writes_cycle_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            base_dir = repo_root / "mystic_data"
            (repo_root / "scripts").mkdir()
            (repo_root / "configs").mkdir()
            (repo_root / "mystic_data" / "eval_holdout").mkdir(parents=True)
            (repo_root / "mystic_data" / "metadata").mkdir(parents=True)
            (repo_root / "mystic_data" / "state").mkdir(parents=True)
            (repo_root / "scripts" / "mystic_loop.py").write_text("", encoding="utf-8")
            (repo_root / "scripts" / "compare_raven_models.py").write_text("", encoding="utf-8")
            (repo_root / "scripts" / "register_model.py").write_text("", encoding="utf-8")
            (repo_root / "scripts" / "train_raven_lora.py").write_text("", encoding="utf-8")
            (repo_root / "scripts" / "evaluate_raven_lora.py").write_text("", encoding="utf-8")
            (repo_root / "configs" / "models.json").write_text("{}", encoding="utf-8")
            (base_dir / "state" / "processed_ids.jsonl").write_text('{"sample_id":"old"}\n', encoding="utf-8")
            (base_dir / "eval_holdout" / "raven_eval.jsonl").write_text('{"sample_id":"eval-1"}\n', encoding="utf-8")
            write_json(base_dir / "metadata" / "model_versions.json", {"models": []})

            source_adapter = repo_root / "export" / "mystic_data" / "adapters" / "raven_lora_v1"
            source_adapter.mkdir(parents=True, exist_ok=True)
            (source_adapter / "adapter_config.json").write_text(
                json.dumps({"base_model_name_or_path": "Qwen/Qwen2.5-0.5B-Instruct"}),
                encoding="utf-8",
            )
            (source_adapter / "adapter_model.safetensors").write_text("weights", encoding="utf-8")

            adapter_tar = repo_root / "raven_lora_v1_qwen.tar.gz"
            with tarfile.open(adapter_tar, "w:gz") as archive:
                archive.add(source_adapter / "adapter_config.json", arcname="mystic_data/adapters/raven_lora_v1/adapter_config.json")
                archive.add(source_adapter / "adapter_model.safetensors", arcname="mystic_data/adapters/raven_lora_v1/adapter_model.safetensors")

            args = argparse.Namespace(
                adapter_tar=str(adapter_tar),
                adapter_path="mystic_data/adapters/raven_lora_v1",
                base_model="Qwen/Qwen2.5-0.5B-Instruct",
                cycle_id="cycle_1",
                run_limit=5,
                compare_limit=10,
                model_id="raven_lora_v1",
                base_dir=str(base_dir),
                run_id="cycle_1_reinjection",
                notes="test run",
            )

            side_effects = [
                (
                    {"processed_count": 2, "run_id": "cycle_1_reinjection"},
                    '{"processed_count": 2, "run_id": "cycle_1_reinjection"}',
                ),
                (
                    {"metrics": {"adapter_better_or_equal_rate": 1.0}},
                    '{"metrics": {"adapter_better_or_equal_rate": 1.0}}',
                ),
                (
                    {"registered_model": {"model_id": "raven_lora_v1"}},
                    '{"registered_model": {"model_id": "raven_lora_v1"}}',
                ),
            ]

            with patch("scripts.run_mystic_cycle.ROOT", repo_root), patch(
                "scripts.run_mystic_cycle.run_command",
                side_effect=side_effects,
            ):
                result = run_finish(args)

            self.assertEqual(result, 0)
            summary_path = base_dir / "cycles" / "cycle_1" / "summary.json"
            self.assertTrue(summary_path.exists())
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["processed_count"], 2)
            self.assertEqual(payload["adapter_better_or_equal_rate"], 1.0)

    def test_current_adapter_status_reports_latest_registry_entry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            base_dir = repo_root / "mystic_data"
            adapter_dir = repo_root / "mystic_data" / "adapters" / "raven_lora_v0"
            adapter_dir.mkdir(parents=True, exist_ok=True)
            (base_dir / "metadata").mkdir(parents=True, exist_ok=True)
            (adapter_dir / "adapter_config.json").write_text(
                json.dumps({"base_model_name_or_path": "Qwen/Qwen2.5-0.5B-Instruct"}),
                encoding="utf-8",
            )
            write_json(
                base_dir / "metadata" / "model_versions.json",
                {
                    "models": [
                        {
                            "model_id": "raven_lora_v0_qwen_0_5b",
                            "adapter_path": "mystic_data/adapters/raven_lora_v0",
                        }
                    ]
                },
            )

            with patch("scripts.run_mystic_cycle.ROOT", repo_root):
                payload = current_adapter_status(base_dir)

            self.assertTrue(payload["adapter_exists"])
            self.assertEqual(payload["adapter_base_model"], "Qwen/Qwen2.5-0.5B-Instruct")

    def test_run_prepare_writes_prepare_summary_and_kaggle_commands(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            base_dir = repo_root / "mystic_data"
            (repo_root / "scripts").mkdir()
            (repo_root / "configs").mkdir()
            (base_dir / "train_ready").mkdir(parents=True)
            (base_dir / "eval_holdout").mkdir(parents=True)
            (base_dir / "metadata").mkdir(parents=True)
            (repo_root / "scripts" / "mystic_loop.py").write_text("", encoding="utf-8")
            (repo_root / "scripts" / "compare_raven_models.py").write_text("", encoding="utf-8")
            (repo_root / "scripts" / "register_model.py").write_text("", encoding="utf-8")
            (repo_root / "scripts" / "train_raven_lora.py").write_text("", encoding="utf-8")
            (repo_root / "scripts" / "evaluate_raven_lora.py").write_text("", encoding="utf-8")
            (repo_root / "configs" / "models.json").write_text("{}", encoding="utf-8")
            (repo_root / "README.md").write_text("README", encoding="utf-8")
            (repo_root / "requirements-training.txt").write_text("torch\n", encoding="utf-8")
            (base_dir / "train_ready" / "raven_lora.jsonl").write_text('{"x":1}\n', encoding="utf-8")
            (base_dir / "train_ready" / "raven_train.jsonl").write_text('{"x":1}\n', encoding="utf-8")
            (base_dir / "eval_holdout" / "raven_eval.jsonl").write_text('{"x":1}\n', encoding="utf-8")

            args = argparse.Namespace(
                cycle_id="cycle_1",
                base_dir=str(base_dir),
                package_out="",
                run_prepare_data=False,
                limit=0,
                train_limit=1000,
                eval_limit=100,
                base_model="Qwen/Qwen2.5-0.5B-Instruct",
                adapter_path="mystic_data/adapters/raven_lora_v1",
                learning_rate=0.00015,
                epochs=1,
                batch_size=1,
                max_length=2048,
            )

            with patch("scripts.run_mystic_cycle.ROOT", repo_root), patch(
                "scripts.run_mystic_cycle.run_command",
                return_value=({"row_count": 1}, '{"row_count": 1}'),
            ):
                result = run_prepare(args)

            self.assertEqual(result, 0)
            self.assertTrue((base_dir / "cycles" / "cycle_1" / "prepare_summary.json").exists())
            self.assertTrue((base_dir / "cycles" / "cycle_1" / "kaggle_commands.md").exists())
            payload = json.loads((base_dir / "cycles" / "cycle_1" / "prepare_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["requested_split"]["train_limit"], 1000)
            self.assertEqual(payload["requested_split"]["eval_limit"], 100)

    def test_run_full_chains_prepare_submit_poll_download_and_finish(self):
        args = argparse.Namespace(
            cycle_id="cycle_1",
            base_dir="/tmp/mystic_data",
            run_prepare_data=True,
            limit=500,
            train_limit=1000,
            eval_limit=100,
            package_out="",
            kaggle_username="tester",
            dataset_slug="mystic-cycle-cycle-1",
            kernel_slug="mystic-raven-cycle-1",
            base_model="Qwen/Qwen2.5-0.5B-Instruct",
            adapter_path="mystic_data/adapters/raven_lora_v0",
            model_id="raven_lora_v0_qwen_auto",
            output_tar_name="raven_lora_v0_qwen.tar.gz",
            learning_rate=0.00015,
            epochs=1,
            batch_size=1,
            max_length=2048,
            run_limit=20,
            compare_limit=10,
            poll_seconds=1,
            timeout_minutes=1,
            notes="",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir) / "mystic_data"
            cycle_root = base_dir / "cycles" / "cycle_1"
            cycle_root.mkdir(parents=True, exist_ok=True)
            write_json(
                cycle_root / "kaggle_download_summary.json",
                {"adapter_tar": "/tmp/raven_lora_v0_qwen.tar.gz"},
            )
            with patch("scripts.run_mystic_cycle.run_prepare", return_value=0) as prepare_mock, patch(
                "scripts.run_mystic_cycle.run_submit",
                return_value=0,
            ) as submit_mock, patch(
                "scripts.run_mystic_cycle.run_poll",
                return_value=0,
            ) as poll_mock, patch(
                "scripts.run_mystic_cycle.run_download",
                return_value=0,
            ) as download_mock, patch(
                "scripts.run_mystic_cycle.run_finish",
                return_value=0,
            ) as finish_mock:
                args.base_dir = str(base_dir)
                result = run_full(args)

            self.assertEqual(result, 0)
            prepare_mock.assert_called_once()
            submit_mock.assert_called_once()
            poll_mock.assert_called_once()
            download_mock.assert_called_once()
            finish_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()

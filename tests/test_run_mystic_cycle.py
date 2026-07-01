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
    discover_package_tar,
    extract_last_json_object,
    locate_cycle_signal_file,
    locate_downloaded_adapter_tar,
    kaggle_dataset_create_needs_version,
    parse_kaggle_status_output,
    parse_kaggle_dataset_status_output,
    run_finish,
    run_full,
    run_prepare,
    run_submit,
    safe_extract_adapter_tar,
    slugify,
    validate_adapter_files,
    wait_for_kaggle_dataset_ready,
    write_kaggle_kernel_metadata,
    write_json,
)


def _load_generated_kernel_namespace(**overrides: object) -> tuple[str, dict[str, object]]:
    script = build_kaggle_training_script(
        cycle_id=str(overrides.get("cycle_id", "raven_vnext_adversarial")),
        dataset_slug=str(overrides.get("dataset_slug", "mystic-cycle-raven-vnext-adversarial")),
        package_filename=str(
            overrides.get(
                "package_filename",
                "mystic_gpu_train_package_raven_vnext_adversarial.tar.gz",
            )
        ),
        base_model=str(overrides.get("base_model", "Qwen/Qwen2.5-0.5B-Instruct")),
        adapter_path=str(
            overrides.get(
                "adapter_path",
                "mystic_data/adapters/raven_lora_vnext_adversarial",
            )
        ),
        adapter_dirname=str(overrides.get("adapter_dirname", "raven_lora_vnext_adversarial")),
        output_tar_name=str(
            overrides.get("output_tar_name", "raven_lora_vnext_adversarial.tar.gz")
        ),
        learning_rate=float(overrides.get("learning_rate", 0.0002)),
        epochs=int(overrides.get("epochs", 1)),
        batch_size=int(overrides.get("batch_size", 1)),
        max_length=int(overrides.get("max_length", 2048)),
    )
    prefix = script.split("write_signal('starting'", 1)[0]
    namespace: dict[str, object] = {"__file__": "train_mystic_raven.py"}
    exec(compile(prefix, "train_mystic_raven.py", "exec"), namespace)
    return script, namespace


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
            cycle_id="cycle_1",
            dataset_slug="mystic-cycle-cycle-1",
            package_filename="mystic_gpu_train_package_cycle_1.tar.gz",
            base_model="Qwen/Qwen2.5-0.5B-Instruct",
            adapter_path="mystic_data/adapters/raven_lora_v0",
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
        self.assertIn('PACKAGE_FILENAME = "mystic_gpu_train_package_cycle_1.tar.gz"', script)
        self.assertIn("discover_package_candidates", script)
        self.assertIn("EXPECTED_KAGGLE_INPUT_DIR", script)
        self.assertIn("limited_directory_listing", script)
        self.assertIn("Path('/kaggle/input')", script)
        self.assertIn("PACKAGE_KEYWORDS", script)
        self.assertIn("range(60)", script)

    def test_build_kaggle_training_script_compiles_for_raven_vnext_cycle(self):
        script, _ = _load_generated_kernel_namespace()
        compile(script, "train_mystic_raven.py", "exec")
        self.assertIn(
            'PACKAGE_FILENAME = "mystic_gpu_train_package_raven_vnext_adversarial.tar.gz"',
            script,
        )

    def test_build_kaggle_training_script_has_no_unresolved_placeholders(self):
        script, _ = _load_generated_kernel_namespace()
        for forbidden in [
            "$EXPECTED_PACKAGE_FILENAME",
            "$OUTPUT_TAR_NAME",
            "{searched_roots}",
            '"\'searched_roots\'"',
        ]:
            self.assertNotIn(forbidden, script)

    def test_generated_find_package_prefers_exact_filename(self):
        _, namespace = _load_generated_kernel_namespace()
        find_package = namespace["find_package"]

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_root = root / "kaggle" / "input"
            dataset_root = input_root / "mystic-cycle-raven-vnext-adversarial"
            dataset_root.mkdir(parents=True, exist_ok=True)
            exact = dataset_root / "mystic_gpu_train_package_raven_vnext_adversarial.tar.gz"
            exact.write_text("exact", encoding="utf-8")
            fallback = dataset_root / "something_mystic_raven_vnext_adversarial.tar.gz"
            fallback.write_text("fallback", encoding="utf-8")

            selected, diagnostics = find_package(
                search_roots=[input_root, dataset_root],
                local_candidates=[],
            )

            self.assertEqual(selected, exact)
            self.assertEqual(diagnostics["selected_candidate"], str(exact))

    def test_generated_find_package_falls_back_to_keyword_match(self):
        _, namespace = _load_generated_kernel_namespace()
        find_package = namespace["find_package"]

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_root = root / "kaggle" / "input"
            dataset_root = input_root / "mystic-cycle-raven-vnext-adversarial"
            dataset_root.mkdir(parents=True, exist_ok=True)
            fallback = dataset_root / "something_mystic_raven_vnext_adversarial.tar.gz"
            fallback.write_text("fallback", encoding="utf-8")

            selected, diagnostics = find_package(
                search_roots=[input_root, dataset_root],
                local_candidates=[],
            )

            self.assertEqual(selected, fallback)
            self.assertEqual(diagnostics["selected_candidate"], str(fallback))

    def test_generated_find_package_failure_raises_runtime_error_with_diagnostics(self):
        _, namespace = _load_generated_kernel_namespace()
        find_package = namespace["find_package"]
        package_discovery_error = namespace["PackageDiscoveryError"]

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_root = root / "kaggle" / "input"
            input_root.mkdir(parents=True, exist_ok=True)

            with self.assertRaises(package_discovery_error) as context:
                find_package(search_roots=[input_root], local_candidates=[])

            message = str(context.exception)
            self.assertIn("expected_package_filename", message)
            self.assertIn("searched_roots", message)
            self.assertTrue("candidates=" in message or "candidate_paths=" in message)
            self.assertIn("input_listing", message)
            self.assertNotIn("KeyError", message)

    def test_discover_package_tar_prefers_exact_filename(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_root = Path(temp_dir) / "kaggle" / "input"
            dataset_root = input_root / "datasets"
            dataset_root.mkdir(parents=True, exist_ok=True)
            expected = dataset_root / "mystic_gpu_train_package_raven_vnext_adversarial.tar.gz"
            expected.write_text("x", encoding="utf-8")
            fallback = dataset_root / "mystic_other.tar.gz"
            fallback.write_text("y", encoding="utf-8")

            selected, diagnostics = discover_package_tar(
                [input_root, dataset_root],
                expected_filename=expected.name,
                dataset_slug="mystic-cycle-raven-vnext-adversarial",
            )

            self.assertEqual(selected, expected)
            self.assertEqual(diagnostics["expected_filename"], expected.name)

    def test_discover_package_tar_falls_back_to_matching_tar(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_root = Path(temp_dir) / "kaggle" / "input"
            dataset_root = input_root / "datasets"
            dataset_root.mkdir(parents=True, exist_ok=True)
            fallback = dataset_root / "mystic_raven_vnext_candidate.tar.gz"
            fallback.write_text("weights", encoding="utf-8")

            selected, diagnostics = discover_package_tar(
                [input_root, dataset_root],
                expected_filename="missing.tar.gz",
                dataset_slug="datasets",
            )

            self.assertEqual(selected, fallback)
            self.assertEqual(diagnostics["candidates"][0]["path"], str(fallback))

    def test_discover_package_tar_errors_with_diagnostics(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_root = Path(temp_dir) / "kaggle" / "input"
            input_root.mkdir(parents=True, exist_ok=True)

            with self.assertRaisesRegex(FileNotFoundError, "expected_filename"):
                discover_package_tar(
                    [input_root],
                    expected_filename="missing.tar.gz",
                    dataset_slug="mystic-cycle-raven-vnext-adversarial",
                )

    def test_write_kaggle_kernel_metadata_includes_dataset_sources(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            kernel_dir = Path(temp_dir)
            path = write_kaggle_kernel_metadata(
                kernel_dir,
                kernel_ref="dyrakd/mystic-raven-cycle-1",
                title="Mystic Raven cycle_1",
                dataset_ref="dyrakd/mystic-cycle-cycle-1",
            )
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["dataset_data_sources"], ["dyrakd/mystic-cycle-cycle-1"])
            self.assertEqual(payload["dataset_sources"], ["dyrakd/mystic-cycle-cycle-1"])

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
                dataset_source="default",
                target="raven",
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
            self.assertEqual(payload["dataset_source"], "default")

    def test_run_submit_writes_extended_submit_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            base_dir = repo_root / "mystic_data"
            cycle_root = base_dir / "cycles" / "cycle_1"
            cycle_root.mkdir(parents=True, exist_ok=True)
            (repo_root / "scripts").mkdir()
            (repo_root / "configs").mkdir()
            (repo_root / "README.md").write_text("README", encoding="utf-8")
            (repo_root / "requirements-training.txt").write_text("torch\n", encoding="utf-8")
            for script_name in ["mystic_loop.py", "compare_raven_models.py", "register_model.py", "train_raven_lora.py", "evaluate_raven_lora.py"]:
                (repo_root / "scripts" / script_name).write_text("", encoding="utf-8")
            (repo_root / "configs" / "models.json").write_text("{}", encoding="utf-8")
            package_path = repo_root / "mystic_gpu_train_package_cycle_1.tar.gz"
            package_path.write_text("package", encoding="utf-8")
            write_json(
                cycle_root / "prepare_summary.json",
                {"package_path": str(package_path)},
            )

            args = argparse.Namespace(
                cycle_id="cycle_1",
                base_dir=str(base_dir),
                kaggle_username="dyrakd",
                dataset_slug="",
                kernel_slug="",
                package_path=str(package_path),
                base_model="Qwen/Qwen2.5-0.5B-Instruct",
                adapter_path="mystic_data/adapters/raven_lora_vnext_adversarial",
                output_tar_name="raven_lora_vnext_adversarial.tar.gz",
                learning_rate=0.00015,
                epochs=1,
                batch_size=1,
                max_length=2048,
            )

            raw_results = [
                type("Result", (), {"stdout": "dataset uploaded", "stderr": ""})(),
                type("Result", (), {"stdout": "kernel pushed", "stderr": ""})(),
            ]
            with patch("scripts.run_mystic_cycle.ROOT", repo_root), patch(
                "scripts.run_mystic_cycle.ensure_kaggle_ready",
                return_value="dyrakd",
            ), patch(
                "scripts.run_mystic_cycle.kaggle_command_prefix",
                return_value=["kaggle"],
            ), patch(
                "scripts.run_mystic_cycle.run_raw_command",
                side_effect=raw_results,
            ), patch(
                "scripts.run_mystic_cycle.wait_for_kaggle_dataset_ready",
                return_value={"final_status": "ready", "checks": []},
            ), patch(
                "scripts.run_mystic_cycle.wait_for_dataset_visibility_stabilization",
                return_value=None,
            ):
                result = run_submit(args)

            self.assertEqual(result, 0)
            summary = json.loads((cycle_root / "kaggle_submit_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["package_filename"], "mystic_gpu_train_package_cycle_1.tar.gz")
            self.assertEqual(summary["dataset_slug"], "mystic-cycle-cycle-1")
            self.assertEqual(summary["kernel_ref"], "dyrakd/mystic-raven-cycle-1")
            self.assertEqual(summary["output_tar_name"], "raven_lora_vnext_adversarial.tar.gz")
            self.assertEqual(summary["expected_kaggle_input_dir"], "/kaggle/input/mystic-cycle-cycle-1")
            self.assertIn("generated_kernel_path", summary)
            self.assertTrue(summary["submit_validation"]["kernel_contains_discovery_helper"])

    def test_run_submit_classifies_kaggle_gpu_quota_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            base_dir = repo_root / "mystic_data"
            cycle_root = base_dir / "cycles" / "raven_vnext_adversarial"
            (repo_root / "scripts").mkdir()
            (repo_root / "configs").mkdir()
            (base_dir / "metadata").mkdir(parents=True)
            (repo_root / "scripts" / "mystic_loop.py").write_text("", encoding="utf-8")
            (repo_root / "scripts" / "compare_raven_models.py").write_text("", encoding="utf-8")
            (repo_root / "scripts" / "register_model.py").write_text("", encoding="utf-8")
            (repo_root / "scripts" / "train_raven_lora.py").write_text("", encoding="utf-8")
            (repo_root / "scripts" / "evaluate_raven_lora.py").write_text("", encoding="utf-8")
            (repo_root / "configs" / "models.json").write_text("{}", encoding="utf-8")
            (repo_root / "README.md").write_text("README", encoding="utf-8")
            (repo_root / "requirements-training.txt").write_text("torch\n", encoding="utf-8")
            package_path = repo_root / "mystic_gpu_train_package_raven_vnext_adversarial.tar.gz"
            package_path.write_text("package", encoding="utf-8")
            write_json(cycle_root / "prepare_summary.json", {"package_path": str(package_path)})

            args = argparse.Namespace(
                cycle_id="raven_vnext_adversarial",
                base_dir=str(base_dir),
                kaggle_username="dyrakd",
                dataset_slug="",
                kernel_slug="",
                package_path=str(package_path),
                base_model="Qwen/Qwen2.5-0.5B-Instruct",
                adapter_path="mystic_data/adapters/raven_lora_vnext_adversarial",
                output_tar_name="raven_lora_vnext_adversarial.tar.gz",
                learning_rate=0.00015,
                epochs=1,
                batch_size=1,
                max_length=2048,
            )

            raw_results = [
                type("Result", (), {"stdout": "dataset uploaded", "stderr": ""})(),
                type(
                    "Result",
                    (),
                    {
                        "stdout": "Kernel push error: Maximum weekly GPU quota of 30.00 hours reached.",
                        "stderr": "",
                    },
                )(),
            ]
            with patch("scripts.run_mystic_cycle.ROOT", repo_root), patch(
                "scripts.run_mystic_cycle.ensure_kaggle_ready",
                return_value="dyrakd",
            ), patch(
                "scripts.run_mystic_cycle.kaggle_command_prefix",
                return_value=["kaggle"],
            ), patch(
                "scripts.run_mystic_cycle.run_raw_command",
                side_effect=raw_results,
            ), patch(
                "scripts.run_mystic_cycle.wait_for_kaggle_dataset_ready",
                return_value={"final_status": "ready", "checks": []},
            ), patch(
                "scripts.run_mystic_cycle.wait_for_dataset_visibility_stabilization",
                return_value=None,
            ):
                result = run_submit(args)

            self.assertEqual(result, 1)
            summary = json.loads((cycle_root / "kaggle_submit_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["failure_category"], "KAGGLE_GPU_QUOTA_EXCEEDED")
            self.assertFalse(summary["training_started"])
            self.assertFalse(summary["kernel_push_succeeded"])
            self.assertFalse(summary["submit_succeeded"])
            self.assertIn("quota", summary["next_action"].lower())

    def test_run_prepare_supports_research_table_dataset_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            base_dir = repo_root / "mystic_data"
            (repo_root / "scripts").mkdir()
            (repo_root / "configs").mkdir()
            (base_dir / "datasets" / "raven").mkdir(parents=True)
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

            args = argparse.Namespace(
                cycle_id="cycle_rt",
                base_dir=str(base_dir),
                package_out="",
                run_prepare_data=True,
                dataset_source="research_table",
                target="raven",
                limit=0,
                train_limit=10,
                eval_limit=1,
                base_model="Qwen/Qwen2.5-0.5B-Instruct",
                adapter_path="mystic_data/adapters/raven_lora_v1",
                learning_rate=0.00015,
                epochs=1,
                batch_size=1,
                max_length=2048,
            )

            prepared_rows = [
                {
                    "sample_id": "rt-1",
                    "problem": "p1",
                    "proof_attempt": "proof1",
                    "messages": [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}, {"role": "assistant", "content": "{\"verdict\":\"INVALID\"}"}],
                    "assistant_output": "{\"verdict\":\"INVALID\"}",
                    "target_verdict": "INVALID",
                },
                {
                    "sample_id": "rt-2",
                    "problem": "p2",
                    "proof_attempt": "proof2",
                    "messages": [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}, {"role": "assistant", "content": "{\"verdict\":\"VALID\"}"}],
                    "assistant_output": "{\"verdict\":\"VALID\"}",
                    "target_verdict": "VALID",
                },
            ]

            def fake_run_command(command, *, cwd):
                self.assertTrue(any(part.endswith("prepare_research_table_training.py") for part in command))
                output_index = command.index("--output") + 1
                prepared_path = Path(command[output_index])
                prepared_path.parent.mkdir(parents=True, exist_ok=True)
                prepared_path.write_text("\n".join(json.dumps(row) for row in prepared_rows) + "\n", encoding="utf-8")
                return (
                    {"rows_written": 2, "output_path": str(prepared_path)},
                    json.dumps({"rows_written": 2, "output_path": str(prepared_path)}),
                )

            with patch("scripts.run_mystic_cycle.ROOT", repo_root), patch(
                "scripts.run_mystic_cycle.run_command",
                side_effect=fake_run_command,
            ):
                result = run_prepare(args)

            self.assertEqual(result, 0)
            summary = json.loads((base_dir / "cycles" / "cycle_rt" / "prepare_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["dataset_source"], "research_table")
            self.assertEqual(summary["target_agent"], "raven")
            self.assertEqual(summary["training_split_payload"]["prepared_rows"], 2)
            self.assertEqual(summary["export_payload"]["rows_written"], 2)
            self.assertTrue((base_dir / "train_ready" / "raven_train.jsonl").exists())
            self.assertTrue((base_dir / "eval_holdout" / "raven_eval.jsonl").exists())

    def test_run_prepare_packages_combined_research_table_and_adversarial_counts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            base_dir = repo_root / "mystic_data"
            (repo_root / "scripts").mkdir()
            (repo_root / "mystic").mkdir()
            (repo_root / "configs").mkdir()
            (base_dir / "datasets" / "raven").mkdir(parents=True)
            (base_dir / "train_ready").mkdir(parents=True)
            (base_dir / "eval_holdout").mkdir(parents=True)
            (base_dir / "metadata").mkdir(parents=True)
            for script_name in [
                "mystic_loop.py",
                "compare_raven_models.py",
                "register_model.py",
                "train_raven_lora.py",
                "evaluate_raven_lora.py",
            ]:
                (repo_root / "scripts" / script_name).write_text("", encoding="utf-8")
            (repo_root / "configs" / "models.json").write_text("{}", encoding="utf-8")
            (repo_root / "README.md").write_text("README", encoding="utf-8")
            (repo_root / "requirements-training.txt").write_text("torch\n", encoding="utf-8")
            adversarial_path = base_dir / "datasets" / "raven" / "adversarial_seed_raven.jsonl"
            adversarial_path.write_text('{"agent":"raven"}\n', encoding="utf-8")

            args = argparse.Namespace(
                cycle_id="cycle_combined",
                base_dir=str(base_dir),
                package_out="",
                run_prepare_data=False,
                dataset_source="research_table",
                target="raven",
                include_adversarial_seeds=True,
                adversarial_path=str(adversarial_path),
                min_invalid_rows=5,
                allow_low_invalid=False,
                limit=0,
                train_limit=10,
                eval_limit=2,
                base_model="Qwen/Qwen2.5-0.5B-Instruct",
                adapter_path="mystic_data/adapters/raven_lora_vnext",
                learning_rate=0.00015,
                epochs=1,
                batch_size=1,
                max_length=2048,
            )

            prepared_rows = [
                {
                    "sample_id": f"combined-{index}",
                    "problem": "p",
                    "proof_attempt": "proof",
                    "messages": [],
                    "assistant_output": '{"verdict":"INVALID"}',
                    "target_verdict": "INVALID",
                    "metadata": {"dataset_source": "adversarial_seed"},
                }
                for index in range(6)
            ]

            def fake_run_command(command, *, cwd):
                self.assertIn("--include-adversarial-seeds", command)
                self.assertIn("--min-invalid-rows", command)
                output_index = command.index("--output") + 1
                prepared_path = Path(command[output_index])
                prepared_path.parent.mkdir(parents=True, exist_ok=True)
                prepared_path.write_text(
                    "\n".join(json.dumps(row) for row in prepared_rows) + "\n",
                    encoding="utf-8",
                )
                manifest = {
                    "rows_written": 6,
                    "research_table_rows": 1,
                    "adversarial_seed_rows": 5,
                    "combined_rows": 6,
                    "invalid_rows_count": 6,
                }
                (prepared_path.parent / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
                return manifest, json.dumps(manifest)

            with patch("scripts.run_mystic_cycle.ROOT", repo_root), patch(
                "scripts.run_mystic_cycle.run_command",
                side_effect=fake_run_command,
            ):
                result = run_prepare(args)

            self.assertEqual(result, 0)
            summary_path = base_dir / "cycles" / "cycle_combined" / "prepare_summary.json"
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary["package_manifest"]["adversarial_seed_rows"], 5)
            self.assertEqual(summary["package_manifest"]["combined_rows"], 6)
            package_path = Path(summary["package_path"])
            with tarfile.open(package_path, "r:gz") as archive:
                names = archive.getnames()
            self.assertIn("mystic_data/train_ready/raven_train.jsonl", names)
            self.assertIn("mystic_data/eval_holdout/raven_eval.jsonl", names)
            self.assertIn("mystic_data/training/raven/package_manifest.json", names)

    def test_run_full_chains_prepare_submit_poll_download_and_finish(self):
        args = argparse.Namespace(
            cycle_id="cycle_1",
            base_dir="/tmp/mystic_data",
            run_prepare_data=True,
            dataset_source="default",
            target="raven",
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

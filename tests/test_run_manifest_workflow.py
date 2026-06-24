from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.run_manifest_workflow import (
    collect_data_status,
    default_hf_slugs,
    extract_last_json_object,
    load_training_targets,
    run_status,
    run_workflow,
    write_json,
)


class RunManifestWorkflowTests(unittest.TestCase):
    def test_extract_last_json_object_reads_final_payload(self):
        payload = extract_last_json_object("line\n{\"ok\": true, \"count\": 2}\n")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["count"], 2)

    def test_default_hf_slugs_include_numina(self):
        slugs = default_hf_slugs()
        self.assertIn("numinamath_cot", slugs)
        self.assertIn("proofnet", slugs)

    def test_load_training_targets_returns_priority_order(self):
        targets = load_training_targets(Path("/Users/JYH/Documents/Mystic"))
        self.assertGreaterEqual(len(targets), 1)
        self.assertEqual(targets[0]["agent"], "raven")

    def test_collect_data_status_counts_jsonl_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir) / "mystic_data"
            (base_dir / "raw").mkdir(parents=True)
            (base_dir / "internal").mkdir(parents=True)
            (base_dir / "processed" / "internal_mystic_data").mkdir(parents=True)
            (base_dir / "train_ready").mkdir(parents=True)
            (base_dir / "eval_holdout").mkdir(parents=True)
            (base_dir / "raw" / "numina_math_cot_100.jsonl").write_text('{"id":1}\n{"id":2}\n', encoding="utf-8")
            (base_dir / "internal" / "raven_critiques.jsonl").write_text('{"id":1}\n', encoding="utf-8")
            (base_dir / "processed" / "internal_mystic_data" / "raven_critiques.jsonl").write_text('{"id":1}\n', encoding="utf-8")
            (base_dir / "train_ready" / "raven_train.jsonl").write_text('{"id":1}\n', encoding="utf-8")
            (base_dir / "eval_holdout" / "raven_eval.jsonl").write_text('{"id":1}\n', encoding="utf-8")

            payload = collect_data_status(base_dir)
            self.assertEqual(payload["numina_rows"], 2)
            self.assertEqual(payload["raven_critiques_rows"], 1)

    def test_run_workflow_writes_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir) / "mystic_data"
            side_effects = [
                ({"ok": "init"}, '{"ok":"init"}'),
                ({"ok": "seed"}, '{"ok":"seed"}'),
                ({"ok": "resolve"}, '{"ok":"resolve"}'),
                ({"results": []}, '{"results": []}'),
                ({"final_count": 1100}, '{"final_count": 1100}'),
                ({"row_count": 10}, '{"row_count": 10}'),
                ({"train_rows": 9, "eval_rows": 1}, '{"train_rows": 9, "eval_rows": 1}'),
                ({"row_counts": {"raven": 1}}, '{"row_counts": {"raven": 1}}'),
                ({"plan": {"agent": "raven"}}, '{"plan": {"agent": "raven"}}'),
                ({"plan": {"agent": "forge"}}, '{"plan": {"agent": "forge"}}'),
                ({"plan": {"agent": "prime"}}, '{"plan": {"agent": "prime"}}'),
                ({"plan": {"agent": "lean"}}, '{"plan": {"agent": "lean"}}'),
                ({"plan": {"agent": "core"}}, '{"plan": {"agent": "core"}}'),
                ({"plan": {"agent": "pattern"}}, '{"plan": {"agent": "pattern"}}'),
                ({"plan": {"agent": "physics"}}, '{"plan": {"agent": "physics"}}'),
                ({"plan": {"agent": "chem"}}, '{"plan": {"agent": "chem"}}'),
                ({"plan": {"agent": "biomath"}}, '{"plan": {"agent": "biomath"}}'),
                ({"plan": {"agent": "report"}}, '{"plan": {"agent": "report"}}'),
                ({"cycle_id": "cycle_1"}, '{"cycle_id": "cycle_1"}'),
            ]
            args = argparse.Namespace(
                workflow_id="wf_1",
                base_dir=str(base_dir),
                seed_internal=True,
                max_hf_rows=1,
                hf_slugs=[],
                numina_limit=1100,
                raven_prepare_limit=500,
                train_limit=1000,
                eval_limit=100,
                run_cycle_prepare=True,
                cycle_id="cycle_1",
                base_model="Qwen/Qwen2.5-0.5B-Instruct",
                adapter_path="mystic_data/adapters/raven_lora_v1",
                learning_rate=0.00015,
                training_backend="manual",
                execute_training=False,
                step_timeout_seconds=120,
                continue_on_error=False,
            )

            with patch("scripts.run_manifest_workflow.verify_project_root"), patch(
                "scripts.run_manifest_workflow.run_json_command",
                side_effect=side_effects,
            ), patch(
                "scripts.run_manifest_workflow.collect_data_status",
                return_value={"numina_rows": 1100},
            ):
                result = run_workflow(args)

            self.assertEqual(result, 0)
            summary_path = base_dir / "workflows" / "wf_1" / "summary.json"
            self.assertTrue(summary_path.exists())
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["download_numina_sample"]["final_count"], 1100)
            self.assertEqual(len(payload["training_targets"]), 10)

    def test_run_status_prints_latest_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir) / "mystic_data"
            summary_path = base_dir / "workflows" / "wf_1" / "summary.json"
            write_json(summary_path, {"workflow_id": "wf_1"})
            args = argparse.Namespace(base_dir=str(base_dir), limit=5)

            with patch("scripts.run_manifest_workflow.verify_project_root"), patch(
                "scripts.run_manifest_workflow.collect_data_status",
                return_value={"numina_rows": 1},
            ):
                result = run_status(args)

            self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()

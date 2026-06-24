from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mystic.training.bootstrap import init_internal_data_files, write_train_ready_seed
from mystic.training.launcher import build_training_plan
from mystic.training.prepare import prepare_train_ready_datasets


class TrainingPrepareTests(unittest.TestCase):
    def test_prepare_routes_internal_records_to_specialists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            init_internal_data_files(base)
            write_train_ready_seed(base)
            internal_root = base / "processed" / "internal_mystic_data"
            record = {
                "record_type": "raven_critiques",
                "instruction": "Critique the proof.",
                "input": "Proof uses an unsupported equivalence.",
                "output": "Unsupported equivalence detected.",
                "status": "GAP",
                "metadata": {"source": "test", "created_at": "2026-06-23T00:00:00Z"},
            }
            (internal_root / "raven_critiques.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")

            result = prepare_train_ready_datasets(base)
            self.assertGreaterEqual(result["row_counts"]["raven"], 1)
            raven_file = base / "train_ready" / "raven_train_ready.jsonl"
            self.assertTrue(raven_file.exists())

    def test_build_training_plan_reads_config(self):
        root = Path(__file__).resolve().parents[1]
        plan = build_training_plan(root, "raven")
        self.assertEqual(plan["agent"], "raven")
        self.assertIn("raven_train_ready.jsonl", plan["train_ready_path"])


if __name__ == "__main__":
    unittest.main()

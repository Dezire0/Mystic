from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mystic.raven_training import load_jsonl
from scripts.prepare_raven_training_data import main as prepare_main


class PrepareRavenTrainingDataTests(unittest.TestCase):
    def test_prepare_splits_valid_rows_into_chat_format(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "raven_lora.jsonl"
            train_out = root / "raven_train.jsonl"
            eval_out = root / "raven_eval.jsonl"

            rows = [
                {
                    "problem": "p1",
                    "proof_attempt": "proof1",
                    "output": json.dumps({"verdict": "INVALID", "first_fatal_error": "bad", "missing_assumptions": [], "invalid_steps": [], "valid_steps": [], "repair_possible": True, "confidence": 0.2, "final_status": "INVALID"}),
                    "metadata": {"sample_id": "s1"},
                },
                {
                    "problem": "p2",
                    "proof_attempt": "proof2",
                    "output": json.dumps({"verdict": "GAP", "first_fatal_error": "missing lemma", "missing_assumptions": ["lemma"], "invalid_steps": [], "valid_steps": [], "repair_possible": True, "confidence": 0.4, "final_status": "GAP"}),
                    "metadata": {"sample_id": "s2"},
                },
            ]
            input_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

            result = prepare_main(
                [
                    "--input",
                    str(input_path),
                    "--train-out",
                    str(train_out),
                    "--eval-out",
                    str(eval_out),
                    "--eval-ratio",
                    "0.5",
                ]
            )

            self.assertEqual(result, 0)
            train_rows = load_jsonl(train_out)
            eval_rows = load_jsonl(eval_out)
            self.assertEqual(len(train_rows), 1)
            self.assertEqual(len(eval_rows), 1)
            self.assertEqual(train_rows[0]["messages"][0]["role"], "system")
            self.assertIn("Critique the proof attempt. Output JSON only.", train_rows[0]["messages"][1]["content"])
            self.assertIn(train_rows[0]["target_verdict"], {"INVALID", "GAP"})


if __name__ == "__main__":
    unittest.main()

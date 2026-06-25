from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mystic.raven_dataset_builder import build_raven_lora_export


class RavenDatasetBuilderTests(unittest.TestCase):
    def test_build_raven_lora_export_scales_with_synthetic_rows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir) / "mystic_data"
            (base / "internal").mkdir(parents=True, exist_ok=True)
            (base / "exports").mkdir(parents=True, exist_ok=True)
            (base / "train_ready").mkdir(parents=True, exist_ok=True)
            (base / "raw").mkdir(parents=True, exist_ok=True)

            (base / "internal" / "raven_critiques.jsonl").write_text(
                json.dumps(
                    {
                        "sample_id": "internal-1",
                        "problem": "Prove 1+1=2.",
                        "proof_text": "By the Peano axioms, the statement holds.",
                        "run_id": "run-1",
                        "verdict": "VALID",
                        "first_fatal_error": "",
                        "missing_assumptions": [],
                        "invalid_steps": [],
                        "valid_steps": ["The statement is referenced correctly."],
                        "repair_possible": True,
                        "confidence": 0.5,
                        "final_status": "VALID",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (base / "raw" / "numina_math_cot_100.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps({"problem": "Prove n+n is even.", "reference_solution": "Let n+n=2n, so it is even."}),
                        json.dumps({"problem": "Show 2 divides 4.", "reference_solution": "Because 4=2*2."}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            rows, payload = build_raven_lora_export(base, target_rows=5)

            self.assertEqual(len(rows), 5)
            self.assertEqual(payload["internal_row_count"], 1)
            self.assertEqual(payload["synthetic_row_count"], 4)
            self.assertIn("synthetic_verdict_counts", payload)
            self.assertGreaterEqual(sum(payload["synthetic_verdict_counts"].values()), 4)


if __name__ == "__main__":
    unittest.main()

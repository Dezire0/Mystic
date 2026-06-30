from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mystic.raven_training import load_jsonl
from scripts.generate_raven_adversarial_seeds import generate_raven_adversarial_seeds


class GenerateRavenAdversarialSeedsTests(unittest.TestCase):
    def test_generator_creates_schema_valid_jsonl_and_manifest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "adversarial_seed_raven.jsonl"

            payload = generate_raven_adversarial_seeds(output_path=output)

            rows = load_jsonl(output)
            self.assertGreater(len(rows), 0)
            self.assertEqual(payload["rows_written"], len(rows))
            manifest_path = output.parent / "adversarial_seed_manifest.json"
            self.assertTrue(manifest_path.exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["target_agent"], "raven")
            for row in rows:
                self.assertEqual(row["agent"], "raven")
                self.assertIsInstance(row["input"], dict)
                self.assertIsInstance(row["output"], dict)
                self.assertEqual(row["source"]["source_type"], "adversarial_seed")

    def test_invalid_and_verifier_rows_have_required_evidence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "adversarial_seed_raven.jsonl"
            generate_raven_adversarial_seeds(output_path=output)

            rows = load_jsonl(output)
            invalid_rows = [row for row in rows if row["output"]["verdict"] == "INVALID"]
            self.assertGreaterEqual(len(invalid_rows), 5)
            self.assertTrue(all(str(row["output"]["first_fatal_error"]).strip() for row in invalid_rows))
            substitution_rows = [
                row
                for row in rows
                if row["source"]["case_type"]
                in {"wrong_candidate_tuple", "arithmetic_substitution_failure", "verifier_override"}
            ]
            self.assertTrue(substitution_rows)
            self.assertTrue(all(str(row["input"]["tool_evidence"]).strip() for row in substitution_rows))

    def test_same_seed_and_count_are_deterministic(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "first" / "adversarial_seed_raven.jsonl"
            second = root / "second" / "adversarial_seed_raven.jsonl"

            generate_raven_adversarial_seeds(output_path=first, count=7, seed=19)
            generate_raven_adversarial_seeds(output_path=second, count=7, seed=19)

            self.assertEqual(first.read_text(encoding="utf-8"), second.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

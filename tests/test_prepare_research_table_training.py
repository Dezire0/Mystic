from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mystic.raven_training import load_jsonl
from scripts.generate_raven_adversarial_seeds import generate_raven_adversarial_seeds
from scripts.prepare_research_table_training import main as prepare_main


class PrepareResearchTableTrainingTests(unittest.TestCase):
    def test_research_table_row_converts_to_raven_training_row(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "research_table_raven.jsonl"
            output_path = root / "training" / "raven" / "research_table_train.jsonl"
            input_path.write_text(json.dumps(self._sample_row()) + "\n", encoding="utf-8")

            result = prepare_main(["--input", str(input_path), "--output", str(output_path)])

            self.assertEqual(result, 0)
            rows = load_jsonl(output_path)
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["problem"], "Find all valid triples.")
            self.assertIn("Model output:", row["proof_attempt"])
            self.assertIn("Discovery or claim:", row["proof_attempt"])
            self.assertIn("Tool evidence:", row["proof_attempt"])
            self.assertEqual(row["target_verdict"], "INVALID")
            output_payload = json.loads(row["assistant_output"])
            self.assertEqual(output_payload["verdict"], "INVALID")
            self.assertEqual(output_payload["first_fatal_error"], "The candidate sums to 7/8, not 1.")
            source = row["metadata"]["research_table"]["source"]
            self.assertEqual(source["session_id"], "session-1")
            self.assertEqual(source["turn_id"], "turn-1")
            self.assertEqual(source["discovery_id"], "disc-1")
            self.assertEqual(source["label_id"], "")

    def test_manifest_is_created_with_verdict_distribution(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "research_table_raven.jsonl"
            output_path = root / "training" / "raven" / "research_table_train.jsonl"
            rows = [self._sample_row() for _ in range(2)]
            input_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

            result = prepare_main(["--input", str(input_path), "--output", str(output_path), "--max-rows", "1"])

            self.assertEqual(result, 0)
            manifest_path = output_path.parent / "manifest.json"
            self.assertTrue(manifest_path.exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["target_agent"], "raven")
            self.assertEqual(manifest["rows_total"], 2)
            self.assertEqual(manifest["rows_written"], 1)
            self.assertEqual(manifest["verdict_distribution"]["INVALID"], 1)

    def test_empty_dataset_is_rejected_without_allow_empty(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "research_table_raven.jsonl"
            output_path = root / "training" / "raven" / "research_table_train.jsonl"
            input_path.write_text("", encoding="utf-8")

            result = prepare_main(["--input", str(input_path), "--output", str(output_path)])

            self.assertEqual(result, 1)
            self.assertFalse(output_path.exists())

    def test_adversarial_seeds_are_combined_deduplicated_and_reported(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "research_table_raven.jsonl"
            adversarial_path = root / "adversarial_seed_raven.jsonl"
            output_path = root / "training" / "raven" / "research_table_train.jsonl"
            duplicate_rows = [self._sample_row(), self._sample_row()]
            input_path.write_text(
                "\n".join(json.dumps(row) for row in duplicate_rows) + "\n",
                encoding="utf-8",
            )
            generated = generate_raven_adversarial_seeds(output_path=adversarial_path)

            result = prepare_main(
                [
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--include-adversarial-seeds",
                    "--adversarial-path",
                    str(adversarial_path),
                ]
            )

            self.assertEqual(result, 0)
            manifest = json.loads((output_path.parent / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["research_table_rows"], 1)
            self.assertEqual(manifest["adversarial_seed_rows"], generated["rows_written"])
            self.assertEqual(manifest["combined_rows"], 1 + generated["rows_written"])
            self.assertEqual(manifest["duplicate_rows_removed"], 1)
            self.assertGreaterEqual(manifest["invalid_rows_count"], 5)
            self.assertFalse(any("Too few INVALID rows" in item for item in manifest["warnings"]))
            sources = {row["metadata"]["dataset_source"] for row in load_jsonl(output_path)}
            self.assertEqual(sources, {"research_table", "adversarial_seed"})

    def test_missing_requested_adversarial_file_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "research_table_raven.jsonl"
            output_path = root / "training.jsonl"
            input_path.write_text(json.dumps(self._sample_row()) + "\n", encoding="utf-8")

            result = prepare_main(
                [
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--include-adversarial-seeds",
                    "--adversarial-path",
                    str(root / "missing.jsonl"),
                ]
            )

            self.assertEqual(result, 1)
            self.assertFalse(output_path.exists())

    def _sample_row(self) -> dict[str, object]:
        return {
            "agent": "raven",
            "input": {
                "problem": "Find all valid triples.",
                "model_output": "Candidate answer (2, 4, 8).",
                "discovery_or_claim": "Candidate answer (2, 4, 8)",
                "tool_evidence": "(2, 4, 8) sums to 7/8, not 1.",
                "context": "Session context for the verifier.",
            },
            "output": {
                "verdict": "INVALID",
                "first_fatal_error": "The candidate sums to 7/8, not 1.",
                "critique": "Reject the candidate immediately.",
                "recommended_next_action": "check remaining bounded cases",
            },
            "source": {
                "session_id": "session-1",
                "turn_id": "turn-1",
                "discovery_id": "disc-1",
                "label_id": "",
            },
        }


if __name__ == "__main__":
    unittest.main()

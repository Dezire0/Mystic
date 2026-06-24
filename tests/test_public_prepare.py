from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mystic.training.public_prepare import prepare_public_train_ready_datasets


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(json.dumps(row, ensure_ascii=True) for row in rows)
    if payload:
        payload += "\n"
    path.write_text(payload, encoding="utf-8")


class PublicPrepareTests(unittest.TestCase):
    def test_prepare_public_train_ready_uses_real_raw_rows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir) / "mystic_data"
            write_jsonl(
                base / "raw" / "numina_math_cot_100.jsonl",
                [
                    {"problem": "Prove x=x.", "solution": "By reflexivity."},
                    {"problem": "Compute 2+2.", "solution": "4"},
                ],
            )
            write_jsonl(
                base / "raw" / "openthoughts" / "sample.jsonl",
                [
                    {
                        "conversations": [
                            {"from": "user", "value": "Write a simulator for a recurrence."},
                            {"from": "assistant", "value": "Use a loop and log each state."},
                        ]
                    }
                ],
            )

            payload = prepare_public_train_ready_datasets(base, max_rows_per_agent=2, overwrite=True)

            self.assertGreaterEqual(payload["added_counts"]["prime"], 1)
            self.assertGreaterEqual(payload["added_counts"]["simulator"], 1)
            prime_rows = [
                json.loads(line)
                for line in (base / "train_ready" / "prime_train_ready.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertTrue(all(row["metadata"]["source_type"] == "public_real" for row in prime_rows))

    def test_prepare_public_train_ready_preserves_non_bootstrap_existing_rows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir) / "mystic_data"
            existing_path = base / "train_ready" / "raven_train_ready.jsonl"
            write_jsonl(
                existing_path,
                [
                    {
                        "agent": "raven",
                        "instruction": "existing",
                        "input": "existing input",
                        "output": "existing output",
                        "metadata": {"bootstrap": False},
                    }
                ],
            )
            write_jsonl(
                base / "raw" / "numina_math_cot_100.jsonl",
                [{"problem": "Show 1=1.", "solution": "Identity."}],
            )

            payload = prepare_public_train_ready_datasets(base, max_rows_per_agent=3, overwrite=True)

            self.assertEqual(payload["preserved_counts"]["raven"], 1)
            contents = existing_path.read_text(encoding="utf-8")
            self.assertIn("existing input", contents)


if __name__ == "__main__":
    unittest.main()

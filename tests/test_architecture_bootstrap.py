from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mystic.training.architecture_bootstrap import bootstrap_architecture_train_ready


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(json.dumps(row, ensure_ascii=True) for row in rows)
    if payload:
        payload += "\n"
    path.write_text(payload, encoding="utf-8")


class ArchitectureBootstrapTests(unittest.TestCase):
    def test_bootstrap_writes_missing_architecture_train_ready_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir) / "mystic_data"
            raw_dir = base / "raw"
            write_jsonl(
                raw_dir / "numina_math_cot_100.jsonl",
                [
                    {"problem": "Prove 1+1=2.", "solution": "By Peano arithmetic."},
                    {"problem": "Compute 2+2.", "solution": "4"},
                    {"problem": "Show x=x.", "solution": "Reflexivity."},
                ],
            )

            payload = bootstrap_architecture_train_ready(base, rows_per_agent=2)

            self.assertGreaterEqual(payload["seed_example_count"], 2)
            algebra_path = base / "train_ready" / "algebra_train_ready.jsonl"
            simulator_path = base / "train_ready" / "simulator_train_ready.jsonl"
            self.assertTrue(algebra_path.exists())
            self.assertTrue(simulator_path.exists())
            algebra_rows = [
                json.loads(line)
                for line in algebra_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(algebra_rows), 2)
            self.assertTrue(all(row["metadata"]["bootstrap"] for row in algebra_rows))
            self.assertIn("algebra", payload["written"])

    def test_bootstrap_keeps_existing_rows_without_force(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir) / "mystic_data"
            raw_dir = base / "raw"
            write_jsonl(
                raw_dir / "numina_math_cot_100.jsonl",
                [{"problem": "Example", "solution": "Example solution"}],
            )
            existing = base / "train_ready" / "logic_train_ready.jsonl"
            write_jsonl(
                existing,
                [
                    {
                        "instruction": "keep",
                        "input": "existing",
                        "output": "row",
                        "metadata": {"bootstrap": False},
                    }
                ],
            )

            payload = bootstrap_architecture_train_ready(base, rows_per_agent=1)

            self.assertIn("logic", payload["skipped"])
            content = existing.read_text(encoding="utf-8")
            self.assertIn("\"existing\"", content)


if __name__ == "__main__":
    unittest.main()

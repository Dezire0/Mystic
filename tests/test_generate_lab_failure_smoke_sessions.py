from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mystic.raven_training import load_jsonl
from scripts.generate_lab_failure_smoke_sessions import generate_lab_failure_smoke_sessions, main as smoke_main


class GenerateLabFailureSmokeSessionsTests(unittest.TestCase):
    def test_script_creates_lab_sessions_with_expected_artifacts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            summary = generate_lab_failure_smoke_sessions(root_path=root, count=3, run_id="smoke")

            self.assertEqual(summary["sessions_created"], 3)
            for session_id in summary["session_ids"]:
                session_dir = root / "mystic_data" / "lab_sessions" / session_id
                self.assertTrue((session_dir / "session.json").exists())
                self.assertTrue((session_dir / "turns.json").exists())
                self.assertTrue((session_dir / "claims.json").exists())
                self.assertTrue((session_dir / "experiments.json").exists())
                self.assertTrue((session_dir / "failures.json").exists())
                self.assertTrue((session_dir / "memory_edges.json").exists())
                self.assertTrue((session_dir / "notebook.md").exists())
                self.assertTrue((session_dir / "report.md").exists())

    def test_failures_are_reusable_and_valid(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            summary = generate_lab_failure_smoke_sessions(root_path=root, count=4, run_id="smoke")

            self.assertEqual(summary["reusable_failures"], 4)
            for session_id in summary["session_ids"]:
                failure_path = root / "mystic_data" / "lab_sessions" / session_id / "failures.json"
                failures = json.loads(failure_path.read_text(encoding="utf-8"))
                self.assertTrue(failures)
                for failure in failures:
                    self.assertTrue(failure["reusable_as_training_data"])
                    self.assertTrue(failure["first_fatal_error"])
                    self.assertIn(
                        failure["failure_type"],
                        {
                            "arithmetic",
                            "missing_case",
                            "insufficient_detail",
                            "logic_gap",
                        },
                    )

    def test_verify_export_produces_raven_compatible_rows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            summary = generate_lab_failure_smoke_sessions(
                root_path=root,
                count=4,
                run_id="smoke",
                verify_export=True,
            )

            export_path = root / "mystic_data" / "datasets" / "lab" / "raven_lab_failures.jsonl"
            rows = load_jsonl(export_path)
            self.assertGreater(len(rows), 0)
            self.assertGreaterEqual(summary["export_verification"]["rows_written"], summary["expected_export_rows"])
            self.assertTrue(any(row["output"]["verdict"] == "INVALID" for row in rows))
            self.assertTrue(all(row["source"]["source_type"] == "lab_failure" for row in rows))

    def test_summary_contains_expected_counts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            result = smoke_main(
                [
                    "--root-path",
                    str(root),
                    "--count",
                    "4",
                    "--run-id",
                    "smoke",
                    "--verify-export",
                ]
            )

            self.assertEqual(result, 0)
            summary_path = root / "mystic_data" / "e2e" / "lab_failure_smoke" / "summary.json"
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary["sessions_created"], 4)
            self.assertEqual(summary["failures_created"], 4)
            self.assertEqual(summary["expected_export_rows"], 4)


if __name__ == "__main__":
    unittest.main()

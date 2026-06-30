from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.check_raven_training_readiness import check_raven_training_readiness


class CheckRavenTrainingReadinessTests(unittest.TestCase):
    def test_missing_dataset_reports_not_ready(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            report = check_raven_training_readiness(root)

            self.assertFalse(report["ready"])
            self.assertFalse(report["dataset_exists"])
            self.assertTrue(report["errors"])
            self.assertTrue((root / "mystic_data" / "training" / "raven" / "readiness_report.json").exists())

    def test_valid_prepared_dataset_reports_ready(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_source_dataset(root)
            self._write_prepared_rows(
                root,
                [
                    self._prepared_row("row-invalid", "INVALID", "fatal issue", "evidence", True),
                    self._prepared_row("row-valid", "VALID", "", "", False),
                    self._prepared_row("row-gap", "NEEDS_MORE_DETAIL", "", "", False),
                    self._prepared_row("row-invalid-2", "INVALID", "fatal two", "evidence two", True),
                    self._prepared_row("row-invalid-3", "INVALID", "fatal three", "evidence three", True),
                    self._prepared_row("row-invalid-4", "INVALID", "fatal four", "evidence four", True),
                    self._prepared_row("row-invalid-5", "INVALID", "fatal five", "evidence five", True),
                ],
            )

            report = check_raven_training_readiness(root)

            self.assertTrue(report["ready"])
            self.assertEqual(report["invalid_rows_count"], 5)
            self.assertEqual(report["needs_more_detail_rows_count"], 1)
            self.assertEqual(report["valid_rows_count"], 1)
            self.assertTrue(report["kaggle_package"]["contains_train_file"])
            self.assertTrue(report["kaggle_package"]["contains_eval_file"])
            self.assertFalse(report["errors"])

    def test_low_invalid_count_creates_warning(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_source_dataset(root)
            self._write_prepared_rows(
                root,
                [
                    self._prepared_row("row-invalid", "INVALID", "fatal issue", "evidence", True),
                    self._prepared_row("row-valid", "VALID", "", "", False),
                ],
            )

            report = check_raven_training_readiness(root)

            self.assertTrue(report["ready"])
            self.assertTrue(any("Too few INVALID rows" in warning for warning in report["warnings"]))

    def test_missing_first_fatal_error_creates_warning(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_source_dataset(root)
            self._write_prepared_rows(
                root,
                [
                    self._prepared_row("row-invalid", "INVALID", "", "evidence", True),
                    self._prepared_row("row-invalid-2", "INVALID", "fatal two", "evidence two", True),
                    self._prepared_row("row-invalid-3", "INVALID", "fatal three", "evidence three", True),
                    self._prepared_row("row-invalid-4", "INVALID", "fatal four", "evidence four", True),
                    self._prepared_row("row-invalid-5", "INVALID", "fatal five", "evidence five", True),
                ],
            )

            report = check_raven_training_readiness(root)

            self.assertTrue(report["ready"])
            self.assertTrue(any("Missing first_fatal_error" in warning for warning in report["warnings"]))

    def _write_source_dataset(self, root: Path) -> None:
        dataset_path = root / "mystic_data" / "datasets" / "raven" / "research_table_raven.jsonl"
        dataset_path.parent.mkdir(parents=True, exist_ok=True)
        dataset_path.write_text(
            json.dumps(
                {
                    "agent": "raven",
                    "input": {"problem": "p", "model_output": "m", "discovery_or_claim": "d", "tool_evidence": "e", "context": "c"},
                    "output": {"verdict": "INVALID", "first_fatal_error": "bad", "critique": "x", "recommended_next_action": "y"},
                    "source": {"session_id": "s", "turn_id": "t", "discovery_id": "d", "label_id": ""},
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def _write_prepared_rows(self, root: Path, rows: list[dict[str, object]]) -> None:
        prepared_path = root / "mystic_data" / "training" / "raven" / "research_table_train.jsonl"
        manifest_path = prepared_path.parent / "manifest.json"
        prepared_path.parent.mkdir(parents=True, exist_ok=True)
        prepared_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
        manifest_path.write_text(
            json.dumps(
                {
                    "target_agent": "raven",
                    "input_path": str(root / "mystic_data" / "datasets" / "raven" / "research_table_raven.jsonl"),
                    "output_path": str(prepared_path),
                    "rows_total": len(rows),
                    "rows_written": len(rows),
                    "verdict_distribution": {},
                    "source_counts": {},
                    "created_at": "2026-06-30T00:00:00+00:00",
                    "warnings": [],
                }
            ),
            encoding="utf-8",
        )

    def _prepared_row(
        self,
        sample_id: str,
        verdict: str,
        first_fatal_error: str,
        tool_evidence: str,
        verifier_derived: bool,
    ) -> dict[str, object]:
        return {
            "sample_id": sample_id,
            "problem": "Find all triples.",
            "proof_attempt": "Candidate and evidence.",
            "messages": [
                {"role": "system", "content": "s"},
                {"role": "user", "content": "u"},
                {"role": "assistant", "content": "{}"},
            ],
            "assistant_output": json.dumps(
                {
                    "verdict": verdict,
                    "first_fatal_error": first_fatal_error,
                }
            ),
            "target_verdict": verdict,
            "metadata": {
                "research_table": {
                    "first_fatal_error": first_fatal_error,
                    "tool_evidence": tool_evidence,
                    "verifier_derived": verifier_derived,
                    "source": {"session_id": "session-1", "turn_id": sample_id, "discovery_id": sample_id, "label_id": ""},
                }
            },
        }


if __name__ == "__main__":
    unittest.main()

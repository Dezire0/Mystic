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
            self._write_lab_failure_dataset(root)
            self._write_prepared_rows(
                root,
                [
                    self._prepared_row("row-invalid", "INVALID", "fatal issue", "evidence", True),
                    self._prepared_row("row-valid", "VALID", "", "", False),
                ],
                lab_failure_rows=1,
            )

            report = check_raven_training_readiness(root)

            self.assertTrue(report["ready"])
            self.assertTrue(any("Too few INVALID rows" in warning for warning in report["warnings"]))
            self.assertTrue(any("--include-adversarial-seeds" in item for item in report["recommendations"]))

    def test_included_adversarial_seeds_improve_invalid_quality(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_source_dataset(root)
            adversarial_path = root / "mystic_data" / "datasets" / "raven" / "adversarial_seed_raven.jsonl"
            adversarial_path.write_text(
                "\n".join(json.dumps({"seed": index}) for index in range(5)) + "\n",
                encoding="utf-8",
            )
            adversarial_manifest = adversarial_path.parent / "adversarial_seed_manifest.json"
            adversarial_manifest.write_text(json.dumps({"rows_written": 5}), encoding="utf-8")
            self._write_prepared_rows(
                root,
                [
                    self._prepared_row(
                        f"seed-{index}",
                        "INVALID",
                        f"fatal {index}",
                        f"evidence {index}",
                        True,
                        dataset_source="adversarial_seed",
                    )
                    for index in range(5)
                ]
                + [self._prepared_row("rt-valid", "VALID", "", "", False)],
                adversarial_seed_rows=5,
            )

            report = check_raven_training_readiness(root)

            self.assertTrue(report["ready"])
            self.assertEqual(report["adversarial_seed_status"]["status"], "included")
            self.assertTrue(report["invalid_row_quality"]["sufficient"])
            self.assertFalse(any("--include-adversarial-seeds" in item for item in report["warnings"]))

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

    def test_readiness_reports_lab_failure_dataset_stats(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_source_dataset(root)
            self._write_lab_failure_dataset(root)
            self._write_prepared_rows(
                root,
                [
                    self._prepared_row("row-invalid", "INVALID", "fatal issue", "evidence", True),
                    self._prepared_row(
                        "lab-failure-1",
                        "INVALID",
                        "fatal issue",
                        "tool evidence",
                        False,
                        dataset_source="lab_failure",
                        claim_id="claim-1",
                        failure_id="failure-1",
                    ),
                ],
                lab_failure_rows=1,
            )

            report = check_raven_training_readiness(root)

            self.assertEqual(report["lab_failure_status"]["status"], "included")
            self.assertEqual(report["lab_failure_status"]["available_rows"], 1)
            self.assertEqual(report["lab_failure_status"]["included_rows"], 1)
            self.assertEqual(report["prepared_dataset"]["dataset_source_counts"]["lab_failure"], 1)

    def test_require_lab_failures_fails_clearly_when_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_source_dataset(root)
            self._write_prepared_rows(
                root,
                [
                    self._prepared_row("row-invalid", "INVALID", "fatal issue", "evidence", True),
                ],
            )

            report = check_raven_training_readiness(root, require_lab_failures=True)

            self.assertFalse(report["ready"])
            self.assertTrue(any("Lab failure dataset is missing" in item for item in report["errors"]))
            self.assertTrue(any("export_lab_failure_datasets.py" in item for item in report["recommendations"]))

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

    def _write_prepared_rows(
        self,
        root: Path,
        rows: list[dict[str, object]],
        *,
        adversarial_seed_rows: int = 0,
        lab_failure_rows: int = 0,
    ) -> None:
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
                    "research_table_rows": len(rows) - adversarial_seed_rows - lab_failure_rows,
                    "adversarial_seed_rows": adversarial_seed_rows,
                    "lab_failure_rows": lab_failure_rows,
                    "combined_rows": len(rows),
                    "verdict_distribution": {},
                    "source_counts": {},
                    "created_at": "2026-06-30T00:00:00+00:00",
                    "warnings": [],
                }
            ),
            encoding="utf-8",
        )

    def _write_lab_failure_dataset(self, root: Path) -> None:
        dataset_path = root / "mystic_data" / "datasets" / "lab" / "raven_lab_failures.jsonl"
        summary_path = root / "mystic_data" / "datasets" / "lab" / "raven_lab_failures_summary.json"
        dataset_path.parent.mkdir(parents=True, exist_ok=True)
        dataset_path.write_text(
            json.dumps(
                {
                    "agent": "raven",
                    "input": {"problem": "p", "model_output": "m", "discovery_or_claim": "d", "tool_evidence": "e", "context": "c"},
                    "output": {"verdict": "INVALID", "first_fatal_error": "bad", "critique": "x", "recommended_next_action": "y"},
                    "source": {
                        "source_type": "lab_failure",
                        "session_id": "lab-session-1",
                        "claim_id": "claim-1",
                        "failure_id": "failure-1",
                        "source_turn_id": "turn-1",
                        "turn_id": "turn-1",
                        "failure_type": "arithmetic",
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        summary_path.write_text(
            json.dumps(
                {
                    "rows_written": 1,
                    "failure_type_distribution": {"arithmetic": 1},
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
        dataset_source: str = "research_table",
        claim_id: str = "",
        failure_id: str = "",
    ) -> dict[str, object]:
        source = {"session_id": "session-1", "turn_id": sample_id, "discovery_id": sample_id, "label_id": ""}
        metadata_block = {
            "first_fatal_error": first_fatal_error,
            "tool_evidence": tool_evidence,
            "verifier_derived": verifier_derived,
            "source": source,
        }
        if dataset_source == "lab_failure":
            source = {
                "source_type": "lab_failure",
                "session_id": "lab-session-1",
                "turn_id": sample_id,
                "claim_id": claim_id,
                "failure_id": failure_id,
                "source_turn_id": sample_id,
            }
            metadata_block["source"] = source
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
                "dataset_source": dataset_source,
                "target_agent": "raven",
                ("lab_failure" if dataset_source == "lab_failure" else "research_table"): metadata_block,
            },
        }


if __name__ == "__main__":
    unittest.main()

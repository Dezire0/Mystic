from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mystic.lab.session import Claim, Experiment, Failure, LabSession, LabSessionBundle, LabTurn
from mystic.lab.storage import LabStorage
from mystic.lab.training_export import export_lab_failures_for_raven, map_lab_failure_to_raven_verdict
from mystic.raven_training import load_jsonl
from scripts.export_lab_failure_datasets import main as export_main


class ExportLabFailureDatasetsTests(unittest.TestCase):
    def test_export_lab_failure_rows_and_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_lab_bundle(root)
            output_path = root / "mystic_data" / "datasets" / "lab" / "raven_lab_failures.jsonl"

            summary = export_lab_failures_for_raven(root, output_path)

            rows = load_jsonl(output_path)
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["agent"], "raven")
            self.assertEqual(row["output"]["verdict"], "INVALID")
            self.assertEqual(row["source"]["source_type"], "lab_failure")
            self.assertEqual(row["source"]["claim_id"], "claim-1")
            self.assertIn("bounded brute force refutes the claim", row["input"]["tool_evidence"])
            self.assertEqual(summary["rows_written"], 1)
            self.assertEqual(summary["reusable_failures"], 1)
            self.assertEqual(summary["failure_type_distribution"]["arithmetic"], 1)

    def test_verdict_mapping_matches_failure_type_rules(self):
        self.assertEqual(map_lab_failure_to_raven_verdict("arithmetic"), "INVALID")
        self.assertEqual(map_lab_failure_to_raven_verdict("insufficient_detail"), "NEEDS_MORE_DETAIL")
        self.assertEqual(map_lab_failure_to_raven_verdict("tool_error"), "UNCLEAR")

    def test_cli_respects_allow_empty(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result = export_main(
                [
                    "--root-path",
                    str(root),
                    "--target",
                    "raven",
                    "--allow-empty",
                ]
            )

            self.assertEqual(result, 0)
            summary_path = root / "mystic_data" / "datasets" / "lab" / "raven_lab_failures_summary.json"
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary["rows_written"], 0)

    def _write_lab_bundle(self, root: Path) -> None:
        storage = LabStorage(root)
        session = LabSession(
            session_id="lab-session-1",
            problem="Find all positive integer triples x <= y <= z such that 1/x + 1/y + 1/z = 1.",
            domain="math",
            goal="Reject false candidate triples and keep only correct ones.",
            mode="proof_critical",
        )
        turn = LabTurn(
            session_id=session.session_id,
            phase="referee_review",
            room="Referee Court",
            agent_role="Referee",
            provider="local",
            model_name="local_prime",
            input_summary="Review candidate (2, 4, 8).",
            output="Candidate (2, 4, 8) works because the reciprocals sum to 1.",
            turn_id="turn-1",
        )
        claim = Claim(
            session_id=session.session_id,
            text="Candidate triple (2, 4, 8) satisfies the equation.",
            claim_type="result",
            status="REFUTED",
            confidence="high",
            source_turn_id=turn.turn_id,
            refuting_evidence=["bounded brute force refutes the claim"],
            claim_id="claim-1",
        )
        experiment = Experiment(
            session_id=session.session_id,
            claim_id=claim.claim_id,
            question="Does (2, 4, 8) sum to 1?",
            method="python_bruteforce",
            inputs={"candidate": [2, 4, 8]},
            outputs={"sum": "7/8"},
            verdict="refutes",
            evidence_summary="bounded brute force refutes the claim: 1/2 + 1/4 + 1/8 = 7/8",
        )
        failure = Failure(
            session_id=session.session_id,
            claim_id=claim.claim_id,
            source_turn_id=turn.turn_id,
            first_fatal_error="The claimed triple sums to 7/8, not 1.",
            failure_type="arithmetic",
            lesson="Check the exact reciprocal sum before accepting a candidate.",
            reusable_as_training_data=True,
            failure_id="failure-1",
        )
        bundle = LabSessionBundle(
            session=session,
            turns=[turn],
            claims=[claim],
            experiments=[experiment],
            failures=[failure],
            memory_edges=[],
        )
        storage.save_bundle(bundle)


if __name__ == "__main__":
    unittest.main()

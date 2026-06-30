from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from mystic.raven_training import load_jsonl
from mystic.research_table.dataset_export import export_research_table_datasets


class ResearchTableDatasetExportTests(unittest.TestCase):
    def test_dataset_export_creates_raven_prime_and_forge_rows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_session_fixture(root)
            self._write_teacher_labels(root)
            self._write_training_items(root)
            self._write_malformed_inputs(root)

            summary = export_research_table_datasets(root)

            raven_rows = load_jsonl(root / "mystic_data" / "datasets" / "raven" / "research_table_raven.jsonl")
            prime_rows = load_jsonl(root / "mystic_data" / "datasets" / "prime" / "research_table_prime.jsonl")
            forge_rows = load_jsonl(root / "mystic_data" / "datasets" / "forge" / "research_table_forge.jsonl")

            self.assertTrue(any(row["source"]["discovery_id"] == "disc-bad" and row["agent"] == "raven" for row in raven_rows))
            self.assertTrue(any(row["source"]["discovery_id"] == "disc-good" and row["agent"] == "prime" for row in prime_rows))
            self.assertTrue(any(row["source"]["discovery_id"] == "disc-bad" and row["agent"] == "forge" for row in forge_rows))

            self.assertTrue(any(row["source"]["label_id"] == "label-raven" for row in raven_rows))
            self.assertTrue(any(row["source"]["label_id"] == "label-prime" for row in prime_rows))

            raven_bad = next(row for row in raven_rows if row["source"]["discovery_id"] == "disc-bad")
            self.assertEqual(raven_bad["output"]["verdict"], "INVALID")

            prime_good = next(row for row in prime_rows if row["source"]["discovery_id"] == "disc-good")
            self.assertIn("Lemma", prime_good["output"]["discovery"])

            forge_req = next(row for row in forge_rows if row["source"]["discovery_id"] == "disc-bad")
            self.assertIn(forge_req["output"]["tool"], {"python", "sympy", "z3", "brute_force"})

            self.assertEqual(summary["datasets"]["raven"]["rows"], len(raven_rows))
            self.assertEqual(summary["datasets"]["prime"]["rows"], len(prime_rows))
            self.assertEqual(summary["datasets"]["forge"]["rows"], len(forge_rows))
            self.assertTrue(summary["warnings"])
            self.assertTrue((root / "mystic_data" / "datasets" / "research_table_summary.json").exists())

    def _write_session_fixture(self, root: Path) -> None:
        session_dir = root / "mystic_data" / "research_table_sessions" / "session-train"
        session_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "session_id": "session-train",
            "problem": "Find all positive integer triples x <= y <= z such that 1/x + 1/y + 1/z = 1.",
            "created_at": "2026-06-30T10:00:00+00:00",
            "participants": ["alpha", "beta"],
            "participant_models": [
                {"model_id": "alpha", "provider": "mock", "model_name": "Alpha"},
                {"model_id": "beta", "provider": "mock", "model_name": "Beta"},
            ],
            "accepted_discoveries": [
                {
                    "discovery_id": "disc-good",
                    "claim": "Lemma: x <= 3",
                    "rationale": "Bounding x narrows the search immediately.",
                    "status": "accepted",
                }
            ],
            "rejected_discoveries": [
                {
                    "discovery_id": "disc-bad",
                    "claim": "Candidate answer (2, 4, 8)",
                    "rationale": "Fails the equation.",
                    "status": "rejected",
                }
            ],
            "verification_requests": [
                {
                    "request_id": "req-bad",
                    "target_discovery_id": "disc-bad",
                    "target_turn_id": "turn-bad",
                    "target_candidate_answer": "Candidate answer (2, 4, 8)",
                    "tool": "brute_force",
                    "question": "Check whether (2, 4, 8) satisfies the equation.",
                    "result_verdict": "INVALID",
                    "result_reasoning": "(2, 4, 8) sums to 7/8, not 1.",
                }
            ],
            "discoveries": [
                {
                    "discovery_id": "disc-bad",
                    "source_turn_id": "turn-bad",
                    "claim": "Candidate answer (2, 4, 8)",
                    "rationale": "It looks close to a valid Egyptian-fraction decomposition.",
                    "confidence": "low",
                    "needs_verification": False,
                    "type": "candidate_answer",
                    "status": "refuted",
                },
                {
                    "discovery_id": "disc-good",
                    "source_turn_id": "turn-good",
                    "claim": "Lemma: x <= 3",
                    "rationale": "If x >= 4 then the sum is at most 3/4.",
                    "confidence": "medium",
                    "needs_verification": False,
                    "type": "lemma",
                    "status": "verified",
                },
            ],
            "turns": [
                {
                    "turn_id": "turn-bad",
                    "phase": "independent_discovery",
                    "speaker_type": "model",
                    "speaker_id": "alpha",
                    "provider": "mock",
                    "model_name": "Alpha",
                    "role": "solver",
                    "status": "ERROR",
                    "content": "Candidate answer (2, 4, 8) should work.",
                    "summary": "bad candidate",
                    "latency_sec": 1.0,
                },
                {
                    "turn_id": "turn-good",
                    "phase": "revision_after_evidence",
                    "speaker_type": "model",
                    "speaker_id": "beta",
                    "provider": "mock",
                    "model_name": "Beta",
                    "role": "reviser",
                    "status": "REVISION",
                    "content": "Lemma: x <= 3, so we only need to check x = 2 or x = 3.",
                    "summary": "useful lemma",
                    "latency_sec": 2.0,
                },
                {
                    "turn_id": "tool-bad",
                    "phase": "tool_verification",
                    "speaker_type": "tool",
                    "speaker_id": "mystic_verify_answer",
                    "provider": "tool",
                    "model_name": "deterministic_verifier",
                    "role": "verifier",
                    "status": "VERIFICATION_RESULT",
                    "content": "(2, 4, 8) sums to 7/8, not 1.",
                    "summary": "INVALID",
                    "target_discovery_id": "disc-bad",
                },
                {
                    "turn_id": "tool-good",
                    "phase": "tool_verification",
                    "speaker_type": "tool",
                    "speaker_id": "mystic_verify_answer",
                    "provider": "tool",
                    "model_name": "deterministic_verifier",
                    "role": "verifier",
                    "status": "VERIFICATION_RESULT",
                    "content": "The bound x <= 3 is valid.",
                    "summary": "VALID",
                    "target_discovery_id": "disc-good",
                },
                {
                    "turn_id": "final-turn",
                    "phase": "final_synthesis",
                    "speaker_type": "controller",
                    "speaker_id": "gpt_controller",
                    "provider": "controller",
                    "model_name": "GPT Controller",
                    "role": "judge",
                    "status": "INVALID",
                    "content": "{}",
                },
            ],
            "final_status": "INVALID",
            "final_decision_source": "deterministic_verifier",
        }
        (session_dir / "session.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        (session_dir / "turns.json").write_text(json.dumps(payload["turns"], indent=2), encoding="utf-8")
        (session_dir / "discoveries.json").write_text(json.dumps(payload["discoveries"], indent=2), encoding="utf-8")
        (session_dir / "verification_requests.json").write_text(json.dumps(payload["verification_requests"], indent=2), encoding="utf-8")
        (session_dir / "final_synthesis.json").write_text(json.dumps({}, indent=2), encoding="utf-8")

    def _write_teacher_labels(self, root: Path) -> None:
        teacher_dir = root / "mystic_data" / "teacher_labels"
        teacher_dir.mkdir(parents=True, exist_ok=True)
        (teacher_dir / "label-raven.json").write_text(
            json.dumps(
                {
                    "label_id": "label-raven",
                    "packet_id": "session-train",
                    "source_model": "alpha",
                    "target_agent": "raven",
                    "label": {
                        "verdict": "INVALID",
                        "first_fatal_error": "The candidate is numerically false.",
                        "critique": "Reject the candidate.",
                        "corrected_reasoning": "Run the deterministic verifier first.",
                    },
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        (teacher_dir / "label-prime.json").write_text(
            json.dumps(
                {
                    "label_id": "label-prime",
                    "packet_id": "session-train",
                    "source_model": "beta",
                    "target_agent": "prime",
                    "label": {
                        "verdict": "VALID_COMPLETE_PROOF",
                        "first_fatal_error": "",
                        "critique": "This was a useful steering lemma.",
                        "corrected_reasoning": "Start with x <= 3 and split cases.",
                    },
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def _write_training_items(self, root: Path) -> None:
        items_dir = root / "mystic_data" / "training_items"
        items_dir.mkdir(parents=True, exist_ok=True)
        (items_dir / "forge-item.json").write_text(
            json.dumps(
                {
                    "item_id": "forge-item",
                    "session_id": "session-train",
                    "discovery_id": "disc-bad",
                    "target_agent": "forge",
                    "claim": "Candidate answer (2, 4, 8)",
                    "rationale": "Use brute force or direct substitution to refute it.",
                    "type": "candidate_answer",
                    "status": "refuted",
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def _write_malformed_inputs(self, root: Path) -> None:
        broken_session_dir = root / "mystic_data" / "research_table_sessions" / "broken-session"
        broken_session_dir.mkdir(parents=True, exist_ok=True)
        (broken_session_dir / "session.json").write_text("{broken", encoding="utf-8")

        teacher_dir = root / "mystic_data" / "teacher_labels"
        teacher_dir.mkdir(parents=True, exist_ok=True)
        (teacher_dir / "broken.json").write_text("{broken", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()

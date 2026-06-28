from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from mystic.research_table.runner import ResearchTableRunner


class _StubRouter:
    def call_model(
        self,
        *,
        model_id: str,
        role: str,
        task: str,
        problem: str,
        context: str = "",
        session_id: str | None = None,
    ) -> dict[str, object]:
        content_map = {
            ("alpha", "draft"): "Discovery: Candidate answer (2, 3) satisfies x + y = 5.",
            ("beta", "draft"): "Discovery: Candidate answer (9, 9) satisfies x + y = 5.",
            ("alpha", "critique"): "Critique: (9, 9) does not satisfy the equation.",
            ("beta", "critique"): "Critique: (2, 3) looks plausible, but verify it.",
            ("alpha", "revise"): "Revision: Keep only candidate answer (2, 3).",
            ("beta", "revise"): "Revision: Withdraw candidate answer (9, 9).",
        }
        content = content_map.get((model_id, role), f"{model_id} {role} fallback")
        return {
            "output_id": f"{model_id}-{role}",
            "model_id": model_id,
            "provider": "mock",
            "model_name": f"mock-{model_id}",
            "role": role,
            "content": content,
            "status": {
                "draft": "DRAFT_ONLY",
                "critique": "CRITIQUE_ONLY",
                "revise": "REVISION",
            }.get(role, "DRAFT_ONLY"),
            "latency_sec": 0.01,
            "artifact_path": str(Path("/tmp") / f"{model_id}-{role}.json"),
        }


def _stub_verify_answer(*, problem: str, candidate_answer: str, **_: object) -> dict[str, object]:
    if "(9, 9)" in candidate_answer:
        return {
            "valid": False,
            "verdict": "INVALID",
            "reasoning": "Candidate answer (9, 9) does not satisfy x + y = 5.",
            "saved_artifact_path": "/tmp/verify-invalid.json",
        }
    if "(2, 3)" in candidate_answer:
        return {
            "valid": True,
            "verdict": "VALID",
            "reasoning": "Candidate answer (2, 3) satisfies x + y = 5.",
            "saved_artifact_path": "/tmp/verify-valid.json",
        }
    return {
        "valid": False,
        "verdict": "UNKNOWN",
        "reasoning": "No deterministic check applied.",
        "saved_artifact_path": "/tmp/verify-unknown.json",
    }


class ResearchTableRunnerTests(unittest.TestCase):
    def test_threaded_session_runs_all_round_phases_and_reply_links(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = ResearchTableRunner(root_path=temp_dir, router=_StubRouter(), verify_answer=_stub_verify_answer)
            result = runner.run(
                problem="positive integers x, y satisfy x + y = 5",
                participants=["alpha", "beta"],
                mode="discovery_debate",
                max_rounds=3,
                enable_tools=True,
                tools=["mystic_verify_answer"],
                controller="gpt_controller",
            )

            phases = [turn["phase"] for turn in result["turns"]]
            self.assertIn("independent_discovery", phases)
            self.assertIn("discovery_sharing", phases)
            self.assertIn("cross_critique", phases)
            self.assertIn("tool_verification", phases)
            self.assertIn("revision_after_evidence", phases)
            self.assertIn("final_synthesis", phases)

            model_turns = [turn for turn in result["turns"] if turn["speaker_type"] == "model"]
            self.assertEqual(len(model_turns), 8)
            self.assertTrue(all("speaker_id" in turn for turn in model_turns))
            self.assertTrue(any(turn["reply_to"] for turn in result["turns"] if turn["phase"] == "cross_critique"))

    def test_discoveries_and_verifier_override_mark_verified_and_refuted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = ResearchTableRunner(root_path=temp_dir, router=_StubRouter(), verify_answer=_stub_verify_answer)
            result = runner.run(
                problem="positive integers x, y satisfy x + y = 5",
                participants=["alpha", "beta"],
                mode="discovery_debate",
                max_rounds=2,
                enable_tools=True,
                tools=["mystic_verify_answer"],
                controller="gpt_controller",
            )

            statuses = {item["claim"]: item["status"] for item in result["discoveries"]}
            self.assertEqual(statuses["Candidate answer (2, 3)"], "verified")
            self.assertEqual(statuses["Candidate answer (9, 9)"], "refuted")
            self.assertEqual(result["final_decision_source"], "deterministic_verifier")
            self.assertEqual(result["final_status"], "INVALID")
            self.assertTrue(result["accepted_discoveries"])
            self.assertTrue(result["rejected_discoveries"])

            tool_turns = [turn for turn in result["turns"] if turn["phase"] == "tool_verification"]
            self.assertTrue(tool_turns)
            self.assertTrue(all(turn["target_discovery_id"] for turn in tool_turns))
            self.assertTrue(all(turn["verification_request_id"] for turn in tool_turns))

    def test_saved_session_files_are_written_under_session_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runner = ResearchTableRunner(root_path=root, router=_StubRouter(), verify_answer=_stub_verify_answer)
            result = runner.run(
                problem="positive integers x, y satisfy x + y = 5",
                participants=["alpha", "beta"],
                mode="discovery_debate",
                max_rounds=2,
                enable_tools=True,
                tools=["mystic_verify_answer"],
                controller="gpt_controller",
            )

            saved = result["saved_artifacts"]
            session_dir = root / "mystic_data" / "research_table_sessions" / result["session_id"]
            self.assertTrue(session_dir.exists())
            self.assertTrue((session_dir / "session.json").exists())
            self.assertTrue((session_dir / "turns.json").exists())
            self.assertTrue((session_dir / "discoveries.json").exists())
            self.assertTrue((session_dir / "verification_requests.json").exists())
            self.assertTrue((session_dir / "final_synthesis.json").exists())
            self.assertEqual(saved["session"], str(session_dir / "session.json"))

            payload = json.loads((session_dir / "session.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["session_id"], result["session_id"])
            self.assertTrue(payload["accepted_discoveries"])
            self.assertTrue(payload["rejected_discoveries"])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from mystic.research_table.metrics import (
    render_research_table_metrics_markdown,
    summarize_research_table_metrics,
    write_research_table_metrics_reports,
)


class ResearchTableMetricsTests(unittest.TestCase):
    def test_metrics_aggregate_sessions_models_tools_and_warnings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_base_session(root)
            self._write_e2e_session(root)
            self._write_cli_smoke_summary(root)
            self._write_malformed_session(root)

            payload = summarize_research_table_metrics(root)

            self.assertEqual(len(payload["sessions"]), 3)
            session_ids = {item["session_id"] for item in payload["sessions"]}
            self.assertIn("session-base", session_ids)
            self.assertIn("session-e2e", session_ids)
            self.assertIn("cli-smoke-skipped", session_ids)

            base_session = next(item for item in payload["sessions"] if item["session_id"] == "session-base")
            self.assertEqual(base_session["model_turns_count"], 2)
            self.assertEqual(base_session["tool_turns_count"], 2)
            self.assertEqual(base_session["teacher_labels_created"], 0)
            self.assertEqual(base_session["training_items_created"], 1)
            self.assertTrue(base_session["deterministic_override_used"])

            e2e_session = next(item for item in payload["sessions"] if item["session_id"] == "session-e2e")
            self.assertEqual(e2e_session["teacher_labels_created"], 1)
            self.assertEqual(e2e_session["training_items_created"], 1)
            self.assertEqual(e2e_session["verified_discoveries_count"], 1)
            self.assertEqual(e2e_session["refuted_discoveries_count"], 1)

            cli_session = next(item for item in payload["sessions"] if item["session_id"] == "cli-smoke-skipped")
            self.assertEqual(cli_session["turns_count"], 0)
            self.assertEqual(cli_session["final_status"], "SKIPPED")
            self.assertEqual(cli_session["provider_statuses"]["gemini_cli"]["state"], "not_authenticated")

            models = {item["model_id"]: item for item in payload["models"]}
            self.assertEqual(models["alpha"]["discoveries_proposed"], 1)
            self.assertEqual(models["alpha"]["discoveries_verified"], 1)
            self.assertEqual(models["beta"]["discoveries_refuted"], 1)
            self.assertEqual(models["gemini_cli"]["sessions_count"], 1)

            tools = {item["tool_name"]: item for item in payload["tools"]}
            self.assertEqual(tools["mystic_verify_answer"]["pass_count"], 2)
            self.assertEqual(tools["mystic_verify_answer"]["fail_count"], 1)
            self.assertEqual(tools["mystic_verify_answer"]["override_count"], 2)
            self.assertEqual(tools["save_discovery_as_training_item"]["pass_count"], 1)

            self.assertTrue(payload["warnings"])

    def test_metrics_reports_are_written(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_base_session(root)

            payload = summarize_research_table_metrics(root)
            paths = write_research_table_metrics_reports(root, payload)

            json_path = Path(paths["json"])
            markdown_path = Path(paths["markdown"])
            self.assertTrue(json_path.exists())
            self.assertTrue(markdown_path.exists())
            json_payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(len(json_payload["sessions"]), 1)
            markdown = markdown_path.read_text(encoding="utf-8")
            self.assertIn("# Research Table Metrics", markdown)
            self.assertIn("session-base", markdown)
            self.assertEqual(markdown, render_research_table_metrics_markdown(payload))

    def _write_base_session(self, root: Path) -> None:
        session_dir = root / "mystic_data" / "research_table_sessions" / "session-base"
        session_dir.mkdir(parents=True, exist_ok=True)
        session_payload = {
            "session_id": "session-base",
            "created_at": "2026-06-30T01:00:00+00:00",
            "participants": ["alpha", "beta"],
            "participant_models": [
                {"model_id": "alpha", "provider": "mock", "model_name": "Alpha"},
                {"model_id": "beta", "provider": "mock", "model_name": "Beta"},
            ],
            "accepted_discoveries": [],
            "rejected_discoveries": [],
            "verification_requests": [{"request_id": "req-base", "target_discovery_id": "disc-alpha"}],
            "discoveries": [
                {
                    "discovery_id": "disc-alpha",
                    "source_turn_id": "turn-alpha",
                    "claim": "Candidate answer (2, 3)",
                    "type": "candidate_answer",
                    "status": "verified",
                }
            ],
            "turns": [
                {
                    "turn_id": "turn-alpha",
                    "phase": "independent_discovery",
                    "speaker_type": "model",
                    "speaker_id": "alpha",
                    "provider": "mock",
                    "model_name": "Alpha",
                    "role": "solver",
                    "status": "DRAFT_ONLY",
                    "content": "Candidate answer (2, 3)",
                    "discoveries": [{"discovery_id": "disc-alpha"}],
                    "latency_sec": 1.5,
                },
                {
                    "turn_id": "turn-beta",
                    "phase": "cross_critique",
                    "speaker_type": "model",
                    "speaker_id": "beta",
                    "provider": "mock",
                    "model_name": "Beta",
                    "role": "critic",
                    "status": "AUTH_REQUIRED",
                    "content": "Login required",
                    "latency_sec": 0.0,
                },
                {
                    "turn_id": "tool-verify-base",
                    "phase": "tool_verification",
                    "speaker_type": "tool",
                    "speaker_id": "mystic_verify_answer",
                    "provider": "tool",
                    "model_name": "deterministic_verifier",
                    "role": "verifier",
                    "status": "VERIFICATION_RESULT",
                    "summary": "VALID",
                    "content": "Verifier accepted the candidate.",
                },
                {
                    "turn_id": "tool-train-base",
                    "phase": "interactive_follow_up",
                    "speaker_type": "tool",
                    "speaker_id": "save_discovery_as_training_item",
                    "provider": "tool",
                    "model_name": "raven_training_writer",
                    "role": "save",
                    "status": "SAVED",
                    "content": "saved",
                },
            ],
            "final_status": "VALID",
            "final_decision_source": "deterministic_verifier",
        }
        (session_dir / "session.json").write_text(json.dumps(session_payload, indent=2), encoding="utf-8")
        (session_dir / "turns.json").write_text(json.dumps(session_payload["turns"], indent=2), encoding="utf-8")
        (session_dir / "discoveries.json").write_text(json.dumps(session_payload["discoveries"], indent=2), encoding="utf-8")
        (session_dir / "verification_requests.json").write_text(json.dumps(session_payload["verification_requests"], indent=2), encoding="utf-8")
        (session_dir / "final_synthesis.json").write_text(json.dumps({}, indent=2), encoding="utf-8")

    def _write_e2e_session(self, root: Path) -> None:
        scenario_dir = root / "mystic_data" / "e2e" / "research_table" / "scenario-e2e"
        session_dir = scenario_dir / "session"
        session_dir.mkdir(parents=True, exist_ok=True)
        session_payload = {
            "session_id": "session-e2e",
            "created_at": "2026-06-30T02:00:00+00:00",
            "participants": ["beta"],
            "participant_models": [
                {"model_id": "beta", "provider": "mock", "model_name": "Beta"},
            ],
            "accepted_discoveries": [
                {"discovery_id": "disc-beta-good", "claim": "Candidate answer (2, 4)", "status": "accepted"}
            ],
            "rejected_discoveries": [
                {"discovery_id": "disc-beta-bad", "claim": "Candidate answer (9, 9)", "status": "rejected"}
            ],
            "verification_requests": [
                {"request_id": "req-good", "target_discovery_id": "disc-beta-good", "result_verdict": "VALID"},
                {"request_id": "req-bad", "target_discovery_id": "disc-beta-bad", "result_verdict": "INVALID"},
            ],
            "discoveries": [
                {
                    "discovery_id": "disc-beta-good",
                    "source_turn_id": "turn-beta-good",
                    "claim": "Candidate answer (2, 4)",
                    "type": "candidate_answer",
                    "status": "verified",
                },
                {
                    "discovery_id": "disc-beta-bad",
                    "source_turn_id": "turn-beta-bad",
                    "claim": "Candidate answer (9, 9)",
                    "type": "candidate_answer",
                    "status": "refuted",
                },
            ],
            "turns": [
                {
                    "turn_id": "turn-beta-good",
                    "phase": "independent_discovery",
                    "speaker_type": "model",
                    "speaker_id": "beta",
                    "provider": "mock",
                    "model_name": "Beta",
                    "role": "solver",
                    "status": "DRAFT_ONLY",
                    "content": "Candidate answer (2, 4)",
                    "discoveries": [{"discovery_id": "disc-beta-good"}],
                    "latency_sec": 2.0,
                },
                {
                    "turn_id": "turn-beta-bad",
                    "phase": "discovery_sharing",
                    "speaker_type": "model",
                    "speaker_id": "beta",
                    "provider": "mock",
                    "model_name": "Beta",
                    "role": "critic",
                    "status": "ERROR",
                    "content": "Candidate answer (9, 9)",
                    "discoveries": [{"discovery_id": "disc-beta-bad"}],
                    "latency_sec": 1.0,
                },
                {
                    "turn_id": "tool-verify-good",
                    "phase": "tool_verification",
                    "speaker_type": "tool",
                    "speaker_id": "mystic_verify_answer",
                    "provider": "tool",
                    "model_name": "deterministic_verifier",
                    "role": "verifier",
                    "status": "VERIFICATION_RESULT",
                    "summary": "VALID",
                    "content": "valid",
                },
                {
                    "turn_id": "tool-verify-bad",
                    "phase": "tool_verification",
                    "speaker_type": "tool",
                    "speaker_id": "mystic_verify_answer",
                    "provider": "tool",
                    "model_name": "deterministic_verifier",
                    "role": "verifier",
                    "status": "VERIFICATION_RESULT",
                    "summary": "INVALID",
                    "content": "invalid",
                },
            ],
            "final_status": "INVALID",
            "final_decision_source": "deterministic_verifier",
        }
        summary_payload = {
            "session_id": "session-e2e",
            "teacher_labels_created": ["mystic_data/teacher_labels/label-e2e.json"],
            "training_items_created": ["mystic_data/training_items/train-e2e.json"],
            "phases_completed": [
                "independent_discovery",
                "discovery_sharing",
                "tool_verification",
                "final_synthesis",
            ],
            "final_status": "INVALID",
            "final_decision_source": "deterministic_verifier",
        }
        (scenario_dir / "summary.json").write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")
        (session_dir / "session.json").write_text(json.dumps(session_payload, indent=2), encoding="utf-8")
        (session_dir / "turns.json").write_text(json.dumps(session_payload["turns"], indent=2), encoding="utf-8")
        (session_dir / "discoveries.json").write_text(json.dumps(session_payload["discoveries"], indent=2), encoding="utf-8")
        (session_dir / "verification_requests.json").write_text(json.dumps(session_payload["verification_requests"], indent=2), encoding="utf-8")
        (session_dir / "final_synthesis.json").write_text(json.dumps({}, indent=2), encoding="utf-8")

    def _write_cli_smoke_summary(self, root: Path) -> None:
        scenario_dir = root / "mystic_data" / "e2e" / "cli_smoke" / "cli-smoke-skipped"
        scenario_dir.mkdir(parents=True, exist_ok=True)
        summary_payload = {
            "selected_participants": ["gemini_cli", "local_prime"],
            "effective_participants": ["local_prime"],
            "provider_auth_statuses": {
                "gemini_cli": {
                    "provider": "cli",
                    "model_name": "gemini_cli",
                    "state": "not_authenticated",
                    "message": "Login with Google.",
                    "available": True,
                    "authenticated": False,
                },
                "local_prime": {
                    "provider": "ollama",
                    "model_name": "deepseek-r1-distill-14b",
                    "state": "ready",
                    "message": "Ollama is reachable.",
                    "available": True,
                    "authenticated": True,
                },
            },
            "completed_phases": [],
            "final_status": "SKIPPED",
            "final_decision_source": "not_run",
        }
        (scenario_dir / "summary.json").write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")

    def _write_malformed_session(self, root: Path) -> None:
        session_dir = root / "mystic_data" / "research_table_sessions" / "broken-session"
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "session.json").write_text("{broken", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()

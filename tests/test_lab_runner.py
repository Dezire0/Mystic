from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mystic.mcp.tools import MysticToolbox
from mystic.models.router import ModelRouter


TEST_CONFIG = """
models:
  local_prime:
    provider: mock
    model: mock-prime
    role_defaults:
      - draft
  local_raven:
    provider: mock
    model: mock-raven
    role_defaults:
      - critique
policy:
  max_models_per_compare: 3
  timeout_per_model_seconds: 5
"""


class LabRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        config_path = self.root / "models.yaml"
        config_path.write_text(TEST_CONFIG, encoding="utf-8")
        router = ModelRouter(root_path=self.root, config_path=config_path)
        self.toolbox = MysticToolbox(root_path=self.root, router=router)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_lab_session_writes_expected_storage_files(self):
        created = self.toolbox.lab_session_create(
            problem="Find positive integers x, y such that x + y = 5.",
            domain="math",
            goal="Trace a structured lab session.",
            mode="cheap",
            participants=["local_prime", "local_raven"],
        )
        session_dir = self.root / "mystic_data" / "lab_sessions" / created["session_id"]
        self.assertTrue((session_dir / "session.json").exists())
        self.assertTrue((session_dir / "turns.json").exists())
        self.assertTrue((session_dir / "claims.json").exists())
        self.assertTrue((session_dir / "experiments.json").exists())
        self.assertTrue((session_dir / "failures.json").exists())
        self.assertTrue((session_dir / "memory_edges.json").exists())
        self.assertTrue((session_dir / "notebook.md").exists())
        self.assertTrue((session_dir / "report.md").exists())

    def test_lab_session_advance_generates_turns_and_experiments(self):
        created = self.toolbox.lab_session_create(
            problem="Find positive integers x, y such that x + y = 5.",
            domain="math",
            goal="Advance through the research loop.",
            mode="serious",
            participants=["local_prime", "local_raven"],
        )
        result = self.toolbox.lab_session_advance(
            session_id=created["session_id"],
            max_steps=4,
            use_model_arena=False,
            use_verifier=True,
        )
        self.assertTrue(result["new_turns"])
        self.assertTrue(result["new_experiments"])

    def test_lab_referee_review_updates_claim_state(self):
        created = self.toolbox.lab_session_create(
            problem="1/x + 1/y + 1/z = 1",
            domain="math",
            goal="Refute an invalid candidate.",
            mode="proof_critical",
            participants=["local_prime", "local_raven"],
        )
        claim_write = self.toolbox.lab_memory_write(
            session_id=created["session_id"],
            kind="claim",
            payload={
                "text": "(2,4,8) is a complete solution set.",
                "claim_type": "result",
                "status": "HEURISTIC",
                "confidence": "medium",
                "source_turn_id": "manual",
            },
        )
        loaded = self.toolbox.lab_session_get(session_id=created["session_id"])
        claim_id = loaded["claims"][0]["claim_id"]
        review = self.toolbox.lab_referee_review(
            session_id=created["session_id"],
            claim_id=claim_id,
            text="(2,4,8)",
            strictness="hostile",
        )
        self.assertEqual(review["verdict"], "INVALID")
        updated = self.toolbox.lab_session_get(session_id=created["session_id"])
        self.assertIn(updated["claims"][0]["status"], {"FAILED", "REFUTED"})
        self.assertTrue(updated["failures"])

    def test_lab_referee_review_can_use_mock_provider_when_requested(self):
        created = self.toolbox.lab_session_create(
            problem="Check whether x + y = 5 has a valid positive integer pair.",
            domain="math",
            goal="Run provider-backed referee review.",
            mode="proof_critical",
            participants=["mock"],
        )
        self.toolbox.lab_memory_write(
            session_id=created["session_id"],
            kind="claim",
            payload={
                "text": "A positive integer pair exists.",
                "claim_type": "result",
                "status": "HEURISTIC",
                "confidence": "low",
                "source_turn_id": "manual",
            },
        )
        with patch(
            "mystic.lab.provider_router.ProviderRouter.invoke",
            return_value={
                "status": "completed",
                "provider_id": "mock",
                "model": "mock-model",
                "output_text": '{"verdict":"VALID","critique":"Looks plausible.","first_fatal_error":"","recommended_next_action":"Keep claim."}',
                "raw_usage_safe": {},
                "latency_ms": 0,
                "error_type": "",
                "error_message_safe": "",
                "call_id": "call-mock",
                "storage_ref": "",
            },
        ):
            review = self.toolbox.lab_referee_review(
                session_id=created["session_id"],
                text="A positive integer pair exists.",
                strictness="hostile",
                provider="mock",
            )
        self.assertEqual(review["verdict"], "VALID")
        self.assertEqual(review["provider_result"]["status"], "completed")


if __name__ == "__main__":
    unittest.main()

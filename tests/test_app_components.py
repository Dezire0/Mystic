from __future__ import annotations

import unittest

from mystic.app.components import ClaimCard, FailureCard, StatusBadge


class AppComponentsTests(unittest.TestCase):
    def test_status_badges_render_expected_labels(self):
        proved = StatusBadge("PROVED")
        auth_required = StatusBadge("AUTH_REQUIRED")
        running = StatusBadge("RUNNING")

        self.assertIn("badge proved", proved)
        self.assertIn(">Proved<", proved)
        self.assertIn("badge auth_required", auth_required)
        self.assertIn(">Auth Required<", auth_required)
        self.assertIn("badge running", running)
        self.assertIn(">Running<", running)

    def test_claim_card_shows_status_and_evidence(self):
        html = ClaimCard(
            claim={
                "claim_id": "claim-1",
                "text": "Every surviving branch has verifier support.",
                "claim_type": "result",
                "status": "TESTED",
                "confidence": "high",
                "source_turn_id": "turn-7",
                "supporting_evidence": ["verify-valid.json", "session-turn-7"],
                "refuting_evidence": ["none"],
                "related_experiments": ["exp-3"],
                "related_failures": ["failure-2"],
                "updated_at": "2026-07-01T10:00:00Z",
            }
        )

        self.assertIn("Every surviving branch has verifier support.", html)
        self.assertIn("Tested", html)
        self.assertIn("verify-valid.json", html)
        self.assertIn("failure-2", html)

    def test_failure_card_highlights_first_fatal_error(self):
        html = FailureCard(
            failure={
                "failure_id": "failure-1",
                "claim_id": "claim-9",
                "source_turn_id": "turn-4",
                "first_fatal_error": "Candidate omits the (2,4,4) branch.",
                "failure_type": "logic_gap",
                "lesson": "Re-check case splits before synthesis.",
                "reusable_as_training_data": True,
            }
        )

        self.assertIn("Candidate omits the (2,4,4) branch.", html)
        self.assertIn("Re-check case splits before synthesis.", html)
        self.assertIn("training data", html)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from mystic.lab.reality_anchor import normalize_claim_status


class RealityAnchorTests(unittest.TestCase):
    def test_model_generated_claim_defaults_to_heuristic(self):
        self.assertEqual(normalize_claim_status(model_generated=True), "HEURISTIC")

    def test_invalid_verifier_refutes_claim(self):
        self.assertEqual(normalize_claim_status(verifier_verdict="INVALID"), "REFUTED")

    def test_symbolic_valid_result_marks_claim_proved(self):
        self.assertEqual(normalize_claim_status(verifier_verdict="VALID", method="symbolic"), "PROVED")

    def test_incomplete_proof_marks_needs_more_detail(self):
        self.assertEqual(normalize_claim_status(incomplete_proof=True), "NEEDS_MORE_DETAIL")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from scripts.evaluate_raven_lora import summarize_results


class EvaluateRavenLoraTests(unittest.TestCase):
    def test_summarize_results_computes_expected_rates(self):
        payload = summarize_results(
            [
                {"verdict_match": True, "valid_json": True, "output_length": 10, "failure": False},
                {"verdict_match": False, "valid_json": False, "output_length": 20, "failure": True},
            ]
        )
        self.assertEqual(payload["total"], 2)
        self.assertEqual(payload["exact_verdict_match_rate"], 0.5)
        self.assertEqual(payload["valid_json_rate"], 0.5)
        self.assertEqual(payload["invalid_json_rate"], 0.5)
        self.assertEqual(payload["average_output_length"], 15.0)
        self.assertEqual(payload["simple_failure_count"], 1)


if __name__ == "__main__":
    unittest.main()

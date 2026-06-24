from __future__ import annotations

import unittest

from mystic.raven_compare import build_comparison_record, should_promote_adapter, summarize_comparison_rows


class RavenCompareTests(unittest.TestCase):
    def test_summarize_comparison_rows(self):
        rows = [
            build_comparison_record(
                sample_id="s1",
                source="eval_script",
                problem="p",
                proof_text="proof",
                target_verdict="INVALID",
                base_critique={"verdict": "NEEDS_MORE_DETAIL", "parse_error": "bad", "first_fatal_error": "", "missing_assumptions": []},
                adapter_critique={"verdict": "INVALID", "parse_error": None, "first_fatal_error": "wrong step", "missing_assumptions": ["lemma"]},
                base_latency=0.3,
                adapter_latency=0.2,
                base_model="base",
                adapter_path="adapter",
                run_id="r1",
            )
        ]
        summary = summarize_comparison_rows(rows)
        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["adapter"]["valid_json_rate"], 1.0)
        self.assertEqual(summary["base"]["invalid_output_count"], 1)

    def test_should_promote_adapter(self):
        promote, reason = should_promote_adapter(
            {
                "base": {
                    "valid_json_rate": 0.5,
                    "verdict_match_rate": 0.5,
                    "first_fatal_error_nonempty_rate": 0.5,
                    "invalid_output_count": 1,
                },
                "adapter": {
                    "valid_json_rate": 1.0,
                    "verdict_match_rate": 0.5,
                    "first_fatal_error_nonempty_rate": 1.0,
                    "invalid_output_count": 0,
                },
            }
        )
        self.assertTrue(promote)
        self.assertIn("better or equal", reason)


if __name__ == "__main__":
    unittest.main()

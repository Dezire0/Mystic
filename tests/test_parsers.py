from __future__ import annotations

import unittest

from mystic.parsers import parse_raven_output
from mystic.final_answer_verifier import extract_candidate_tuples, enumerate_egyptian_fraction_solutions


class ParserTests(unittest.TestCase):
    def test_parse_raven_output_accepts_fenced_json(self):
        critique = parse_raven_output(
            raw_output="""```json
{"verdict":"GAP","first_fatal_error":"missing lemma","missing_assumptions":["lemma"],"invalid_steps":[],"valid_steps":["setup"],"repair_possible":true,"confidence":0.7,"final_status":"GAP"}
```""",
            sample_id="s1",
            run_id="r1",
            backend="ollama",
            model="qwen2.5:7b",
        )
        self.assertEqual(critique["verdict"], "GAP")
        self.assertEqual(critique["missing_assumptions"], ["lemma"])

    def test_parse_raven_output_falls_back_on_invalid_json(self):
        critique = parse_raven_output(
            raw_output="I think this looks wrong.",
            sample_id="s1",
            run_id="r1",
            backend="ollama",
            model="qwen2.5:7b",
        )
        self.assertEqual(critique["verdict"], "NEEDS_MORE_DETAIL")
        self.assertEqual(critique["first_fatal_error"], "Raven returned invalid JSON.")
        self.assertTrue(critique["parse_error"])

    def test_egyptian_fraction_verifier_enumerates_expected_solutions(self):
        self.assertEqual(
            enumerate_egyptian_fraction_solutions(),
            [(2, 3, 6), (2, 4, 4), (3, 3, 3)],
        )
        self.assertEqual(
            extract_candidate_tuples("(2,4,8), (2,3,6), (3,3,3)"),
            [(2, 4, 8), (2, 3, 6), (3, 3, 3)],
        )

    def test_parse_raven_output_marks_invalid_when_candidate_fails_substitution(self):
        problem = "1/x + 1/y + 1/z = 1, x <= y <= z, positive integers"
        answer_text = "All ordered solutions are (2,4,8), (2,3,6), (3,3,3)."
        critique = parse_raven_output(
            raw_output='{"verdict":"GAP","first_fatal_error":"","missing_assumptions":[],"invalid_steps":[],"valid_steps":[],"repair_possible":true,"confidence":0.6,"final_status":"GAP"}',
            sample_id="s1",
            run_id="r1",
            backend="ollama",
            model="qwen2.5:7b",
            problem=problem,
            answer_text=answer_text,
        )
        self.assertEqual(critique["verdict"], "INVALID")
        self.assertIn("(2, 4, 8)", critique["first_fatal_error"])
        self.assertIn("Missing valid solutions: (2, 4, 4)", " ".join(critique["invalid_steps"]))

    def test_parse_raven_output_accepts_complete_egyptian_fraction_solution_set(self):
        problem = "1/x + 1/y + 1/z = 1, x <= y <= z, positive integers"
        answer_text = "The complete solutions are (2,3,6), (2,4,4), (3,3,3)."
        critique = parse_raven_output(
            raw_output='{"verdict":"VALID","first_fatal_error":"","missing_assumptions":[],"invalid_steps":[],"valid_steps":[],"repair_possible":false,"confidence":0.9,"final_status":"VALID"}',
            sample_id="s1",
            run_id="r1",
            backend="ollama",
            model="qwen2.5:7b",
            problem=problem,
            answer_text=answer_text,
        )
        self.assertEqual(critique["verdict"], "VALID")
        self.assertEqual(critique["first_fatal_error"], "")


if __name__ == "__main__":
    unittest.main()

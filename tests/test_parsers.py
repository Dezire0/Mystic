from __future__ import annotations

import unittest

from mystic.final_answer_verifier import (
    enumerate_egyptian_fraction_solutions,
    extract_candidate_tuples,
    verify_final_answer,
)
from mystic.verification.integer_bruteforce import search_integer_solutions
from mystic.parsers import parse_raven_output


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

    def test_generic_substitution_verifier_accepts_valid_tuple(self):
        verification = verify_final_answer(
            problem="positive integers x, y satisfy x + y = 5",
            answer_text="Candidate solution: (2,3)",
        )
        assert verification is not None
        self.assertEqual(verification["verdict"], "VALID")
        self.assertTrue(verification["valid"])
        self.assertEqual(verification["passed_candidates"], ["(2, 3)"])

    def test_generic_substitution_verifier_rejects_invalid_tuple(self):
        verification = verify_final_answer(
            problem="positive integers x, y satisfy x + y = 5",
            answer_text="Candidate solution: (2,2)",
        )
        assert verification is not None
        self.assertEqual(verification["verdict"], "INVALID")
        self.assertIn("(2, 2)", verification["first_fatal_error"])
        self.assertFalse(verification["valid"])
        self.assertEqual(verification["failed_candidates"], ["(2, 2)"])

    def test_generic_substitution_verifier_skips_when_problem_uses_unknown_variable(self):
        verification = verify_final_answer(
            problem="positive integers x, y, z satisfy x + z = 5",
            answer_text="Candidate solution: (2,3)",
        )
        self.assertIsNone(verification)

    def test_integer_search_finds_small_ordered_solution_set(self):
        result = search_integer_solutions(
            problem="positive integers x, y satisfy x + y = 5, x <= y",
            variable_order=["x", "y"],
            bounds={"x": (1, 4), "y": (1, 4)},
        )
        self.assertEqual(result.solutions, [(1, 4), (2, 3)])

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

    def test_parse_raven_output_marks_all_bad_integer_tuples_invalid(self):
        problem = "1/x + 1/y + 1/z = 1, x <= y <= z, positive integers"
        answer_text = "Candidate tuples: (3,6,4), (4,5,7)."
        critique = parse_raven_output(
            raw_output='{"verdict":"GAP","first_fatal_error":"","missing_assumptions":[],"invalid_steps":[],"valid_steps":[],"repair_possible":true,"confidence":0.4,"final_status":"GAP"}',
            sample_id="s2",
            run_id="r2",
            backend="ollama",
            model="qwen2.5:7b",
            problem=problem,
            answer_text=answer_text,
        )
        combined = " ".join(critique["invalid_steps"])
        self.assertEqual(critique["verdict"], "INVALID")
        self.assertIn("(3, 6, 4)", combined)
        self.assertIn("y=6 > z=4", combined)
        self.assertIn("3/4 != 1", combined)
        self.assertIn("(4, 5, 7)", combined)
        self.assertIn("83/140 != 1", combined)
        self.assertIn("Missing valid solutions: (2, 3, 6), (2, 4, 4), (3, 3, 3)", combined)

    def test_final_verifier_reports_missing_complete_solution_set(self):
        verification = verify_final_answer(
            problem="1/x + 1/y + 1/z = 1, x <= y <= z, positive integers",
            answer_text="All ordered solutions are (2,3,6), (3,3,3).",
        )
        assert verification is not None
        self.assertEqual(verification["verdict"], "INVALID")
        self.assertEqual(verification["missing_candidates"], ["(2, 4, 4)"])
        self.assertIn("Bounded integer search", verification["reasoning"])

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

    def test_parse_raven_output_does_not_crash_when_verifier_cannot_map_variables(self):
        critique = parse_raven_output(
            raw_output='{"verdict":"GAP","first_fatal_error":"missing justification","missing_assumptions":[],"invalid_steps":[],"valid_steps":[],"repair_possible":true,"confidence":0.5,"final_status":"GAP"}',
            sample_id="s1",
            run_id="r1",
            backend="ollama",
            model="qwen2.5:7b",
            problem="positive integers x, y, z satisfy x + z = 5",
            answer_text="Candidate solution: (2,3)",
        )
        self.assertEqual(critique["verdict"], "GAP")
        self.assertEqual(critique["first_fatal_error"], "missing justification")


if __name__ == "__main__":
    unittest.main()

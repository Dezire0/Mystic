from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()

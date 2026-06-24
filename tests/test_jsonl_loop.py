from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mystic.jsonl_loop import (
    append_jsonl,
    ensure_data_dirs,
    export_raven_lora_rows,
    processed_ids,
    read_jsonl,
)
from scripts.mystic_loop import main as loop_main


class _LoopClient:
    def __init__(self, *, raven_output: str) -> None:
        self.raven_output = raven_output

    def generate_text(self, *, model: str, system_prompt: str, user_prompt: str) -> str:
        if "Mystic-Proof" in system_prompt:
            return "Attempted proof with explicit intermediate steps."
        if "Mystic-Raven" in system_prompt:
            return self.raven_output
        raise AssertionError("Unexpected prompt")


class JsonlLoopTests(unittest.TestCase):
    def test_export_raven_lora_rows_shape(self):
        rows = export_raven_lora_rows(
            [
                {
                    "sample_id": "s1",
                    "run_id": "r1",
                    "problem": "p",
                    "proof_text": "proof",
                    "verdict": "INVALID",
                    "first_fatal_error": "bad step",
                    "missing_assumptions": [],
                    "invalid_steps": ["bad step"],
                    "valid_steps": [],
                    "repair_possible": True,
                    "confidence": 0.4,
                    "final_status": "INVALID",
                }
            ]
        )
        self.assertEqual(rows[0]["classification"], "INVALID")
        self.assertIn("Problem:\np", rows[0]["input"])
        self.assertIn('"verdict": "INVALID"', rows[0]["output"])

    def test_loop_is_resumable_after_successful_processing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir) / "mystic_data"
            paths = ensure_data_dirs(base)
            append_jsonl(
                paths.raw_file,
                {
                    "sample_id": "numina-0001",
                    "problem": "Prove something.",
                    "reference_solution": "ref",
                    "raw": {},
                },
            )
            raven_json = json.dumps(
                {
                    "verdict": "VALID",
                    "first_fatal_error": "",
                    "missing_assumptions": [],
                    "invalid_steps": [],
                    "valid_steps": ["Uses a coherent structure."],
                    "repair_possible": False,
                    "confidence": 0.9,
                    "final_status": "VALID",
                }
            )
            fake_client = _LoopClient(raven_output=raven_json)

            with patch("scripts.mystic_loop.build_client", return_value=fake_client):
                first = loop_main(["--base-dir", str(base), "--limit", "10", "--backend", "ollama"])
                second = loop_main(["--base-dir", str(base), "--limit", "10", "--backend", "ollama"])

            self.assertEqual(first, 0)
            self.assertEqual(second, 0)
            self.assertEqual(len(read_jsonl(paths.results_file)), 1)
            self.assertEqual(len(read_jsonl(paths.verified_file)), 1)
            self.assertEqual(len(read_jsonl(paths.rejected_file)), 0)
            self.assertEqual(len(read_jsonl(paths.run_log_file)), 1)
            self.assertEqual(processed_ids(paths.processed_ids_file), {"numina-0001"})

    def test_loop_downgrades_invalid_raven_json_without_crashing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir) / "mystic_data"
            paths = ensure_data_dirs(base)
            append_jsonl(
                paths.raw_file,
                {
                    "sample_id": "numina-0002",
                    "problem": "Prove another claim.",
                    "reference_solution": "",
                    "raw": {},
                },
            )
            fake_client = _LoopClient(raven_output="not valid json at all")

            with patch("scripts.mystic_loop.build_client", return_value=fake_client):
                result = loop_main(["--base-dir", str(base), "--limit", "10", "--backend", "ollama"])

            self.assertEqual(result, 0)
            rejected_rows = read_jsonl(paths.rejected_file)
            critique_rows = read_jsonl(paths.raven_critiques_file)
            run_log_rows = read_jsonl(paths.run_log_file)
            self.assertEqual(rejected_rows[0]["verdict"], "NEEDS_MORE_DETAIL")
            self.assertEqual(critique_rows[0]["verdict"], "NEEDS_MORE_DETAIL")
            self.assertTrue(critique_rows[0]["parse_error"])
            self.assertEqual(run_log_rows[0]["status"], "NEEDS_MORE_DETAIL")

    def test_loop_compare_raven_appends_comparison_rows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir) / "mystic_data"
            paths = ensure_data_dirs(base)
            append_jsonl(
                paths.raw_file,
                {
                    "sample_id": "numina-0003",
                    "problem": "Check a claim.",
                    "reference_solution": "",
                    "raw": {},
                },
            )
            generator_client = _LoopClient(raven_output="")
            adapter_client = _LoopClient(
                raven_output=json.dumps(
                    {
                        "verdict": "INVALID",
                        "first_fatal_error": "bad step",
                        "missing_assumptions": ["lemma"],
                        "invalid_steps": ["bad step"],
                        "valid_steps": [],
                        "repair_possible": True,
                        "confidence": 0.8,
                        "final_status": "INVALID",
                    }
                )
            )
            base_client = _LoopClient(
                raven_output=json.dumps(
                    {
                        "verdict": "NEEDS_MORE_DETAIL",
                        "first_fatal_error": "",
                        "missing_assumptions": [],
                        "invalid_steps": [],
                        "valid_steps": [],
                        "repair_possible": True,
                        "confidence": 0.1,
                        "final_status": "NEEDS_MORE_DETAIL",
                    }
                )
            )

            with patch(
                "scripts.mystic_loop.build_client",
                side_effect=[generator_client, adapter_client, base_client],
            ):
                result = loop_main(
                    [
                        "--base-dir",
                        str(base),
                        "--limit",
                        "10",
                        "--backend",
                        "adapter",
                        "--compare-raven",
                        "--base-model",
                        "Qwen/Qwen2.5-0.5B-Instruct",
                        "--adapter-path",
                        "mystic_data/adapters/raven_lora_v0",
                    ]
                )

            self.assertEqual(result, 0)
            comparison_rows = read_jsonl(paths.raven_comparison_results_file)
            self.assertEqual(len(comparison_rows), 1)
            self.assertTrue(comparison_rows[0]["adapter_better_or_equal"])
            adapter_logs = read_jsonl(paths.adapter_inference_log_file)
            self.assertGreaterEqual(len(adapter_logs), 2)


if __name__ == "__main__":
    unittest.main()

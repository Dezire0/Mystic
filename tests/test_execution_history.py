from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mystic.execution_history import collect_execution_records, format_duration, render_execution_history_html


def append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


class ExecutionHistoryTests(unittest.TestCase):
    def test_collect_execution_records_merges_training_eval_compare_and_loop(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir) / "mystic_data"
            logs = base / "logs"
            cycles = base / "cycles" / "cycle_1"
            logs.mkdir(parents=True, exist_ok=True)
            cycles.mkdir(parents=True, exist_ok=True)

            append_jsonl(
                logs / "training_log.jsonl",
                {
                    "event_id": "train-1",
                    "timestamp": "2026-06-24T10:00:00+00:00",
                    "status": "TRAIN_OK",
                    "base_model": "Qwen/Qwen2.5-0.5B-Instruct",
                    "output_dir": "mystic_data/adapters/raven_lora_v0",
                    "metrics": {"train_runtime": 12.5},
                },
            )
            append_jsonl(
                logs / "raven_eval_results.jsonl",
                {
                    "event_id": "eval-1",
                    "timestamp": "2026-06-24T10:05:00+00:00",
                    "base_model": "Qwen/Qwen2.5-0.5B-Instruct",
                    "metrics": {"invalid_json_rate": 0.0, "simple_failure_count": 0},
                },
            )
            append_jsonl(
                logs / "raven_comparison_results.jsonl",
                {
                    "event_id": "compare-1",
                    "timestamp": "2026-06-24T10:06:00+00:00",
                    "kind": "summary",
                    "base_model": "Qwen/Qwen2.5-0.5B-Instruct",
                    "metrics": {"total": 2, "adapter_better_or_equal_rate": 1.0, "adapter": {"average_latency": 1.5}},
                },
            )
            append_jsonl(
                logs / "run_log.jsonl",
                {
                    "event_id": "run-1a",
                    "timestamp": "2026-06-24T10:10:00+00:00",
                    "run_id": "loop-1",
                    "raven_model": "mystic_data/adapters/raven_lora_v0",
                    "generator_model": "qwen2.5:7b",
                    "status": "INVALID",
                },
            )
            append_jsonl(
                logs / "run_log.jsonl",
                {
                    "event_id": "run-1b",
                    "timestamp": "2026-06-24T10:10:05+00:00",
                    "run_id": "loop-1",
                    "raven_model": "mystic_data/adapters/raven_lora_v0",
                    "generator_model": "qwen2.5:7b",
                    "status": "COMPARE_OK",
                },
            )
            (cycles / "kaggle_poll_summary.json").write_text(
                json.dumps(
                    {
                        "timestamp": "2026-06-24T10:20:00+00:00",
                        "final_status": "complete",
                        "base_model": "Qwen/Qwen2.5-0.5B-Instruct",
                        "checks": [
                            {"timestamp": "2026-06-24T10:15:00+00:00"},
                            {"timestamp": "2026-06-24T10:20:00+00:00"},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            records = collect_execution_records(base)

            self.assertEqual(len(records), 5)
            self.assertEqual(records[0].source, "cycle_poll")
            training = next(record for record in records if record.source == "training_log")
            self.assertEqual(training.part, "raven")
            self.assertEqual(training.duration_seconds, 12.5)
            loop = next(record for record in records if record.source == "run_log")
            self.assertEqual(loop.status, "LOOP_OK")
            self.assertAlmostEqual(loop.duration_seconds or 0.0, 5.0, places=2)

    def test_render_execution_history_html_contains_table_rows(self):
        html_text = render_execution_history_html(
            records=[],
            generated_at="2026-06-24T10:00:00+00:00",
        )
        self.assertIn("Mystic Execution History", html_text)
        self.assertIn("기록이 없습니다", html_text)

    def test_format_duration(self):
        self.assertEqual(format_duration(None), "-")
        self.assertEqual(format_duration(0.5), "0.50s")
        self.assertEqual(format_duration(5.2), "5.2s")
        self.assertEqual(format_duration(65.0), "1m 5s")


if __name__ == "__main__":
    unittest.main()

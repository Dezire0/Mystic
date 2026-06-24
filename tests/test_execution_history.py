from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mystic.execution_history import (
    collect_execution_records,
    format_duration,
    render_execution_history_html,
    write_execution_history_outputs,
)


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

    def test_collect_execution_records_includes_specialist_batch_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir) / "mystic_data"
            reports = base / "reports"
            logs = base / "logs" / "training_jobs"
            reports.mkdir(parents=True, exist_ok=True)
            logs.mkdir(parents=True, exist_ok=True)

            manifest_path = logs / "core-manual-20260624T141701Z.json"
            manifest_path.write_text(
                json.dumps({"created_at": "20260624T141701Z"}),
                encoding="utf-8",
            )
            batch_payload = [
                {
                    "agent": "core",
                    "returncode": 0,
                    "stdout": json.dumps(
                        {
                            "job_manifest": str(manifest_path),
                            "local_training": {
                                "plan": {
                                    "agent": "core",
                                    "model_name": "sshleifer/tiny-gpt2",
                                },
                                "result": {
                                    "metrics": {
                                        "train_runtime": 1.52,
                                    }
                                },
                            },
                        }
                    ),
                }
            ]
            (reports / "specialist_training_batch_run.json").write_text(
                json.dumps(batch_payload, indent=2),
                encoding="utf-8",
            )

            records = collect_execution_records(base)
            batch_record = next(record for record in records if record.source == "specialist_training_batch")
            self.assertEqual(batch_record.part, "core")
            self.assertEqual(batch_record.model_name, "sshleifer/tiny-gpt2")
            self.assertTrue(batch_record.success)
            self.assertAlmostEqual(batch_record.duration_seconds or 0.0, 1.52, places=2)

    def test_render_execution_history_html_contains_table_rows(self):
        html_text = render_execution_history_html(
            records=[],
            generated_at="2026-06-24T10:00:00+00:00",
        )
        self.assertIn("Mystic Execution History", html_text)
        self.assertIn("Continuous Training", html_text)
        self.assertIn("기록이 없습니다", html_text)
        self.assertIn("http-equiv=\"refresh\"", html_text)

    def test_collect_execution_records_prefers_append_only_specialist_history(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir) / "mystic_data"
            logs = base / "logs"
            logs.mkdir(parents=True, exist_ok=True)

            append_jsonl(
                logs / "specialist_training_history.jsonl",
                {
                    "event_id": "spec-1",
                    "timestamp": "2026-06-24T11:00:00+00:00",
                    "agent": "physics",
                    "division": "applied",
                    "model_name": "sshleifer/tiny-gpt2",
                    "base_model": "Qwen/Qwen2.5-0.5B-Instruct",
                    "duration_seconds": 9.5,
                    "returncode": 0,
                    "success": True,
                    "status": "TRAIN_OK",
                },
            )

            records = collect_execution_records(base)
            self.assertEqual(len(records), 1)
            record = records[0]
            self.assertEqual(record.source, "specialist_training_history")
            self.assertEqual(record.part, "physics")
            self.assertEqual(record.model_name, "sshleifer/tiny-gpt2")
            self.assertTrue(record.success)
            self.assertAlmostEqual(record.duration_seconds or 0.0, 9.5, places=2)

    def test_write_execution_history_outputs_writes_html_and_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir) / "mystic_data"
            logs = base / "logs"
            logs.mkdir(parents=True, exist_ok=True)
            state_dir = base / "state"
            state_dir.mkdir(parents=True, exist_ok=True)
            append_jsonl(
                logs / "training_log.jsonl",
                {
                    "event_id": "train-2",
                    "timestamp": "2026-06-24T10:00:00+00:00",
                    "status": "TRAIN_OK",
                    "base_model": "sshleifer/tiny-gpt2",
                    "output_dir": "mystic_data/adapters/core_router_lora_v0",
                    "metrics": {"train_runtime": 1.25},
                },
            )
            (state_dir / "continuous_training_state.json").write_text(
                json.dumps(
                    {
                        "status": "running",
                        "current_cycle": 3,
                        "completed_cycles": 2,
                        "active_slug": "proofnet",
                        "next_slug": "openthoughts",
                        "last_heartbeat": "2026-06-24T10:00:05+00:00",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            payload = write_execution_history_outputs(base)

            html_path = Path(str(payload["output_html"]))
            json_path = Path(str(payload["output_json"]))
            self.assertTrue(html_path.exists())
            self.assertTrue(json_path.exists())
            self.assertIn("sshleifer/tiny-gpt2", html_path.read_text(encoding="utf-8"))
            self.assertIn("Continuous Training", html_path.read_text(encoding="utf-8"))
            json_payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(json_payload["record_count"], 1)
            self.assertEqual(json_payload["continuous_status"]["status"], "running")

    def test_format_duration(self):
        self.assertEqual(format_duration(None), "-")
        self.assertEqual(format_duration(0.5), "0.50s")
        self.assertEqual(format_duration(5.2), "5.2s")
        self.assertEqual(format_duration(65.0), "1m 5s")


if __name__ == "__main__":
    unittest.main()

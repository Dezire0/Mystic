from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mystic.discord_dashboard import (
    GREEN,
    PAGE_SIZE,
    RED,
    YELLOW,
    expert_detail_page,
    level_from_percent,
    load_dashboard_snapshot,
    overview_page,
    render_level_badge,
)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


class DiscordDashboardTests(unittest.TestCase):
    def test_level_badge_maps_percent_to_level_and_xp(self):
        self.assertEqual(level_from_percent(0), 1)
        self.assertEqual(level_from_percent(60), 7)
        self.assertEqual(level_from_percent(100), 10)
        self.assertEqual(render_level_badge(32), "Lv.4 XP 2/10")
        self.assertEqual(render_level_badge(100), "Lv.10 MAX")

    def test_dashboard_snapshot_builds_overview_and_detail(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir) / "mystic_data"
            (base / "logs").mkdir(parents=True, exist_ok=True)
            (base / "train_ready").mkdir(parents=True, exist_ok=True)
            (base / "state").mkdir(parents=True, exist_ok=True)
            (base / "reports").mkdir(parents=True, exist_ok=True)

            (base / "train_ready" / "prime_train_ready.jsonl").write_text('{"x":1}\n' * 100, encoding="utf-8")
            (base / "train_ready" / "raven_train_ready.jsonl").write_text('{"x":1}\n' * 58, encoding="utf-8")
            (base / "logs" / "specialist_training_history.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "event_id": "prime-ok",
                                "timestamp": "2026-06-25T00:00:00+00:00",
                                "agent": "prime",
                                "division": "Pure Math",
                                "model_name": "deepseek-r1-distill-14b",
                                "base_model": "deepseek-r1-distill-14b",
                                "success": True,
                                "status": "TRAIN_OK",
                                "duration_seconds": 120.0,
                            }
                        ),
                        json.dumps(
                            {
                                "event_id": "raven-fail",
                                "timestamp": "2026-06-25T01:00:00+00:00",
                                "agent": "raven",
                                "division": "Verification",
                                "model_name": "Qwen/Qwen2.5-0.5B-Instruct",
                                "base_model": "Qwen/Qwen2.5-0.5B-Instruct",
                                "success": False,
                                "status": "TRAIN_ERROR",
                                "duration_seconds": 60.0,
                                "error": "adapter load failed",
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            write_json(
                base / "state" / "continuous_training_state.json",
                {
                    "status": "running",
                    "current_cycle": 5,
                    "current_run_id": "continuous_cycle_000005_openmathinstruct_2",
                    "active_slug": "openmathinstruct_2",
                    "next_slug": "proofnet",
                    "cycle_started_at": "2026-06-25T01:10:00+00:00",
                },
            )
            write_json(
                base / "state" / "continuous_training_progress.json",
                {
                    "run_id": "continuous_cycle_000005_openmathinstruct_2",
                    "run_label": "continuous_cycle_000005_openmathinstruct_2",
                    "status": "running",
                    "iteration": 1,
                    "iterations_total": 1,
                    "total_steps": 4,
                    "completed_steps": 1,
                    "current_step_index": 2,
                    "current_step_label": "전문가 학습 배치 실행",
                    "progress_percent": 25,
                },
            )
            write_json(
                base / "state" / "remote_cycle_state.json",
                {
                    "status": "running",
                    "active_cycle_id": "remote_cycle_0042",
                    "current_phase": "polling",
                    "current_dataset_ref": "dyrakd/mystic-cycle-remote-cycle-0042",
                    "cycle_started_at": "2026-06-25T01:12:00+00:00",
                },
            )

            snapshot = load_dashboard_snapshot(base)
            self.assertGreaterEqual(len(snapshot["experts"]), PAGE_SIZE)
            self.assertEqual(snapshot["total_train_ready_rows"], 158)
            self.assertGreaterEqual(snapshot["overall_progress_percent"], 0)

            prime = next(item for item in snapshot["experts"] if item.agent == "prime")
            raven = next(item for item in snapshot["experts"] if item.agent == "raven")
            self.assertEqual(prime.status_kind, YELLOW)
            self.assertEqual(prime.status_text, "학습 중")
            self.assertEqual(prime.progress_percent, 25)
            self.assertIn("2/4 단계", prime.status_detail)
            self.assertEqual(prime.dataset_progress_text, "0/19 datasets")
            self.assertEqual(raven.status_kind, YELLOW)
            self.assertEqual(raven.status_text, "학습 중")
            self.assertGreaterEqual(raven.progress_percent, 70)

            overview = overview_page(snapshot, 0)
            self.assertIn("Mystic 학습 개요", overview["title"])
            self.assertIn("전체 진행", [field["name"] for field in overview["fields"]])
            self.assertNotIn("100%", overview["description"])
            self.assertIn("학습 중", overview["description"])
            self.assertIn("Lv.", overview["description"])
            self.assertIn("다음:", [field["value"] for field in overview["fields"]][0])
            self.assertIn("현재 단계:", [field["value"] for field in overview["fields"]][2])

            detail = expert_detail_page(snapshot, "raven")
            self.assertIn("실패 로그", [field["name"] for field in detail["fields"]])
            self.assertIn("데이터셋 진행", [field["name"] for field in detail["fields"]])
            self.assertIn("레벨", [field["name"] for field in detail["fields"]])
            self.assertIn("총 학습 데이터셋", [field["name"] for field in detail["fields"]])
            self.assertIn("남은 데이터셋", [field["name"] for field in detail["fields"]])

    def test_failed_expert_is_red_when_not_active(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir) / "mystic_data"
            (base / "logs").mkdir(parents=True, exist_ok=True)
            (base / "train_ready").mkdir(parents=True, exist_ok=True)
            (base / "state").mkdir(parents=True, exist_ok=True)
            (base / "logs" / "specialist_training_history.jsonl").write_text(
                json.dumps(
                    {
                        "event_id": "logic-fail",
                        "timestamp": "2026-06-25T02:00:00+00:00",
                        "agent": "logic",
                        "division": "Pure Math",
                        "model_name": "qwen3-14b",
                        "base_model": "qwen3-14b",
                        "success": False,
                        "status": "TRAIN_ERROR",
                        "duration_seconds": 10.0,
                        "error": "bad sample",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            write_json(base / "state" / "continuous_training_state.json", {"status": "sleeping", "active_slug": ""})
            write_json(base / "state" / "remote_cycle_state.json", {"status": "sleeping", "current_phase": ""})

            snapshot = load_dashboard_snapshot(base)
            logic = next(item for item in snapshot["experts"] if item.agent == "logic")
            self.assertEqual(logic.status_kind, RED)
            self.assertIn("bad sample", logic.error_excerpt)

    def test_waiting_expert_is_yellow(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir) / "mystic_data"
            (base / "train_ready").mkdir(parents=True, exist_ok=True)
            (base / "state").mkdir(parents=True, exist_ok=True)
            (base / "train_ready" / "report_train_ready.jsonl").write_text('{"x":1}\n' * 50, encoding="utf-8")
            write_json(base / "state" / "continuous_training_state.json", {"status": "sleeping", "active_slug": ""})
            write_json(base / "state" / "remote_cycle_state.json", {"status": "sleeping", "current_phase": ""})

            snapshot = load_dashboard_snapshot(base)
            report = next(item for item in snapshot["experts"] if item.agent == "report")
            self.assertEqual(report.status_kind, GREEN)
            self.assertEqual(report.status_text, "대기")

    def test_progress_uses_dataset_metadata_coverage(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir) / "mystic_data"
            (base / "train_ready").mkdir(parents=True, exist_ok=True)
            (base / "state").mkdir(parents=True, exist_ok=True)
            (base / "reports").mkdir(parents=True, exist_ok=True)
            rows = [
                {
                    "metadata": {"dataset": "numinamath_cot"},
                },
                {
                    "metadata": {"dataset": "openmathinstruct_2"},
                },
                {
                    "metadata": {"dataset": "openr1_mixture_of_thoughts"},
                },
            ]
            (base / "train_ready" / "prime_train_ready.jsonl").write_text(
                "\n".join(json.dumps(row) for row in rows) + "\n",
                encoding="utf-8",
            )
            (base / "logs").mkdir(parents=True, exist_ok=True)
            (base / "logs" / "specialist_training_history.jsonl").write_text(
                json.dumps(
                    {
                        "event_id": "prime-ok",
                        "timestamp": "2026-06-25T02:00:00+00:00",
                        "agent": "prime",
                        "division": "Pure Math",
                        "model_name": "deepseek-r1-distill-14b",
                        "base_model": "deepseek-r1-distill-14b",
                        "success": True,
                        "status": "TRAIN_OK",
                        "duration_seconds": 12.0,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            write_json(base / "state" / "continuous_training_state.json", {"status": "sleeping", "active_slug": ""})
            write_json(base / "state" / "remote_cycle_state.json", {"status": "sleeping", "current_phase": ""})

            snapshot = load_dashboard_snapshot(base)
            prime = next(item for item in snapshot["experts"] if item.agent == "prime")
            self.assertEqual(prime.dataset_progress_text, "3/19 datasets")
            self.assertEqual(prime.dataset_covered_count, 3)
            self.assertEqual(prime.dataset_expected_count, 19)
            self.assertLess(prime.progress_percent, 30)
            self.assertEqual(prime.status_kind, GREEN)
            self.assertEqual(prime.status_text, "대기")

    def test_tool_only_agent_is_not_shown_as_fully_trained(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir) / "mystic_data"
            (base / "state").mkdir(parents=True, exist_ok=True)
            write_json(base / "state" / "continuous_training_state.json", {"status": "sleeping", "active_slug": ""})
            write_json(base / "state" / "remote_cycle_state.json", {"status": "sleeping", "current_phase": ""})

            snapshot = load_dashboard_snapshot(base)
            smt = next(item for item in snapshot["experts"] if item.agent == "smt")
            self.assertEqual(smt.status_text, "도구")
            self.assertEqual(smt.progress_percent, 0)
            self.assertEqual(smt.status_detail, "학습 대상 아님")
            self.assertEqual(smt.status_kind, GREEN)


if __name__ == "__main__":
    unittest.main()

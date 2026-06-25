from __future__ import annotations

import unittest
from dataclasses import replace
from unittest.mock import patch

from mystic.discord_dashboard import ExpertSnapshot
from mystic.research_lab import (
    ResearchSections,
    build_final_answer,
    build_critic_client,
    heuristic_specialist,
    parse_json_object,
    parse_sections,
    run_research_lab,
)


class FakeClient:
    def __init__(self, outputs: list[str]):
        self.outputs = outputs

    def generate_text(self, *, model: str, system_prompt: str, user_prompt: str) -> str:
        if not self.outputs:
            raise AssertionError("No fake outputs left")
        return self.outputs.pop(0)


class ResearchLabTests(unittest.TestCase):
    def test_heuristic_specialist_prefers_geometry_for_triangle_question(self):
        self.assertEqual(heuristic_specialist("In a triangle, prove the angle bisector theorem."), "geo")

    def test_parse_json_object_extracts_embedded_json(self):
        payload = parse_json_object("text before {\"specialist\":\"prime\",\"reason\":\"x\"}")
        self.assertEqual(payload["specialist"], "prime")

    def test_parse_sections_extracts_named_blocks(self):
        sections = parse_sections(
            "UNDERSTANDING:\nproblem\nSTRATEGY:\nplan\nEXECUTION:\nwork\nCONCLUSION:\nanswer\nUNCERTAINTIES:\nnone"
        )
        self.assertEqual(sections.understanding, "problem")
        self.assertEqual(sections.conclusion, "answer")

    def test_build_final_answer_adds_critique_warning(self):
        sections = ResearchSections(
            understanding="u",
            strategy="s",
            execution="e",
            conclusion="c",
            uncertainties="uncertain",
            raw_text="raw",
        )
        critique = type(
            "Critique",
            (),
            {
                "verdict": "GAP",
                "first_fatal_error": "missing lemma",
                "confidence": 0.2,
            },
        )()
        text = build_final_answer(
            plan=type("Plan", (), {"specialist": "prime", "strategy": "s"})(),
            sections=sections,
            critique=critique,
        )
        self.assertIn("검증 판정: GAP", text)
        self.assertIn("missing lemma", text)

    @patch("mystic.research_lab.load_model_defaults")
    @patch("mystic.research_lab.build_client")
    def test_build_critic_client_falls_back_when_adapter_runtime_is_missing(self, client_builder, defaults_loader):
        defaults_loader.return_value = {
            "backend": "ollama",
            "generator_model": "qwen2.5:7b",
            "raven_model": "qwen2.5:7b",
            "active_raven_backend": "adapter",
            "active_raven_base_model": "Qwen/Qwen2.5-0.5B-Instruct",
            "active_raven_adapter": "mystic_data/adapters/raven_lora_v0",
        }
        fallback_client = FakeClient(
            [
                '{"verdict":"VALID","first_fatal_error":"","missing_assumptions":[],"invalid_steps":[],"valid_steps":[],"repair_possible":true,"confidence":0.9,"final_status":"VALID"}'
            ]
        )
        client_builder.side_effect = [RuntimeError("No module named 'torch'"), fallback_client]

        backend, model, client = build_critic_client(config_path="configs/models.json")

        self.assertEqual(backend, "ollama")
        self.assertEqual(model, "qwen2.5:7b")
        self.assertIs(client, fallback_client)

    @patch("mystic.research_lab.load_model_defaults")
    @patch("mystic.research_lab.build_client")
    @patch("mystic.research_lab.load_dashboard_snapshot")
    def test_run_research_lab_uses_router_solver_and_critic(self, snapshot_loader, client_builder, defaults_loader):
        expert = ExpertSnapshot(
            agent="prime",
            name="Mystic-Prime",
            division="Pure Math",
            model="deepseek-r1-distill-14b",
            adapter="prime_lora_v0",
            dataset="OpenMathInstruct-2",
            train_ready_rows=10,
            progress_percent=60,
            status_text="학습 중",
            status_kind="yellow",
            status_emoji="🟡",
            status_color=0xF1C40F,
            is_active=True,
            is_trainable=True,
            latest_timestamp="2026-06-25T00:00:00+00:00",
            success_count=1,
            failure_count=0,
            eta_text="진행 중",
            error_excerpt="",
            stage="planning_only",
            dataset_covered_count=3,
            dataset_expected_count=19,
            dataset_progress_text="3/19 datasets",
            status_detail="OpenMathInstruct-2",
            progress_reason="현재 로컬 학습 기준",
        )
        snapshot_loader.return_value = {
            "experts": [
                expert,
                replace(expert, agent="logic", name="Mystic-Logic", division="Logic", model="qwen3-14b"),
                replace(expert, agent="pattern", name="Mystic-Pattern", division="Discovery", model="qwen3-14b"),
                replace(expert, agent="forge", name="Mystic-Forge", division="Discovery", model="qwen3-coder"),
                replace(expert, agent="raven", name="Mystic-Raven", division="Verification", model="qwen3-14b"),
            ]
        }
        defaults_loader.return_value = {
            "backend": "ollama",
            "generator_model": "qwen2.5:7b",
            "raven_model": "qwen2.5:7b",
            "active_raven_backend": "ollama",
        }
        client_builder.side_effect = [
            FakeClient(
                [
                    '{"specialist":"prime","reason":"정수론 문제로 보인다","strategy":"문제를 작은 단계로 쪼개 확인한다"}',
                    "UNDERSTANDING:\nprime 관점 질문 파악\nSTRATEGY:\nprime 계획\nEXECUTION:\nprime 단계별 풀이\nCONCLUSION:\nprime 결과\nUNCERTAINTIES:\n없음",
                    "UNDERSTANDING:\nlogic 관점 질문 파악\nSTRATEGY:\nlogic 계획\nEXECUTION:\nlogic 단계별 풀이\nCONCLUSION:\nlogic 결과\nUNCERTAINTIES:\n없음",
                    "UNDERSTANDING:\npattern 관점 질문 파악\nSTRATEGY:\npattern 계획\nEXECUTION:\npattern 단계별 풀이\nCONCLUSION:\npattern 결과\nUNCERTAINTIES:\n없음",
                    "UNDERSTANDING:\nforge 관점 질문 파악\nSTRATEGY:\nforge 계획\nEXECUTION:\nforge 단계별 풀이\nCONCLUSION:\nforge 결과\nUNCERTAINTIES:\n없음",
                    "UNDERSTANDING:\nraven 관점 질문 파악\nSTRATEGY:\nraven 계획\nEXECUTION:\nraven 단계별 풀이\nCONCLUSION:\nraven 결과\nUNCERTAINTIES:\n없음",
                    "UNDERSTANDING:\n통합 질문 파악\nSTRATEGY:\n통합 계획\nEXECUTION:\n통합 단계별 풀이\nCONCLUSION:\n통합 최종 결과\nUNCERTAINTIES:\n없음",
                ]
            ),
            FakeClient(
                [
                    '{"verdict":"VALID","first_fatal_error":"","missing_assumptions":[],"invalid_steps":[],"valid_steps":["ok"],"repair_possible":true,"confidence":0.8,"final_status":"VALID"}'
                ]
            ),
        ]

        progress_events: list[tuple[str, dict[str, str]]] = []

        result = run_research_lab(
            "Prove something about primes.",
            base_dir="mystic_data",
            progress_callback=lambda stage, payload: progress_events.append((stage, payload)),
        )
        self.assertEqual(result.specialist, "prime")
        self.assertIn("prime", result.participating_specialists)
        self.assertIn("raven", result.participating_specialists)
        self.assertEqual(result.critic_verdict, "VALID")
        self.assertIn("결론", result.final_answer)
        self.assertEqual(
            [stage for stage, _ in progress_events],
            [
                "routing_complete",
                "specialist_complete",
                "specialist_complete",
                "specialist_complete",
                "specialist_complete",
                "specialist_complete",
                "synthesis_complete",
                "critique_complete",
                "final_answer_ready",
            ],
        )


if __name__ == "__main__":
    unittest.main()

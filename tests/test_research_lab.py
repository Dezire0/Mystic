from __future__ import annotations

import unittest
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
            dataset_progress_text="3/19 datasets",
            status_detail="OpenMathInstruct-2",
            progress_reason="현재 로컬 학습 기준",
        )
        snapshot_loader.return_value = {"experts": [expert]}
        defaults_loader.return_value = {
            "backend": "ollama",
            "generator_model": "qwen2.5:7b",
            "raven_model": "qwen2.5:7b",
            "active_raven_backend": "ollama",
        }
        client_builder.side_effect = [
            FakeClient(
                [
                    '{"specialist":"prime","reason":"number theory","strategy":"break problem down"}',
                    "UNDERSTANDING:\nquestion\nSTRATEGY:\nplan\nEXECUTION:\nsteps\nCONCLUSION:\nresult\nUNCERTAINTIES:\nnone",
                ]
            ),
            FakeClient(
                [
                    '{"verdict":"VALID","first_fatal_error":"","missing_assumptions":[],"invalid_steps":[],"valid_steps":["ok"],"repair_possible":true,"confidence":0.8,"final_status":"VALID"}'
                ]
            ),
        ]

        result = run_research_lab("Prove something about primes.", base_dir="mystic_data")
        self.assertEqual(result.specialist, "prime")
        self.assertEqual(result.critic_verdict, "VALID")
        self.assertIn("결론", result.final_answer)


if __name__ == "__main__":
    unittest.main()

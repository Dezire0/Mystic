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
            plan=type(
                "Plan",
                (),
                {
                    "specialist": "prime",
                    "support_specialists": ["logic"],
                    "strategy": "s",
                    "critic_summary": "critic",
                    "task_assignments": [],
                },
            )(),
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
                    '{"strategy":"정수 조건을 먼저 제한하고 분기별로 닫는다","phases":["범위 제한","경우 분기","검산 및 완전성 확인"],"execution_mode":"full","selected_count_cap":5,"debate_rounds":1,"require_revision":true,"early_stop_if_closed":false}',
                    '{"summary":"라우팅은 괜찮지만 단계 분해가 약하다","findings":["초기 계획만으로는 완전성 보장이 약함"],"revision":"분류 후 specialist별 태스크를 재분배한다"}',
                    '{"summary":"빠질 수 있는 경우가 있다","findings":["경계 사례 분류 필요"],"revision":"모든 경우를 분류하도록 태스크를 배분한다"}',
                    '{"summary":"반례 공격이 필요하다","findings":["잘못된 후보를 빠르게 솎아야 함"],"revision":"Forge와 Raven을 통해 반례와 검산을 병행한다"}',
                    '{"summary":"중복 계산을 줄여야 한다","findings":["각 specialist는 자기 파트만 맡아야 함"],"revision":"중복 없이 역할을 나눈 뒤 마지막에 통합한다"}',
                    '{"method_summary":"prime은 정수 조건과 구조를 분해한다","task_candidate":"x의 범위와 정수 조건을 제한한다","dependencies":["logic"],"deliverable":"정수 조건 분류"}',
                    '{"method_summary":"logic은 경우 분류의 누락을 공격한다","task_candidate":"분기 구조를 검토한다","dependencies":["prime"],"deliverable":"누락 없는 케이스 구조"}',
                    '{"method_summary":"pattern은 후보 패턴을 정리한다","task_candidate":"해 패턴 후보를 추린다","dependencies":["prime"],"deliverable":"후보 패턴 목록"}',
                    '{"method_summary":"forge는 작은 경우를 검산한다","task_candidate":"후보를 빠르게 검산한다","dependencies":["pattern"],"deliverable":"검산 로그"}',
                    '{"method_summary":"raven은 최종 허점을 찾는다","task_candidate":"최종 진술을 검증한다","dependencies":["logic","forge"],"deliverable":"최종 검증 메모"}',
                    '{"combined_strategy":"정수 범위 제한, 경우 분류, 패턴 추출, 검산, 최종 검증 순서로 간다","handoff_notes":["prime 이후 logic","pattern 이후 forge"],"task_assignments":[{"agent":"prime","task":"x의 범위 제한과 초기 정수 조건 정리","deliverable":"가능한 x 범위"},{"agent":"logic","task":"경우 분류 누락 여부 점검","deliverable":"케이스 분류표"},{"agent":"pattern","task":"후보 패턴 정리","deliverable":"후보 패턴 목록"},{"agent":"forge","task":"후보 직접 검산","deliverable":"검산 로그"},{"agent":"raven","task":"최종 답안 보수 검증","deliverable":"최종 검증 메모"}]}',
                    "UNDERSTANDING:\nprime 이해\nSTRATEGY:\nprime 전략\nEXECUTION:\nprime 실행\nCONCLUSION:\nprime 결론\nUNCERTAINTIES:\n없음",
                    "UNDERSTANDING:\nlogic 이해\nSTRATEGY:\nlogic 전략\nEXECUTION:\nlogic 실행\nCONCLUSION:\nlogic 결론\nUNCERTAINTIES:\n없음",
                    "UNDERSTANDING:\npattern 이해\nSTRATEGY:\npattern 전략\nEXECUTION:\npattern 실행\nCONCLUSION:\npattern 결론\nUNCERTAINTIES:\n없음",
                    "UNDERSTANDING:\nforge 이해\nSTRATEGY:\nforge 전략\nEXECUTION:\nforge 실행\nCONCLUSION:\nforge 결론\nUNCERTAINTIES:\n없음",
                    "UNDERSTANDING:\nraven 이해\nSTRATEGY:\nraven 전략\nEXECUTION:\nraven 실행\nCONCLUSION:\nraven 결론\nUNCERTAINTIES:\n없음",
                    '{"objection":"prime 결과에 예외 검토가 약하다","risk":"경계 사례 누락","requested_fix":"x=2,3 이후 불가능성을 명시하라"}',
                    '{"objection":"prime이 패턴 목록 연결을 덜 했다","risk":"후속 패턴화가 느려짐","requested_fix":"핵심 후보 구조를 함께 넘겨라"}',
                    '{"objection":"prime 검산 포인트를 더 줘야 한다","risk":"후속 검산 누락","requested_fix":"직접 대입 후보를 명시하라"}',
                    '{"objection":"prime 최종 진술이 아직 거칠다","risk":"보수 검증 약화","requested_fix":"불가능 케이스 근거를 더 써라"}',
                    '{"objection":"logic은 prime 가정을 더 엄밀히 써야 한다","risk":"케이스 분류 흔들림","requested_fix":"정렬 조건을 앞에 고정하라"}',
                    '{"objection":"logic은 패턴과 연결이 약하다","risk":"후보 패턴 생략","requested_fix":"각 케이스별 패턴 결과를 붙여라"}',
                    '{"objection":"logic은 검산 단계 handoff가 부족하다","risk":"검산 대상 누락","requested_fix":"검산 대상 후보를 표로 정리하라"}',
                    '{"objection":"logic은 최종 진술 조건을 더 써야 한다","risk":"완전성 약화","requested_fix":"불가능한 분기를 명시하라"}',
                    '{"objection":"pattern은 prime 범위를 더 반영해야 한다","risk":"가짜 후보 포함","requested_fix":"x 범위 조건을 앞에 적어라"}',
                    '{"objection":"pattern은 logic 분류를 더 존중해야 한다","risk":"중복 후보 발생","requested_fix":"케이스별 후보만 남겨라"}',
                    '{"objection":"pattern은 검산 우선순위를 줘야 한다","risk":"forge 효율 저하","requested_fix":"유력 후보부터 정렬하라"}',
                    '{"objection":"pattern은 최종 진술이 아니다","risk":"후보와 정답 혼동","requested_fix":"후보 단계임을 명시하라"}',
                    '{"objection":"forge는 prime 조건을 보존해야 한다","risk":"순서 조건 누락","requested_fix":"정렬 조건과 함께 검산하라"}',
                    '{"objection":"forge는 logic 분기표와 연결해야 한다","risk":"검산 로그 해석 어려움","requested_fix":"각 로그에 분기 태그를 붙여라"}',
                    '{"objection":"forge는 pattern 후보 전부를 커버해야 한다","risk":"일부 후보 미검산","requested_fix":"모든 후보를 순회하라"}',
                    '{"objection":"forge는 최종 진술 전에 결과를 정리해야 한다","risk":"Raven 확인 어려움","requested_fix":"성공/실패 후보를 분리하라"}',
                    '{"objection":"raven은 prime 근거를 더 집어야 한다","risk":"오탐 가능성","requested_fix":"범위 제한 근거를 재확인하라"}',
                    '{"objection":"raven은 logic 분류 체크리스트를 가져와라","risk":"완전성 판단 흔들림","requested_fix":"분기 누락 여부를 명시하라"}',
                    '{"objection":"raven은 pattern 후보 표를 같이 봐야 한다","risk":"후보 누락 탐지 실패","requested_fix":"후보 표 기준으로 검증하라"}',
                    '{"objection":"raven은 forge 로그를 요약해야 한다","risk":"최종 판정 근거 약함","requested_fix":"검산 성공/실패를 요약하라"}',
                    "UNDERSTANDING:\nprime 수정 이해\nSTRATEGY:\nprime 수정 전략\nEXECUTION:\nprime 수정 실행\nCONCLUSION:\nprime 수정 결론\nUNCERTAINTIES:\n없음",
                    "UNDERSTANDING:\nlogic 수정 이해\nSTRATEGY:\nlogic 수정 전략\nEXECUTION:\nlogic 수정 실행\nCONCLUSION:\nlogic 수정 결론\nUNCERTAINTIES:\n없음",
                    "UNDERSTANDING:\npattern 수정 이해\nSTRATEGY:\npattern 수정 전략\nEXECUTION:\npattern 수정 실행\nCONCLUSION:\npattern 수정 결론\nUNCERTAINTIES:\n없음",
                    "UNDERSTANDING:\nforge 수정 이해\nSTRATEGY:\nforge 수정 전략\nEXECUTION:\nforge 수정 실행\nCONCLUSION:\nforge 수정 결론\nUNCERTAINTIES:\n없음",
                    "UNDERSTANDING:\nraven 수정 이해\nSTRATEGY:\nraven 수정 전략\nEXECUTION:\nraven 수정 실행\nCONCLUSION:\nraven 수정 결론\nUNCERTAINTIES:\n없음",
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
        self.assertIn("mode=full", result.final_answer)
        self.assertEqual(
            [stage for stage, _ in progress_events],
            [
                "routing_complete",
                "planning_complete",
                "plan_critic_complete",
                "completeness_critic_complete",
                "counterexample_critic_complete",
                "cost_latency_critic_complete",
                "method_proposal_complete",
                "method_proposal_complete",
                "method_proposal_complete",
                "method_proposal_complete",
                "method_proposal_complete",
                "task_assignment_complete",
                "task_execution_complete",
                "task_execution_complete",
                "task_execution_complete",
                "task_execution_complete",
                "task_execution_complete",
                "debate_objection_complete",
                "debate_objection_complete",
                "debate_objection_complete",
                "debate_objection_complete",
                "debate_objection_complete",
                "debate_objection_complete",
                "debate_objection_complete",
                "debate_objection_complete",
                "debate_objection_complete",
                "debate_objection_complete",
                "debate_objection_complete",
                "debate_objection_complete",
                "debate_objection_complete",
                "debate_objection_complete",
                "debate_objection_complete",
                "debate_objection_complete",
                "debate_objection_complete",
                "debate_objection_complete",
                "debate_objection_complete",
                "debate_objection_complete",
                "revision_complete",
                "revision_complete",
                "revision_complete",
                "revision_complete",
                "revision_complete",
                "synthesis_complete",
                "critique_complete",
                "final_answer_ready",
            ],
        )

    @patch("mystic.research_lab.load_model_defaults")
    @patch("mystic.research_lab.build_client")
    @patch("mystic.research_lab.load_dashboard_snapshot")
    def test_run_research_lab_can_early_stop_after_closed_executions(self, snapshot_loader, client_builder, defaults_loader):
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
                    '{"specialist":"prime","reason":"정수론 문제","strategy":"범위를 제한한다"}',
                    '{"strategy":"작게 닫힌 분기만 확인한다","phases":["범위 제한","케이스 정리"],"execution_mode":"fast","selected_count_cap":2,"debate_rounds":1,"require_revision":true,"early_stop_if_closed":true}',
                    '{"summary":"좋다","findings":[],"revision":"작게 닫힌 분기를 유지한다"}',
                    '{"summary":"누락 없음","findings":[],"revision":"작게 닫힌 분기를 유지한다"}',
                    '{"summary":"반례 위험 낮음","findings":[],"revision":"작게 닫힌 분기를 유지한다"}',
                    '{"summary":"빠르게 끝낼 수 있다","findings":[],"revision":"작게 닫힌 분기를 유지한다"}',
                    '{"method_summary":"prime은 범위를 닫는다","task_candidate":"x 범위 제한","dependencies":[],"deliverable":"범위 결론"}',
                    '{"method_summary":"logic은 완전성만 체크한다","task_candidate":"분기 누락 점검","dependencies":["prime"],"deliverable":"완전성 메모"}',
                    '{"combined_strategy":"prime과 logic만으로 닫는다","handoff_notes":[],"task_assignments":[{"agent":"prime","task":"x 범위 제한","deliverable":"범위 결론"},{"agent":"logic","task":"분기 누락 점검","deliverable":"완전성 메모"}]}',
                    "UNDERSTANDING:\nprime 이해\nSTRATEGY:\n닫힌 전략\nEXECUTION:\n범위를 제한했다\nCONCLUSION:\nprime 결론 완성\nUNCERTAINTIES:\n없음",
                    "UNDERSTANDING:\nlogic 이해\nSTRATEGY:\n완전성 점검 전략\nEXECUTION:\n누락을 확인했다\nCONCLUSION:\nlogic 결론 완성\nUNCERTAINTIES:\n없음",
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
            "Classify the finite cases.",
            base_dir="mystic_data",
            progress_callback=lambda stage, payload: progress_events.append((stage, payload)),
        )

        self.assertEqual(result.participating_specialists, ["prime", "logic"])
        self.assertIn("early_stop=yes", result.final_answer)
        stages = [stage for stage, _ in progress_events]
        self.assertIn("early_stop_triggered", stages)
        self.assertNotIn("debate_objection_complete", stages)
        self.assertNotIn("revision_complete", stages)


if __name__ == "__main__":
    unittest.main()

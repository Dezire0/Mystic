from __future__ import annotations

import unittest

from mystic.app.pages import (
    DebateSessionPage,
    ResearchTableSessionPage,
    ResearchTableStartPage,
    TeacherLabelsPage,
)


class AppPagesTests(unittest.TestCase):
    def test_start_page_shows_participant_selector_and_auth_guidance(self):
        html = ResearchTableStartPage(
            participants=[
                {
                    "model_id": "local_prime",
                    "label": "Local DeepSeek-R1-Distill-14B",
                    "provider": "ollama",
                    "model_name": "deepseek-r1-distill-14b",
                    "roles": ["draft", "revise"],
                    "auth_state": "ready",
                    "checked": True,
                },
                {
                    "model_id": "gemini_cli",
                    "label": "Gemini CLI",
                    "provider": "cli",
                    "model_name": "gemini_cli",
                    "roles": ["draft", "critique"],
                    "auth_state": "not_authenticated",
                    "checked": False,
                },
            ],
            auth_cards=["Gemini CLI is not authenticated. Login with Google."],
        )
        self.assertIn("ResearchTableStartPage", html)
        self.assertIn("Local DeepSeek-R1-Distill-14B", html)
        self.assertIn("Gemini CLI", html)
        self.assertIn("Login with Google", html)

    def test_research_table_page_renders_discoveries_and_metadata(self):
        html = ResearchTableSessionPage(
            session={
                "problem": "Test problem",
                "turns": [
                    {
                        "round_index": 1,
                        "phase": "independent_discovery",
                        "speaker_type": "model",
                        "speaker_id": "local_prime",
                        "provider": "ollama",
                        "model_name": "deepseek-r1-distill-14b",
                        "role": "solver",
                        "status": "DRAFT_ONLY",
                        "content": "Discovery draft",
                        "reply_to": [],
                    },
                    {
                        "round_index": 2,
                        "phase": "tool_verification",
                        "speaker_type": "tool",
                        "speaker_id": "mystic_verify_answer",
                        "provider": "tool",
                        "model_name": "deterministic_verifier",
                        "role": "verifier",
                        "status": "VERIFICATION_RESULT",
                        "content": "Verifier refuted the claim.",
                        "reply_to": ["turn-1"],
                    },
                ],
                "discoveries": [
                    {
                        "claim": "A useful invariant appears.",
                        "rationale": "Observed in round 1.",
                        "confidence": "medium",
                        "needs_verification": True,
                        "status": "proposed",
                        "type": "invariant",
                    }
                ],
                "verification_requests": [{"tool": "brute_force", "status": "pending", "question": "Check invariant"}],
                "rejected_discoveries": [],
                "final_synthesis_package": {"final_verdict": "UNKNOWN"},
            }
        )
        self.assertIn("deepseek-r1-distill-14b", html)
        self.assertIn("deterministic_verifier", html)
        self.assertIn("New Discovery", html)
        self.assertIn("Needs Verification", html)

    def test_debate_page_renders_threading_and_tool_evidence(self):
        html = DebateSessionPage(
            session={
                "problem": "Debate problem",
                "turns": [
                    {
                        "round_index": 1,
                        "phase": "parallel_draft",
                        "speaker_type": "model",
                        "speaker_id": "local_qwen",
                        "provider": "ollama",
                        "model_name": "qwen3-14b",
                        "role": "solver",
                        "status": "DRAFT_ONLY",
                        "content": "Initial draft",
                        "reply_to": [],
                    },
                    {
                        "round_index": 2,
                        "phase": "cross_critique",
                        "speaker_type": "model",
                        "speaker_id": "local_raven",
                        "provider": "local_adapter",
                        "model_name": "Qwen/Qwen2.5-0.5B-Instruct + raven_lora_v0",
                        "role": "critic",
                        "status": "CRITIQUE_ONLY",
                        "content": "This misses a case.",
                        "reply_to": ["turn-a"],
                    },
                ],
                "final_package": "Final judgment",
            }
        )
        self.assertIn("Replies to", html)
        self.assertIn("This misses a case.", html)
        self.assertIn("Final Judge", html)

    def test_teacher_labels_page_lists_packets_and_labels(self):
        html = TeacherLabelsPage(
            packets=[{"packet_id": "packet-1", "target_agent": "raven", "cases": [1, 2]}],
            labels=[{"label_id": "label-1", "target_agent": "raven", "source_model": "gpt_controller", "label": {"verdict": "INVALID"}}],
        )
        self.assertIn("packet-1", html)
        self.assertIn("label-1", html)
        self.assertIn("INVALID", html)


if __name__ == "__main__":
    unittest.main()

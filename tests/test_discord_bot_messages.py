from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scripts.run_discord_bot import is_dm_message, normalize_message_question, progress_message_chunks, stage_title


class DiscordBotMessageTests(unittest.TestCase):
    def test_stage_title_maps_new_multi_critic_and_debate_stages(self):
        self.assertEqual(stage_title("planning_complete"), "3. Core 초기 계획 완료")
        self.assertEqual(stage_title("completeness_critic_complete"), "4-2. Completeness Critic 완료")
        self.assertEqual(stage_title("debate_objection_complete"), "8. selected specialist objection")

    def test_progress_message_chunks_expands_lines(self):
        messages = progress_message_chunks(
            "task_assignment_complete",
            {
                "lines": [
                    "Core 재배분 전략: 역할을 나눔",
                    "Mystic-Prime 담당: 범위 제한",
                    "Mystic-Forge 담당: 검산",
                ]
            },
        )
        self.assertEqual(messages[0], "6. Core 태스크 배분 완료")
        self.assertIn("Mystic-Prime 담당: 범위 제한", messages)

    def test_normalize_message_question_keeps_dm_text(self):
        self.assertEqual(
            normalize_message_question(content="  prove fermat little theorem  ", bot_user_id=42, is_dm=True),
            "prove fermat little theorem",
        )

    def test_normalize_message_question_strips_bot_mentions(self):
        self.assertEqual(
            normalize_message_question(content="<@42> solve x^2=4", bot_user_id=42, is_dm=False),
            "solve x^2=4",
        )
        self.assertEqual(
            normalize_message_question(content="<@!42>   check this proof", bot_user_id=42, is_dm=False),
            "check this proof",
        )

    def test_normalize_message_question_returns_empty_when_only_mention(self):
        self.assertEqual(normalize_message_question(content="<@42>", bot_user_id=42, is_dm=False), "")

    def test_is_dm_message_uses_dm_channel_type(self):
        class FakeDMChannel:
            pass

        with patch("scripts.run_discord_bot.discord.DMChannel", FakeDMChannel):
            message = SimpleNamespace(channel=FakeDMChannel())
            self.assertTrue(is_dm_message(message))


if __name__ == "__main__":
    unittest.main()

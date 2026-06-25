from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scripts.run_discord_bot import is_dm_message, normalize_message_question


class DiscordBotMessageTests(unittest.TestCase):
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

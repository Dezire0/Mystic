from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.manage_discord_bot_service import daemon_command, plist_payload


class ManageDiscordBotServiceTests(unittest.TestCase):
    def test_daemon_command_uses_discord_venv_and_optional_guild(self):
        args = argparse.Namespace(
            base_dir="/tmp/mystic_data",
            token_env="MYSTIC_DISCORD_TOKEN",
            guild_id=123456789,
        )
        with patch("scripts.manage_discord_bot_service.ROOT", Path("/repo")), patch(
            "scripts.manage_discord_bot_service.PYTHON_BIN",
            Path("/repo/.venv-discord/bin/python"),
        ):
            command = daemon_command(args)
        self.assertEqual(command[0], "/repo/.venv-discord/bin/python")
        self.assertIn("--guild-id", command)
        self.assertIn("123456789", command)

    def test_plist_payload_writes_expected_logs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            args = argparse.Namespace(
                base_dir=temp_dir,
                token_env="MYSTIC_DISCORD_TOKEN",
                guild_id=0,
            )
            with patch("scripts.manage_discord_bot_service.ROOT", Path("/repo")), patch(
                "scripts.manage_discord_bot_service.PYTHON_BIN",
                Path("/repo/.venv-discord/bin/python"),
            ):
                payload = plist_payload(args)
            self.assertEqual(payload["Label"], "com.mystic.discord-bot")
            self.assertTrue(payload["StandardOutPath"].endswith("discord_bot.launchd.stdout.log"))
            self.assertEqual(payload["EnvironmentVariables"]["PYTHONUNBUFFERED"], "1")


if __name__ == "__main__":
    unittest.main()

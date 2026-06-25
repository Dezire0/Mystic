from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from mystic.env_loader import load_dotenv_file


class EnvLoaderTests(unittest.TestCase):
    def test_load_dotenv_file_sets_missing_keys(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "MYSTIC_DISCORD_TOKEN=test-token\nMYSTIC_DISCORD_GUILD_ID=12345\n",
                encoding="utf-8",
            )
            os.environ.pop("MYSTIC_DISCORD_TOKEN", None)
            os.environ.pop("MYSTIC_DISCORD_GUILD_ID", None)

            loaded = load_dotenv_file(env_path)

            self.assertEqual(loaded["MYSTIC_DISCORD_TOKEN"], "test-token")
            self.assertEqual(os.environ["MYSTIC_DISCORD_GUILD_ID"], "12345")

    def test_load_dotenv_file_does_not_override_existing_by_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text("MYSTIC_DISCORD_TOKEN=file-token\n", encoding="utf-8")
            os.environ["MYSTIC_DISCORD_TOKEN"] = "shell-token"

            loaded = load_dotenv_file(env_path, override=False)

            self.assertEqual(loaded, {})
            self.assertEqual(os.environ["MYSTIC_DISCORD_TOKEN"], "shell-token")


if __name__ == "__main__":
    unittest.main()

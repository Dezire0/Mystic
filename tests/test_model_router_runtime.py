from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mystic.models.router import ModelRouter


TEST_CONFIG = """
models:
  local_prime:
    provider: mock
    model: mock-prime
    role_defaults:
      - draft
  local_raven:
    provider: local_adapter
    base_model: Qwen/Test
    adapter_path: ADAPTER_PATH
    role_defaults:
      - critique
  gemini_cli:
    provider: cli
    command: gemini
    auth: google_login
    role_defaults:
      - draft
  claude_cli:
    provider: cli
    command: claude
    auth: claude_login
    role_defaults:
      - critique
policy:
  max_models_per_compare: 2
  timeout_per_model_seconds: 5
"""


class ModelRouterRuntimeTests(unittest.TestCase):
    def test_router_returns_mock_model_output_with_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            adapter_dir = root / "mystic_data" / "adapters" / "raven_lora_v0"
            adapter_dir.mkdir(parents=True)
            config_path = root / "models.yaml"
            config_path.write_text(
                TEST_CONFIG.replace("ADAPTER_PATH", str(adapter_dir)),
                encoding="utf-8",
            )
            router = ModelRouter(root_path=root, config_path=config_path)
            result = router.call_model(
                model_id="local_prime",
                role="draft",
                task="Draft a solution",
                problem="x + y = 5",
            )
            self.assertEqual(result["provider"], "mock")
            self.assertEqual(result["model_name"], "mock-prime")
            self.assertEqual(result["status"], "DRAFT_ONLY")
            self.assertTrue(Path(result["artifact_path"]).exists())

    def test_router_reports_cli_auth_required_when_login_marker_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            adapter_dir = root / "mystic_data" / "adapters" / "raven_lora_v0"
            adapter_dir.mkdir(parents=True)
            config_path = root / "models.yaml"
            config_path.write_text(
                TEST_CONFIG.replace("ADAPTER_PATH", str(adapter_dir)),
                encoding="utf-8",
            )
            router = ModelRouter(root_path=root, config_path=config_path)
            with patch("mystic.models.providers.base.shutil.which", return_value="/usr/bin/gemini"), patch(
                "mystic.models.providers.cli_provider.run_command",
                return_value=(1, "", "Login with Google", 0.01),
            ):
                status = router.status_snapshot()["gemini_cli"]["status"]
            self.assertEqual(status["state"], "not_authenticated")
            self.assertIn("Login with Google", status["message"])

    def test_router_reports_missing_cli_provider(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            adapter_dir = root / "mystic_data" / "adapters" / "raven_lora_v0"
            adapter_dir.mkdir(parents=True)
            config_path = root / "models.yaml"
            config_path.write_text(
                TEST_CONFIG.replace("ADAPTER_PATH", str(adapter_dir)),
                encoding="utf-8",
            )
            router = ModelRouter(root_path=root, config_path=config_path)
            with patch("mystic.models.providers.base.shutil.which", return_value=None):
                status = router.status_snapshot()["gemini_cli"]["status"]
            self.assertEqual(status["state"], "missing")
            self.assertFalse(status["available"])

    def test_router_call_model_returns_auth_required_for_logged_out_cli(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            adapter_dir = root / "mystic_data" / "adapters" / "raven_lora_v0"
            adapter_dir.mkdir(parents=True)
            config_path = root / "models.yaml"
            config_path.write_text(
                TEST_CONFIG.replace("ADAPTER_PATH", str(adapter_dir)),
                encoding="utf-8",
            )
            router = ModelRouter(root_path=root, config_path=config_path)
            with patch("mystic.models.providers.base.shutil.which", return_value="/usr/bin/gemini"), patch(
                "mystic.models.providers.cli_provider.run_command",
                return_value=(1, "", "not authenticated", 0.01),
            ):
                result = router.call_model(
                    model_id="gemini_cli",
                    role="draft",
                    task="Draft",
                    problem="x + y = 5",
                )
            self.assertEqual(result["status"], "AUTH_REQUIRED")
            self.assertIn("Login with Google", result["auth_message"])

    def test_router_call_model_returns_authenticated_cli_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            adapter_dir = root / "mystic_data" / "adapters" / "raven_lora_v0"
            adapter_dir.mkdir(parents=True)
            config_path = root / "models.yaml"
            config_path.write_text(
                TEST_CONFIG.replace("ADAPTER_PATH", str(adapter_dir)),
                encoding="utf-8",
            )
            router = ModelRouter(root_path=root, config_path=config_path)
            with patch("mystic.models.providers.base.shutil.which", return_value="/usr/bin/claude"), patch(
                "mystic.models.providers.cli_provider.run_command",
                side_effect=[
                    (0, '{"status":"authenticated"}', "", 0.01),
                    (0, '{"content":[{"text":"Claude response"}]}', "", 0.02),
                ],
            ):
                result = router.call_model(
                    model_id="claude_cli",
                    role="critique",
                    task="Critique",
                    problem="x + y = 5",
                )
            self.assertEqual(result["status"], "CRITIQUE_ONLY")
            self.assertEqual(result["provider"], "cli")
            self.assertIn("Claude response", result["content"])

    def test_router_reports_local_adapter_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            adapter_dir = root / "mystic_data" / "adapters" / "raven_lora_v0"
            adapter_dir.mkdir(parents=True)
            config_path = root / "models.yaml"
            config_path.write_text(
                TEST_CONFIG.replace("ADAPTER_PATH", str(adapter_dir)),
                encoding="utf-8",
            )
            router = ModelRouter(root_path=root, config_path=config_path)
            status = router.status_snapshot()["local_raven"]
            self.assertEqual(status["provider"], "local_adapter")
            self.assertEqual(status["status"]["state"], "ready")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from scripts import mystic_gemini_cli_bridge as bridge


class GeminiCliBridgeTests(unittest.TestCase):
    def test_detects_prompt_flag_from_help(self) -> None:
        with (
            patch.object(bridge, "resolve_binary", return_value="/usr/local/bin/gemini"),
            patch.object(
                bridge.subprocess,
                "run",
                return_value=subprocess.CompletedProcess(["gemini", "--help"], 0, "Use --prompt for headless mode.", ""),
            ),
        ):
            command, detection = bridge.detect_command()
        self.assertEqual(detection, "--prompt")
        self.assertEqual(command, bridge.GeminiCommand("/usr/local/bin/gemini", ("--prompt", "{prompt}")))

    def test_override_template_rejects_workspace_or_auto_approval_flags(self) -> None:
        with patch.dict("os.environ", {"MYSTIC_GEMINI_CLI_ARGS_TEMPLATE": "--yolo --prompt {prompt}"}, clear=False):
            self.assertIsNone(bridge.parse_override_template("--yolo --prompt {prompt}"))

    def test_normalizes_output_without_returning_stderr(self) -> None:
        calls: list[tuple[list[str], dict[str, object]]] = []

        def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            calls.append((command, kwargs))
            if command[-1] == "--help":
                return subprocess.CompletedProcess(command, 0, "--prompt", "")
            return subprocess.CompletedProcess(command, 0, "mystic-gemini-cli-ok\n", "private diagnostic")

        with (
            patch.object(bridge, "resolve_binary", return_value="/usr/local/bin/gemini"),
            patch.object(bridge.subprocess, "run", side_effect=fake_run),
        ):
            result = bridge.run_bridge("Reply with exactly: mystic-gemini-cli-ok")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["output"], "mystic-gemini-cli-ok")
        self.assertEqual(result["safe_error"], "")
        self.assertEqual(calls[1][0], ["/usr/local/bin/gemini", "--prompt", "Reply with exactly: mystic-gemini-cli-ok"])
        self.assertNotIn("private diagnostic", str(result))

    def test_timeout_returns_safe_error(self) -> None:
        def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            if command[-1] == "--help":
                return subprocess.CompletedProcess(command, 0, "--prompt", "")
            raise subprocess.TimeoutExpired(command, 5)

        with (
            patch.object(bridge, "resolve_binary", return_value="/usr/local/bin/gemini"),
            patch.object(bridge.subprocess, "run", side_effect=fake_run),
        ):
            result = bridge.run_bridge("ping", timeout_seconds=5)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["safe_error"], "Gemini CLI request timed out.")

    def test_authentication_prompt_returns_local_login_requirement(self) -> None:
        def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            if command[-1] == "--help":
                return subprocess.CompletedProcess(command, 0, "--prompt", "")
            return subprocess.CompletedProcess(command, 0, "Opening authentication page in your browser.", "")

        with (
            patch.object(bridge, "resolve_binary", return_value="/usr/local/bin/gemini"),
            patch.object(bridge.subprocess, "run", side_effect=fake_run),
        ):
            result = bridge.run_bridge("ping")
        self.assertEqual(result["status"], "error")
        self.assertIn("local Google login", result["safe_error"])

    def test_sanitizes_local_paths_and_tokens_from_failures(self) -> None:
        def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            if command[-1] == "--help":
                return subprocess.CompletedProcess(command, 0, "--prompt", "")
            return subprocess.CompletedProcess(command, 1, "", "failed at /Users/example/.gemini token=private-value")

        with (
            patch.object(bridge, "resolve_binary", return_value="/usr/local/bin/gemini"),
            patch.object(bridge.subprocess, "run", side_effect=fake_run),
        ):
            result = bridge.run_bridge("ping")
        self.assertEqual(result["status"], "error")
        self.assertNotIn("/Users/example", result["safe_error"])
        self.assertNotIn("private-value", result["safe_error"])

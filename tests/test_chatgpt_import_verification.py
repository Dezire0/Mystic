from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from mystic.mcp.import_verification import (
    REQUIRED_TOOLS,
    artifact_contains_secret_like_fields,
    default_verification_artifact_path,
    load_import_verification,
    summarize_import_verification,
    validate_import_verification_artifact,
)
from scripts import create_chatgpt_import_verification_artifact as artifact_cli


def _valid_artifact(public_endpoint: str) -> dict[str, object]:
    return {
        "artifact_version": 1,
        "verified_at": "2026-07-02T09:17:49+00:00",
        "verified_by": "manual",
        "public_endpoint": public_endpoint,
        "mcp_endpoint": f"{public_endpoint}/mcp",
        "chatgpt_developer_mode_imported": True,
        "oauth_flow_completed": True,
        "tools_list_visible_in_chatgpt": True,
        "required_tools_visible": list(REQUIRED_TOOLS),
        "manual_tool_call_results": {tool: "passed" for tool in REQUIRED_TOOLS},
        "notes": "No secrets. No tokens. Manual verification only.",
    }


class ChatGPTImportVerificationTests(unittest.TestCase):
    def test_default_verification_path(self) -> None:
        self.assertTrue(
            str(default_verification_artifact_path("/tmp/mystic-root")).endswith(
                "mystic_data/e2e/chatgpt_remote_mcp_import/verification.json"
            )
        )

    def test_valid_artifact_validates(self) -> None:
        data = _valid_artifact("https://mystic.dexproject.workers.dev")
        validation = validate_import_verification_artifact(data, public_endpoint="https://mystic.dexproject.workers.dev")
        self.assertTrue(validation["valid"])
        self.assertTrue(validation["verified"])
        self.assertFalse(validation["errors"])

    def test_secret_like_fields_fail_validation(self) -> None:
        data = _valid_artifact("https://mystic.dexproject.workers.dev")
        data["access_token"] = "redacted"
        self.assertTrue(artifact_contains_secret_like_fields(data))
        validation = validate_import_verification_artifact(data, public_endpoint="https://mystic.dexproject.workers.dev")
        self.assertFalse(validation["valid"])
        self.assertFalse(validation["verified"])

    def test_load_and_summarize_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_path = Path(temp_dir) / "verification.json"
            artifact_path.write_text(json.dumps(_valid_artifact("https://mystic.dexproject.workers.dev")), encoding="utf-8")
            loaded = load_import_verification(artifact_path)
            self.assertIsNotNone(loaded)
            summary = summarize_import_verification(loaded)
            self.assertEqual(summary["verified_by"], "manual")
            self.assertEqual(summary["required_tools_visible"], list(REQUIRED_TOOLS))
            self.assertNotIn("notes", summary)

    def test_artifact_helper_refuses_without_confirmations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            exit_code = artifact_cli.main(
                [
                    "--root-path",
                    temp_dir,
                    "--public-endpoint",
                    "https://mystic.dexproject.workers.dev",
                ]
            )
        self.assertNotEqual(exit_code, 0)

    def test_artifact_helper_creates_valid_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "artifact.json"
            exit_code = artifact_cli.main(
                [
                    "--root-path",
                    temp_dir,
                    "--public-endpoint",
                    "https://mystic.dexproject.workers.dev",
                    "--output",
                    str(output_path),
                    "--confirm-imported",
                    "--confirm-oauth-flow",
                    "--confirm-tools-visible",
                    "--confirm-tool-calls-passed",
                ]
            )
            self.assertEqual(exit_code, 0)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertFalse(artifact_contains_secret_like_fields(payload))
            validation = validate_import_verification_artifact(
                payload,
                public_endpoint="https://mystic.dexproject.workers.dev",
            )
            self.assertTrue(validation["verified"])


if __name__ == "__main__":
    unittest.main()

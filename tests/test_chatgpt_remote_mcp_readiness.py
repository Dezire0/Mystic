from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch

from scripts import check_chatgpt_remote_mcp_readiness as readiness


def _mcp_success(request_id: int, result: dict[str, object]) -> dict[str, object]:
    return {"status": 200, "headers": {}, "body": {"jsonrpc": "2.0", "id": request_id, "result": result}}


class ChatGPTRemoteMCPReadinessTests(unittest.TestCase):
    def test_readiness_reports_oauth_blocker_when_mcp_is_otherwise_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = readiness.Path(temp_dir) / "readiness.json"

            def fake_http_json_request(url: str, *, payload=None, method="POST", timeout_seconds=30):  # type: ignore[no-untyped-def]
                if url.endswith("/health"):
                    return {"status": 200, "headers": {}, "body": {"status": "ok"}}
                if url.endswith("/.well-known/oauth-protected-resource"):
                    return {"status": 404, "headers": {}, "body": {"error": "not found"}}
                if url.endswith("/.well-known/oauth-authorization-server"):
                    return {"status": 404, "headers": {}, "body": {"error": "not found"}}
                if url.endswith("/.well-known/openid-configuration"):
                    return {"status": 404, "headers": {}, "body": {"error": "not found"}}
                raise AssertionError(f"Unexpected URL: {url}")

            responses = {
                1: _mcp_success(1, {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}}}),
                2: _mcp_success(
                    2,
                    {"tools": [{"name": name} for name in sorted(readiness.LAB_TOOLS | {"mystic_status"})]},
                ),
            }

            with patch.object(readiness, "http_json_request", side_effect=fake_http_json_request), patch.object(
                readiness,
                "mcp_request",
                side_effect=lambda *args, **kwargs: responses[kwargs["request_id"]],
            ):
                report = readiness.check_chatgpt_remote_mcp_readiness(
                    "https://mystic.dexproject.workers.dev",
                    timeout_seconds=5,
                    output_path=output_path,
                )

            self.assertTrue(report["health_ok"])
            self.assertTrue(report["mcp_initialize_ok"])
            self.assertTrue(report["tools_list_ok"])
            self.assertTrue(report["lab_tools_visible"])
            self.assertFalse(report["oauth_configured"])
            self.assertFalse(report["import_ready"])
            self.assertIn("OAUTH_NOT_CONFIGURED", report["blockers"])
            self.assertTrue(output_path.exists())


if __name__ == "__main__":
    unittest.main()

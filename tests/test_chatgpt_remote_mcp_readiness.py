from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch

from scripts import check_chatgpt_remote_mcp_readiness as readiness


def _mcp_success(request_id: int, result: dict[str, object]) -> dict[str, object]:
    return {"status": 200, "headers": {}, "body": {"jsonrpc": "2.0", "id": request_id, "result": result}}


class ChatGPTRemoteMCPReadinessTests(unittest.TestCase):
    def test_readiness_reports_oauth_blocker_when_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = readiness.Path(temp_dir) / "readiness.json"

            def fake_http_json_request(url: str, *, payload=None, method="POST", timeout_seconds=30, headers=None):  # type: ignore[no-untyped-def]
                if url.endswith("/health"):
                    return {"status": 200, "headers": {}, "body": {"status": "ok"}}
                if ".well-known/oauth-protected-resource" in url:
                    return {"status": 404, "headers": {}, "body": {"error": "not found"}}
                return {"status": 404, "headers": {}, "body": {"error": "missing"}}

            responses = {
                1: _mcp_success(1, {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}}}),
                4: _mcp_success(
                    4,
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
            self.assertFalse(report["oauth_configured"])
            self.assertFalse(report["import_ready"])
            self.assertFalse(report["import_ready_candidate"])
            self.assertIn("OAUTH_NOT_CONFIGURED", report["blockers"])

    def test_readiness_reports_candidate_when_oauth_and_token_path_work(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = readiness.Path(temp_dir) / "readiness.json"

            def fake_http_json_request(url: str, *, payload=None, method="POST", timeout_seconds=30, headers=None):  # type: ignore[no-untyped-def]
                if url.endswith("/health"):
                    return {"status": 200, "headers": {}, "body": {"status": "ok"}}
                if url.endswith("/.well-known/oauth-protected-resource"):
                    return {
                        "status": 200,
                        "headers": {},
                        "body": {
                            "resource": "https://mystic.dexproject.workers.dev/mcp",
                            "authorization_servers": ["https://mystic.dexproject.workers.dev"],
                        },
                    }
                if url.endswith("/.well-known/oauth-authorization-server"):
                    return {
                        "status": 200,
                        "headers": {},
                        "body": {
                            "authorization_endpoint": "https://mystic.dexproject.workers.dev/oauth/authorize",
                            "token_endpoint": "https://mystic.dexproject.workers.dev/oauth/token",
                        },
                    }
                if "/oauth/authorize?" in url:
                    return {"status": 200, "headers": {}, "body": {"ok": True}}
                if url.endswith("/oauth/token"):
                    return {"status": 400, "headers": {}, "body": {"error": "invalid_request"}}
                if url.endswith("/oauth/register"):
                    return {"status": 404, "headers": {}, "body": {"error": "not found"}}
                raise AssertionError(f"Unexpected URL: {url}")

            responses = {
                1: {
                    "status": 401,
                    "headers": {
                        "WWW-Authenticate": (
                            'Bearer resource_metadata="https://mystic.dexproject.workers.dev/.well-known/oauth-protected-resource"'
                        )
                    },
                    "body": {"error": "unauthorized"},
                },
                2: _mcp_success(2, {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}}}),
                3: _mcp_success(
                    3,
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
                    bearer_token="redacted-token",
                    expect_oauth=True,
                    timeout_seconds=5,
                    output_path=output_path,
                )

            self.assertTrue(report["oauth_configured"])
            self.assertTrue(report["oauth_metadata_ok"])
            self.assertTrue(report["oauth_authorize_ok"])
            self.assertTrue(report["oauth_token_ok"])
            self.assertTrue(report["token_validation_ok"])
            self.assertTrue(report["mcp_initialize_ok"])
            self.assertTrue(report["tools_list_ok"])
            self.assertTrue(report["lab_tools_visible"])
            self.assertTrue(report["import_ready_candidate"])
            self.assertFalse(report["import_ready"])
            self.assertNotIn("redacted-token", output_path.read_text(encoding="utf-8"))

    def test_readiness_can_require_dynamic_client_registration(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = readiness.Path(temp_dir) / "readiness.json"

            def fake_http_json_request(url: str, *, payload=None, method="POST", timeout_seconds=30, headers=None):  # type: ignore[no-untyped-def]
                if url.endswith("/health"):
                    return {"status": 200, "headers": {}, "body": {"status": "ok"}}
                if url.endswith("/.well-known/oauth-protected-resource"):
                    return {
                        "status": 200,
                        "headers": {},
                        "body": {
                            "resource": "https://mystic.dexproject.workers.dev/mcp",
                            "authorization_servers": ["https://mystic.dexproject.workers.dev"],
                        },
                    }
                if url.endswith("/.well-known/oauth-authorization-server"):
                    return {
                        "status": 200,
                        "headers": {},
                        "body": {
                            "authorization_endpoint": "https://mystic.dexproject.workers.dev/oauth/authorize",
                            "token_endpoint": "https://mystic.dexproject.workers.dev/oauth/token",
                        },
                    }
                if "/oauth/authorize?" in url:
                    return {"status": 200, "headers": {}, "body": {"ok": True}}
                if url.endswith("/oauth/token"):
                    return {"status": 400, "headers": {}, "body": {"error": "invalid_request"}}
                if url.endswith("/oauth/register"):
                    return {"status": 404, "headers": {}, "body": {"error": "not found"}}
                raise AssertionError(f"Unexpected URL: {url}")

            responses = {
                1: {
                    "status": 401,
                    "headers": {
                        "WWW-Authenticate": (
                            'Bearer resource_metadata="https://mystic.dexproject.workers.dev/.well-known/oauth-protected-resource"'
                        )
                    },
                    "body": {"error": "unauthorized"},
                },
                2: _mcp_success(2, {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}}}),
                3: _mcp_success(
                    3,
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
                    bearer_token="redacted-token",
                    expect_oauth=True,
                    require_dynamic_client_registration=True,
                    timeout_seconds=5,
                    output_path=output_path,
                )

            self.assertFalse(report["dynamic_client_registration_ok"])
            self.assertIn("OAUTH_DYNAMIC_CLIENT_REGISTRATION_MISSING", report["blockers"])
            self.assertFalse(report["import_ready_candidate"])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from mystic.mcp.import_verification import REQUIRED_TOOLS
from scripts import check_chatgpt_remote_mcp_readiness as readiness


def _mcp_success(request_id: int, result: dict[str, object]) -> dict[str, object]:
    return {"status": 200, "headers": {}, "body": {"jsonrpc": "2.0", "id": request_id, "result": result}}


class ChatGPTRemoteMCPReadinessTests(unittest.TestCase):
    def _write_artifact(self, directory: str, payload: dict[str, object]) -> readiness.Path:
        artifact_path = readiness.Path(directory) / "verification.json"
        artifact_path.write_text(readiness.json.dumps(payload, indent=2), encoding="utf-8")
        return artifact_path

    @staticmethod
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
                    {"tools": [{"name": name} for name in sorted(readiness.EXISTING_TOOLS | readiness.LAB_TOOLS)]},
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
            authorize_requests: list[str] = []

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
                    authorize_requests.append(url)
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
                    {"tools": [{"name": name} for name in sorted(readiness.EXISTING_TOOLS | readiness.LAB_TOOLS)]},
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
            self.assertFalse(report["manual_import_verified"])
            self.assertIn("MANUAL_IMPORT_NOT_VERIFIED", report["blockers"])
            self.assertNotIn("redacted-token", output_path.read_text(encoding="utf-8"))
            self.assertEqual(len(authorize_requests), 1)
            params = parse_qs(urlparse(authorize_requests[0]).query)
            self.assertEqual(params["client_id"], ["mystic-chatgpt"])
            self.assertEqual(
                params["redirect_uri"],
                ["https://chatgpt.com/connector/oauth/wpja_UKVNtTE"],
            )

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
                    {"tools": [{"name": name} for name in sorted(readiness.EXISTING_TOOLS | readiness.LAB_TOOLS)]},
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

    def test_readiness_returns_import_ready_true_with_valid_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = readiness.Path(temp_dir) / "readiness.json"
            artifact_path = self._write_artifact(temp_dir, self._valid_artifact("https://mystic.dexproject.workers.dev"))

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
                    return {"status": 200, "headers": {"content-type": "text/html"}, "body": {"raw": "<html></html>"}}
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
                3: _mcp_success(3, {"tools": [{"name": name} for name in sorted(readiness.EXISTING_TOOLS | readiness.LAB_TOOLS)]}),
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
                    manual_import_verification_artifact_path=artifact_path,
                )

            self.assertTrue(report["import_ready_candidate"])
            self.assertTrue(report["manual_import_verification_checked"])
            self.assertTrue(report["manual_import_verified"])
            self.assertTrue(report["import_ready"])

    def test_readiness_reports_manual_import_blocker_when_artifact_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = readiness.Path(temp_dir) / "readiness.json"
            artifact_path = readiness.Path(temp_dir) / "missing.json"

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
                    return {"status": 200, "headers": {"content-type": "text/html"}, "body": {"raw": "<html></html>"}}
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
                3: _mcp_success(3, {"tools": [{"name": name} for name in sorted(readiness.EXISTING_TOOLS | readiness.LAB_TOOLS)]}),
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
                    manual_import_verification_artifact_path=artifact_path,
                )

            self.assertTrue(report["import_ready_candidate"])
            self.assertFalse(report["import_ready"])
            self.assertIn("MANUAL_IMPORT_NOT_VERIFIED", report["blockers"])

    def test_readiness_rejects_invalid_artifact_and_endpoint_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = readiness.Path(temp_dir) / "readiness.json"
            artifact = self._valid_artifact("https://other.example.com")
            artifact["manual_tool_call_results"] = {"lab_session_create": "passed"}
            artifact_path = self._write_artifact(temp_dir, artifact)

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
                    return {"status": 200, "headers": {"content-type": "text/html"}, "body": {"raw": "<html></html>"}}
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
                3: _mcp_success(3, {"tools": [{"name": name} for name in sorted(readiness.EXISTING_TOOLS | readiness.LAB_TOOLS)]}),
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
                    manual_import_verification_artifact_path=artifact_path,
                )

            self.assertFalse(report["manual_import_verified"])
            self.assertFalse(report["import_ready"])
            self.assertTrue(report["manual_import_verification_errors"])

    def test_readiness_rejects_secret_like_artifact_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = readiness.Path(temp_dir) / "readiness.json"
            artifact = self._valid_artifact("https://mystic.dexproject.workers.dev")
            artifact["client_secret"] = "redacted"
            artifact_path = self._write_artifact(temp_dir, artifact)

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
                    return {"status": 200, "headers": {"content-type": "text/html"}, "body": {"raw": "<html></html>"}}
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
                3: _mcp_success(3, {"tools": [{"name": name} for name in sorted(readiness.EXISTING_TOOLS | readiness.LAB_TOOLS)]}),
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
                    manual_import_verification_artifact_path=artifact_path,
                )

            self.assertFalse(report["manual_import_verified"])
            self.assertFalse(report["import_ready"])
            self.assertTrue(report["manual_import_verification_errors"])

    def test_valid_artifact_does_not_override_candidate_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = readiness.Path(temp_dir) / "readiness.json"
            artifact_path = self._write_artifact(temp_dir, self._valid_artifact("https://mystic.dexproject.workers.dev"))

            def fake_http_json_request(url: str, *, payload=None, method="POST", timeout_seconds=30, headers=None):  # type: ignore[no-untyped-def]
                if url.endswith("/health"):
                    return {"status": 503, "headers": {}, "body": {"error": "down"}}
                if ".well-known/oauth-protected-resource" in url:
                    return {"status": 404, "headers": {}, "body": {"error": "not found"}}
                return {"status": 404, "headers": {}, "body": {"error": "missing"}}

            responses = {
                1: _mcp_success(1, {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}}}),
                4: _mcp_success(4, {"tools": [{"name": name} for name in sorted(readiness.EXISTING_TOOLS | readiness.LAB_TOOLS)]}),
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
                    manual_import_verification_artifact_path=artifact_path,
                )

            self.assertFalse(report["import_ready_candidate"])
            self.assertTrue(report["manual_import_verified"])
            self.assertFalse(report["import_ready"])


if __name__ == "__main__":
    unittest.main()

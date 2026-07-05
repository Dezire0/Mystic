from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch

from scripts import check_public_backend_origin as origin_health


def _mcp_success(request_id: int, result: dict[str, object]) -> dict[str, object]:
    return {"status": 200, "headers": {}, "body": {"jsonrpc": "2.0", "id": request_id, "result": result}}


class PublicBackendOriginHealthTests(unittest.TestCase):
    def test_public_health_ok_classifies_ok(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = origin_health.Path(temp_dir) / "summary.json"
            responses = {
                1: _mcp_success(1, {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}}}),
            }

            def fake_http_json_request(url: str, *, payload=None, method="POST", timeout_seconds=30, headers=None):  # type: ignore[no-untyped-def]
                if url.endswith("/health"):
                    return {"status": 200, "headers": {}, "body": {"status": "ok"}}
                raise AssertionError(f"Unexpected URL: {url}")

            with patch.object(origin_health, "http_json_request", side_effect=fake_http_json_request), patch.object(
                origin_health,
                "mcp_request",
                side_effect=lambda *args, **kwargs: responses[kwargs["request_id"]],
            ):
                summary = origin_health.check_public_backend_origin(
                    "https://mystic.dexproject.workers.dev",
                    output_path=output_path,
                )

            self.assertEqual(summary["failure_category"], origin_health.OK)
            self.assertTrue(summary["public_health_ok"])
            self.assertTrue(summary["likely_worker_ok"])

    def test_backend_origin_dead_classification(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = origin_health.Path(temp_dir) / "summary.json"
            health_response = {
                "status": 530,
                "headers": {"x-mystic-public-origin": "https://expired.trycloudflare.com"},
                "body": {"raw": "Error 1016 Origin DNS error"},
            }
            responses = {
                1: {
                    "status": 401,
                    "headers": {"WWW-Authenticate": "Bearer resource_metadata=https://example.com/.well-known/oauth-protected-resource"},
                    "body": {"error": "unauthorized"},
                },
            }
            with patch.object(origin_health, "http_json_request", return_value=health_response), patch.object(
                origin_health,
                "mcp_request",
                side_effect=lambda *args, **kwargs: responses[kwargs["request_id"]],
            ):
                summary = origin_health.check_public_backend_origin(
                    "https://mystic.dexproject.workers.dev",
                    expect_oauth=True,
                    output_path=output_path,
                )

            self.assertEqual(summary["failure_category"], origin_health.BACKEND_ORIGIN_DEAD)
            self.assertTrue(summary["likely_origin_dead"])

    def test_no_token_auth_required_ok(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = origin_health.Path(temp_dir) / "summary.json"
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
            }

            def fake_http_json_request(url: str, *, payload=None, method="POST", timeout_seconds=30, headers=None):  # type: ignore[no-untyped-def]
                if url.endswith("/health"):
                    return {"status": 200, "headers": {}, "body": {"status": "ok"}}
                raise AssertionError(f"Unexpected URL: {url}")

            with patch.object(origin_health, "http_json_request", side_effect=fake_http_json_request), patch.object(
                origin_health,
                "mcp_request",
                side_effect=lambda *args, **kwargs: responses[kwargs["request_id"]],
            ):
                summary = origin_health.check_public_backend_origin(
                    "https://mystic.dexproject.workers.dev",
                    expect_oauth=True,
                    output_path=output_path,
                )

            self.assertTrue(summary["mcp_auth_required_ok"])
            self.assertEqual(summary["failure_category"], origin_health.OK)

    def test_bearer_mcp_ok(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = origin_health.Path(temp_dir) / "summary.json"
            seen_headers: list[dict[str, str] | None] = []
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
                3: _mcp_success(3, {"tools": [{"name": name} for name in sorted(origin_health.LAB_TOOLS | {"mystic_status"})]}),
            }

            def fake_http_json_request(url: str, *, payload=None, method="POST", timeout_seconds=30, headers=None):  # type: ignore[no-untyped-def]
                if url.endswith("/health"):
                    return {"status": 200, "headers": {}, "body": {"status": "ok"}}
                raise AssertionError(f"Unexpected URL: {url}")

            def fake_mcp_request(*args, **kwargs):  # type: ignore[no-untyped-def]
                seen_headers.append(kwargs.get("headers"))
                return responses[kwargs["request_id"]]

            with patch.object(origin_health, "http_json_request", side_effect=fake_http_json_request), patch.object(
                origin_health,
                "mcp_request",
                side_effect=fake_mcp_request,
            ):
                summary = origin_health.check_public_backend_origin(
                    "https://mystic.dexproject.workers.dev",
                    expect_oauth=True,
                    bearer_token="secret-token",
                    output_path=output_path,
                )

            self.assertTrue(summary["bearer_mcp_ok"])
            self.assertEqual(summary["failure_category"], origin_health.OK)
            self.assertIn({"Authorization": "Bearer secret-token"}, seen_headers)

    def test_bearer_token_redaction(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = origin_health.Path(temp_dir) / "summary.json"
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
                2: {"status": 500, "headers": {}, "body": {"raw": "secret-token should never be written"}},
            }

            def fake_http_json_request(url: str, *, payload=None, method="POST", timeout_seconds=30, headers=None):  # type: ignore[no-untyped-def]
                if url.endswith("/health"):
                    return {"status": 200, "headers": {}, "body": {"status": "ok"}}
                raise AssertionError(f"Unexpected URL: {url}")

            with patch.object(origin_health, "http_json_request", side_effect=fake_http_json_request), patch.object(
                origin_health,
                "mcp_request",
                side_effect=lambda *args, **kwargs: responses[kwargs["request_id"]],
            ):
                summary = origin_health.check_public_backend_origin(
                    "https://mystic.dexproject.workers.dev",
                    expect_oauth=True,
                    bearer_token="secret-token",
                    output_path=output_path,
                )

            self.assertEqual(summary["failure_category"], origin_health.BEARER_MCP_FAILED)
            self.assertFalse(summary["bearer_mcp_ok"])
            self.assertNotIn("secret-token", output_path.read_text(encoding="utf-8"))
            self.assertNotIn("secret-token", origin_health.json.dumps(summary))

    def test_origin_dead_on_502_like_worker_response(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = origin_health.Path(temp_dir) / "summary.json"
            health_response = {
                "status": 502,
                "headers": {"x-mystic-public-origin": "https://expired.trycloudflare.com"},
                "body": {"raw": "Upstream or external service errors"},
            }
            responses = {
                1: {"status": 500, "headers": {}, "body": {"error": "not reached"}},
            }
            with patch.object(origin_health, "http_json_request", return_value=health_response), patch.object(
                origin_health,
                "mcp_request",
                side_effect=lambda *args, **kwargs: responses[kwargs["request_id"]],
            ):
                summary = origin_health.check_public_backend_origin(
                    "https://mystic.dexproject.workers.dev",
                    output_path=output_path,
                )

            self.assertEqual(summary["failure_category"], origin_health.BACKEND_ORIGIN_DEAD)
            self.assertTrue(summary["likely_origin_dead"])

    def test_output_summary_includes_recommendations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = origin_health.Path(temp_dir) / "summary.json"
            health_response = {"status": None, "headers": {}, "body": {"error": "network unreachable"}}
            responses = {
                1: {"status": None, "headers": {}, "body": {"error": "network unreachable"}},
            }
            with patch.object(origin_health, "http_json_request", return_value=health_response), patch.object(
                origin_health,
                "mcp_request",
                side_effect=lambda *args, **kwargs: responses[kwargs["request_id"]],
            ):
                summary = origin_health.check_public_backend_origin(
                    "https://mystic.dexproject.workers.dev",
                    output_path=output_path,
                )

            self.assertEqual(summary["failure_category"], origin_health.PUBLIC_WORKER_UNREACHABLE)
            self.assertTrue(summary["recommendations"])
            self.assertIn("Cloudflare Worker", summary["recommendations"][0])


if __name__ == "__main__":
    unittest.main()

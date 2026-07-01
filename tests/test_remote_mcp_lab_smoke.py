from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch

from scripts import run_remote_mcp_lab_smoke as smoke


def _mcp_success(request_id: int, result: dict[str, object]) -> dict[str, object]:
    return {"status": 200, "headers": {}, "body": {"jsonrpc": "2.0", "id": request_id, "result": result}}


class RemoteMCPLabSmokeTests(unittest.TestCase):
    def test_remote_smoke_success_creates_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = smoke.Path(temp_dir)
            session_dir = temp_root / "mystic_data" / "lab_sessions" / "lab-123"
            session_dir.mkdir(parents=True, exist_ok=True)
            persisted = {
                "session_path": str(session_dir / "session.json"),
                "notebook_path": str(session_dir / "notebook.md"),
                "report_path": str(session_dir / "report.md"),
            }
            for path_text in persisted.values():
                smoke.Path(path_text).write_text("ok", encoding="utf-8")
            output_path = temp_root / "summary.json"

            responses = {
                1: _mcp_success(1, {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}}}),
                2: _mcp_success(
                    2,
                    {"tools": [{"name": name} for name in sorted(smoke.EXISTING_TOOLS | smoke.LAB_TOOLS)]},
                ),
                3: _mcp_success(3, {"structuredContent": {"session_id": "lab-123", "paths": persisted}}),
                4: _mcp_success(4, {"structuredContent": {"updated_session": {"session_id": "lab-123"}, "paths": persisted}}),
                5: _mcp_success(
                    5,
                    {
                        "structuredContent": {
                            "session": {"session_id": "lab-123"},
                            "notebook_path": persisted["notebook_path"],
                            "report_path": persisted["report_path"],
                        }
                    },
                ),
                6: _mcp_success(6, {"structuredContent": {"report_path": persisted["report_path"]}}),
            }

            with patch.object(smoke, "mcp_request", side_effect=lambda *args, **kwargs: responses[kwargs["request_id"]]):
                summary = smoke.run_remote_mcp_lab_smoke(
                    endpoint="http://127.0.0.1:8765/mcp",
                    session_problem="test problem",
                    domain="math",
                    mode="proof_critical",
                    timeout_seconds=5,
                    output_path=output_path,
                )

            self.assertEqual(summary["final_status"], smoke.READY_LOCAL)
            self.assertTrue(summary["session_created"])
            self.assertTrue(summary["advance_ok"])
            self.assertTrue(summary["get_ok"])
            self.assertTrue(summary["report_ok"])
            self.assertEqual(summary["session_id"], "lab-123")
            self.assertTrue(output_path.exists())

    def test_remote_smoke_reports_missing_lab_tools(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = smoke.Path(temp_dir) / "summary.json"
            responses = {
                1: _mcp_success(1, {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}}}),
                2: _mcp_success(2, {"tools": [{"name": name} for name in sorted(smoke.EXISTING_TOOLS)]}),
            }
            with patch.object(smoke, "mcp_request", side_effect=lambda *args, **kwargs: responses[kwargs["request_id"]]):
                summary = smoke.run_remote_mcp_lab_smoke(
                    endpoint="http://127.0.0.1:8765/mcp",
                    session_problem="test problem",
                    domain="math",
                    mode="proof_critical",
                    timeout_seconds=5,
                    output_path=output_path,
                )

            self.assertEqual(summary["final_status"], smoke.MISSING_LAB_TOOLS)
            self.assertIn("lab_session_create", summary["missing_tools"])

    def test_remote_smoke_reports_oauth_required_for_chatgpt_import(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = smoke.Path(temp_dir) / "summary.json"
            response = {
                "status": 401,
                "headers": {
                    "WWW-Authenticate": (
                        'Bearer resource_metadata="https://mystic.dexproject.workers.dev/.well-known/oauth-protected-resource"'
                    )
                },
                "body": {"error": "unauthorized"},
            }
            with patch.object(smoke, "mcp_request", return_value=response):
                summary = smoke.run_remote_mcp_lab_smoke(
                    endpoint="https://mystic.dexproject.workers.dev/mcp",
                    session_problem="test problem",
                    domain="math",
                    mode="proof_critical",
                    timeout_seconds=5,
                    output_path=output_path,
                )

            self.assertEqual(summary["final_status"], smoke.OAUTH_REQUIRED)
            self.assertTrue(summary["auth_required"])
            self.assertTrue(summary["oauth_required"])


if __name__ == "__main__":
    unittest.main()

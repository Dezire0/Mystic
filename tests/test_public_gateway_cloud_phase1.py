from __future__ import annotations

import json
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


def run_worker_helper(helper: str, payload: dict[str, object]) -> dict[str, object] | str:
    script = """
import { __test } from './cloudflare/mystic_public_gateway_worker.js';
const helper = process.argv[1];
const payload = JSON.parse(process.argv[2]);
const result = await __test[helper](payload);
console.log(JSON.stringify(result));
"""
    completed = subprocess.run(
        ["node", "--input-type=module", "-e", script, helper, json.dumps(payload)],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(completed.stdout)


class PublicGatewayCloudPhase1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.env = {
            "MYSTIC_STORAGE_BACKEND": "supabase",
            "MYSTIC_SUPABASE_URL": "https://example.supabase.co",
            "MYSTIC_SUPABASE_SERVICE_ROLE_KEY": "service-role-key",
            "MYSTIC_OAUTH_ENABLED": "true",
            "MYSTIC_OAUTH_ISSUER": "https://mystic.dexproject.workers.dev",
            "MYSTIC_OAUTH_SIGNING_SECRET": "secret-signing-key",
            "MYSTIC_OAUTH_DEV_STATIC_TOKEN": "dev-static-token",
        }
        self.auth_headers = {"Authorization": "Bearer dev-static-token"}
        self.request_url = "https://mystic.dexproject.workers.dev/mcp"

    def test_cloud_phase1_health_returns_ok_without_backend_proxy(self) -> None:
        result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": "https://mystic.dexproject.workers.dev/health",
                "method": "GET",
            },
        )
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["body"], {"status": "ok"})
        self.assertEqual(result["headers"]["x-mystic-public-origin"], "worker://supabase")
        self.assertEqual(result["fetchCalls"], [])

    def test_cloud_phase1_tools_list_exposes_required_tools(self) -> None:
        result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            },
        )
        self.assertEqual(result["status"], 200)
        tool_names = [tool["name"] for tool in result["body"]["result"]["tools"]]
        self.assertEqual(
            tool_names,
            [
                "mystic_status",
                "health_check",
                "lab_session_create",
                "lab_session_get",
                "lab_report_generate",
            ],
        )

    def test_cloud_phase1_lab_session_create_writes_supabase(self) -> None:
        result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "lab_session_create",
                        "arguments": {
                            "problem": "x + y = 5",
                            "domain": "math",
                            "goal": "Create a cloud-native lab session.",
                            "mode": "proof_critical",
                            "participants": ["Director", "Theorist"],
                        },
                    },
                },
                "fetchResponses": [
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_sessions", "status": 201, "body": [{}]},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/lab_turns", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/claims", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/failures", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/memory_edges", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/reports", "status": 204},
                ],
            },
        )
        payload = result["body"]["result"]["structuredContent"]
        self.assertTrue(str(payload["session_id"]).startswith("lab-"))
        self.assertTrue(payload["paths"]["session"].startswith("supabase://public/lab_sessions/"))
        session_posts = [call for call in result["fetchCalls"] if call["method"] == "POST"]
        self.assertEqual(len(session_posts), 1)
        self.assertIn(payload["session_id"], session_posts[0]["body"])

    def test_cloud_phase1_get_and_report_generate_use_supabase_state(self) -> None:
        session_id = "lab-20260706010101-abcdef12"
        session_row = {
            "session_id": session_id,
            "problem": "x + y = 5",
            "domain": "math",
            "goal": "Read a saved session.",
            "mode": "proof_critical",
            "status": "created",
            "current_phase": "problem_intake",
            "active_room": "Control Panel",
            "created_at": "2026-07-06T01:01:01Z",
            "updated_at": "2026-07-06T01:01:01Z",
            "controller": {"model_id": "gpt_controller"},
            "participants": [],
            "artifact_paths": {
                "session": f"supabase://public/lab_sessions/{session_id}",
                "report": f"supabase://public/reports/{session_id}",
                "notebook": f"supabase://public/lab_sessions/{session_id}#notebook",
            },
            "next_actions": ["Generate report."],
            "warnings": [],
            "notebook_markdown": "# Notebook",
            "experiments_json": [],
        }
        common_fetch = [
            {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_sessions", "status": 200, "body": [session_row]},
            {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_turns", "status": 200, "body": []},
            {"methodPrefix": "GET https://example.supabase.co/rest/v1/claims", "status": 200, "body": []},
            {"methodPrefix": "GET https://example.supabase.co/rest/v1/failures", "status": 200, "body": []},
            {"methodPrefix": "GET https://example.supabase.co/rest/v1/memory_edges", "status": 200, "body": []},
            {"methodPrefix": "GET https://example.supabase.co/rest/v1/reports", "status": 200, "body": []},
        ]
        get_result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {"name": "lab_session_get", "arguments": {"session_id": session_id}},
                },
                "fetchResponses": common_fetch,
            },
        )
        get_payload = get_result["body"]["result"]["structuredContent"]
        self.assertEqual(get_payload["session"]["session_id"], session_id)
        self.assertEqual(get_payload["report_markdown"], "")

        report_result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 5,
                    "method": "tools/call",
                    "params": {
                        "name": "lab_report_generate",
                        "arguments": {
                            "session_id": session_id,
                            "format": "markdown",
                            "include_failures": True,
                            "include_next_actions": True,
                        },
                    },
                },
                "fetchResponses": [
                    *common_fetch,
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_sessions", "status": 201, "body": [{}]},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/lab_turns", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/claims", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/failures", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/memory_edges", "status": 204},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/reports", "status": 201, "body": [{}]},
                ],
            },
        )
        report_payload = report_result["body"]["result"]["structuredContent"]
        self.assertTrue(report_payload["report_path"].startswith("supabase://public/reports/"))
        self.assertIn(session_id, report_payload["markdown"])


if __name__ == "__main__":
    unittest.main()

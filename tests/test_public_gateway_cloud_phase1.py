from __future__ import annotations

import json
from pathlib import Path
import subprocess
import unittest

from scripts import check_chatgpt_action_discovery_compatibility as compatibility


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
            "MYSTIC_PROVIDER_CONNECT_BASE_URL": "https://mystic.dexproject.workers.dev",
        }
        self.auth_headers = {"Authorization": "Bearer dev-static-token"}
        self.request_url = "https://mystic.dexproject.workers.dev/mcp"

    @staticmethod
    def _session_row(session_id: str) -> dict[str, object]:
        return {
            "session_id": session_id,
            "problem": "x + y = 5",
            "domain": "math",
            "goal": "Read a saved session.",
            "mode": "proof_critical",
            "status": "created",
            "current_phase": "problem_intake",
            "active_room": "Main Lab Room",
            "created_at": "2026-07-06T01:01:01Z",
            "updated_at": "2026-07-06T01:01:01Z",
            "controller": {"model_id": "gpt_controller"},
            "participants": [],
            "artifact_paths": {
                "session": f"supabase://public/lab_sessions/{session_id}",
                "report": f"supabase://public/reports/{session_id}",
                "notebook": f"supabase://public/lab_sessions/{session_id}#notebook",
                "claims": f"supabase://public/claims?session_id={session_id}",
                "experiments": f"supabase://public/lab_sessions/{session_id}#experiments",
                "memory_edges": f"supabase://public/memory_edges?session_id={session_id}",
            },
            "next_actions": ["Generate report."],
            "warnings": [],
            "notebook_markdown": "# Notebook",
            "experiments_json": [],
        }

    @staticmethod
    def _scene_row(scene_id: str, session_id: str, *, domain: str = "physics") -> dict[str, object]:
        return {
            "scene_id": scene_id,
            "session_id": session_id,
            "domain": domain,
            "title": "Projectile baseline",
            "description": "Cloud-native scene",
            "units": {"length": "m", "time": "s", "mass": "kg"},
            "parameters": {"gravity": 9.81},
            "attached_simulations": [],
            "evidence_refs": [],
            "report_refs": [],
            "metadata": {"scene_adapter": "scene.three_json"},
            "artifact_paths": {
                "scene": f"supabase://public/lab_scenes/{scene_id}",
                "objects": f"supabase://public/lab_scene_objects?scene_id={scene_id}",
                "simulations": f"supabase://public/lab_simulations?scene_id={scene_id}",
                "report": f"supabase://public/lab_scenes/{scene_id}#report",
                "snapshot": f"supabase://public/lab_scenes/{scene_id}#exports",
            },
            "exports_json": {},
            "report_markdown": "",
            "created_at": "2026-07-06T01:01:01Z",
            "updated_at": "2026-07-06T01:01:01Z",
        }

    @staticmethod
    def _provider_connection_row(provider_id: str, *, status: str = "connected") -> dict[str, object]:
        provider_type = "future/custom" if provider_id == "future_custom" else provider_id
        auth_method = "oauth" if provider_id in {"future_custom", "google_vertex_ai"} else "api_key"
        return {
            "connection_id": f"provider-{provider_id}",
            "provider_id": provider_id,
            "provider_type": provider_type,
            "auth_method": auth_method,
            "status": status,
            "scopes": ["model:generate"],
            "model_list": ["mock-model"] if provider_id == "mock" else [f"{provider_id}-model"],
            "setup_url": f"https://mystic.dexproject.workers.dev/providers/{provider_id}/setup",
            "setup_instructions": "setup",
            "last_verified_at": "2026-07-06T01:01:01Z",
            "failure_reason": "",
            "metadata": {
                "connect_url": f"https://mystic.dexproject.workers.dev/providers/{provider_id}/connect",
                "status_url": f"https://mystic.dexproject.workers.dev/providers/{provider_id}/status",
            },
            "created_at": "2026-07-06T01:01:01Z",
            "updated_at": "2026-07-06T01:01:01Z",
        }

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

    def test_cloud_phase1_initialize_returns_mcp_server_capabilities(self) -> None:
        result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {"jsonrpc": "2.0", "id": 1, "method": "initialize"},
            },
        )
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["body"]["result"]["protocolVersion"], "2025-06-18")
        self.assertEqual(result["body"]["result"]["serverInfo"]["name"], "mystic-cloud-worker")
        self.assertEqual(result["fetchCalls"], [])

    def test_cloud_phase1_requires_auth_before_mcp_runtime(self) -> None:
        result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "body": {"jsonrpc": "2.0", "id": 9, "method": "initialize"},
            },
        )
        self.assertEqual(result["status"], 401)
        self.assertIn("www-authenticate", result["headers"])
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
                "lab_session_advance",
                "lab_agent_run",
                "lab_referee_review",
                "lab_experiment_create",
                "lab_experiment_run",
                "lab_memory_search",
                "lab_memory_write",
                "lab_models_debate",
                "lab_report_generate",
                "create_lab_scene",
                "get_lab_scene",
                "add_lab_object",
                "update_lab_object",
                "remove_lab_object",
                "set_lab_parameters",
                "run_lab_simulation",
                "attach_simulation_to_scene",
                "export_lab_snapshot",
                "generate_lab_report",
                "provider_list",
                "provider_status",
                "provider_connect_start",
                "provider_connect_callback_status",
                "provider_configure_secret_instructions",
                "provider_verify",
                "provider_disconnect",
                "provider_model_list",
                "provider_call_test",
            ],
        )

    def test_cloud_phase1_tools_list_passes_chatgpt_action_discovery_rules(self) -> None:
        result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            },
        )
        tools = result["body"]["result"]["tools"]
        seen: set[str] = set()
        summaries = [compatibility.evaluate_tool_descriptor(tool, seen) for tool in tools]
        self.assertTrue(summaries)
        for summary in summaries:
            self.assertEqual(summary["blockers"], [], msg=json.dumps(summary, indent=2))

    def test_cloud_phase1_mystic_status_reports_supabase_mode(self) -> None:
        result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 10,
                    "method": "tools/call",
                    "params": {"name": "mystic_status", "arguments": {}},
                },
            },
        )
        payload = result["body"]["result"]["structuredContent"]
        self.assertEqual(payload["storage_backend"], "supabase")
        self.assertTrue(payload["storage_status"]["configured"])
        self.assertEqual(payload["runtime_mode"], "cloud_native_worker_lab_v0")
        self.assertIn("health_check", payload["tools"])
        self.assertIn("provider_list", payload["tools"])
        self.assertTrue(payload["chatgpt_remote_import_ready_candidate"])
        self.assertFalse(payload["chatgpt_remote_import_ready"])
        self.assertEqual(result["fetchCalls"], [])

    def test_cloud_phase1_mystic_status_reports_verified_import_when_runtime_artifact_is_configured(self) -> None:
        verification_payload = {
            "artifact_version": 1,
            "verified_at": "2026-07-07T13:48:38.147408+00:00",
            "verified_by": "manual",
            "public_endpoint": "https://mystic.dexproject.workers.dev",
            "mcp_endpoint": "https://mystic.dexproject.workers.dev/mcp",
            "chatgpt_developer_mode_imported": True,
            "oauth_flow_completed": True,
            "tools_list_visible_in_chatgpt": True,
            "required_tools_visible": [
                "health_check",
                "lab_session_create",
                "lab_session_get",
                "lab_report_generate",
            ],
            "manual_tool_call_results": {
                "health_check": "passed",
                "lab_session_create": "passed",
                "lab_session_get": "passed",
                "lab_report_generate": "passed",
            },
            "notes": "manual verification notes",
        }
        result = run_worker_helper(
            "simulateRequest",
            {
                "env": {
                    **self.env,
                    "MYSTIC_CHATGPT_IMPORT_VERIFICATION_JSON": json.dumps(verification_payload),
                },
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 11,
                    "method": "tools/call",
                    "params": {"name": "mystic_status", "arguments": {}},
                },
            },
        )
        payload = result["body"]["result"]["structuredContent"]
        self.assertTrue(payload["chatgpt_remote_import_ready"])
        self.assertTrue(payload["manual_import_verification_checked"])
        self.assertTrue(payload["manual_import_verified"])
        self.assertEqual(payload["manual_import_verification_path"], "env://MYSTIC_CHATGPT_IMPORT_VERIFICATION_JSON")
        self.assertNotIn("MANUAL_IMPORT_NOT_VERIFIED", payload["blockers"])
        self.assertEqual(payload["manual_import_verification_summary"]["verified_by"], "manual")
        self.assertNotIn("notes", json.dumps(payload))

    def test_cloud_provider_list_and_status_return_safe_registry_data(self) -> None:
        legacy_row = self._provider_connection_row("openai_compatible", status="api_key_required")
        legacy_row["setup_url"] = "https://platform.openai.com/api-keys"
        legacy_row["metadata"]["external_setup_url"] = "https://platform.openai.com/api-keys"
        list_result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {"jsonrpc": "2.0", "id": 101, "method": "tools/call", "params": {"name": "provider_list", "arguments": {}}},
                "fetchResponses": [
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/provider_connections", "status": 200, "body": [legacy_row]},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/provider_oauth_tokens", "status": 200, "body": []},
                ],
            },
        )
        status_result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 102,
                    "method": "tools/call",
                    "params": {"name": "provider_status", "arguments": {"provider_id": "openai_compatible"}},
                },
                "fetchResponses": [
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/provider_connections", "status": 200, "body": [legacy_row]},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/provider_oauth_tokens", "status": 200, "body": []},
                ],
            },
        )
        instructions_result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 103,
                    "method": "tools/call",
                    "params": {"name": "provider_configure_secret_instructions", "arguments": {"provider_id": "openai_compatible"}},
                },
            },
        )

        listing = list_result["body"]["result"]["structuredContent"]
        status = status_result["body"]["result"]["structuredContent"]
        instructions = instructions_result["body"]["result"]["structuredContent"]
        self.assertEqual(listing["providers"][0]["provider_id"], "openai_compatible")
        self.assertIn("google_vertex_ai", [item["provider_id"] for item in listing["providers"]])
        self.assertIn(status["status"], {"not_configured", "api_key_required"})
        self.assertIn("/providers/openai_compatible/setup", status["setup_url"])
        self.assertIn("/providers/openai_compatible/connect", status["connect_url"])
        self.assertEqual(listing["providers"][0]["external_setup_url"], "https://platform.openai.com/api-keys")
        self.assertIn("MYSTIC_PROVIDER_OPENAI_COMPAT_API_KEY", instructions["secret_names"])
        self.assertNotIn("service-role-key", json.dumps(instructions))
        self.assertFalse(instructions["direct_secret_write_supported"])

    def test_cloud_provider_connect_start_and_callback_status_record_oauth_metadata_flow(self) -> None:
        connect_result = run_worker_helper(
            "simulateRequest",
            {
                "env": {
                    **self.env,
                    "MYSTIC_PROVIDER_FUTURE_CUSTOM_OAUTH_ENABLED": "true",
                    "MYSTIC_PROVIDER_FUTURE_CUSTOM_AUTHORIZATION_ENDPOINT": "https://provider.example.com/oauth/authorize",
                    "MYSTIC_PROVIDER_FUTURE_CUSTOM_TOKEN_ENDPOINT": "https://provider.example.com/oauth/token",
                    "MYSTIC_PROVIDER_FUTURE_CUSTOM_CLIENT_ID": "client-123",
                    "MYSTIC_PROVIDER_FUTURE_CUSTOM_REDIRECT_URI": "https://mystic.dexproject.workers.dev/providers/oauth/callback?provider_id=future_custom",
                    "MYSTIC_PROVIDER_FUTURE_CUSTOM_SCOPES": "model:generate profile",
                },
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 104,
                    "method": "tools/call",
                    "params": {
                        "name": "provider_connect_start",
                        "arguments": {"provider_id": "future_custom", "auth_method": "oauth"},
                    },
                },
                "fetchResponses": [
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/provider_auth_flows", "status": 201, "body": [{}]},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/provider_connections", "status": 201, "body": [{}]},
                ],
            },
        )
        flow_id = connect_result["body"]["result"]["structuredContent"]["flow"]["flow_id"]
        callback_result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 105,
                    "method": "tools/call",
                    "params": {
                        "name": "provider_connect_callback_status",
                        "arguments": {"provider_id": "future_custom", "flow_id": flow_id},
                    },
                },
                "fetchResponses": [
                    {
                        "methodPrefix": "GET https://example.supabase.co/rest/v1/provider_auth_flows",
                        "status": 200,
                        "body": [
                            {
                                "flow_id": flow_id,
                                "provider_id": "future_custom",
                                "auth_method": "oauth",
                                "status": "oauth_required",
                                "authorization_url": "https://provider.example.com/oauth/authorize?response_type=code",
                                "redirect_url": "https://mystic.dexproject.workers.dev/providers/oauth/callback?provider_id=future_custom",
                                "state": "",
                                "state_hash": "abc123",
                                "code_challenge": "challenge-1",
                                "code_challenge_method": "S256",
                                "callback_received_at": None,
                                "failure_reason": "",
                                "metadata": {},
                                "created_at": "2026-07-06T01:01:01Z",
                                "updated_at": "2026-07-06T01:01:01Z",
                            }
                        ],
                    },
                    {
                        "methodPrefix": "GET https://example.supabase.co/rest/v1/provider_connections",
                        "status": 200,
                        "body": [self._provider_connection_row("future_custom", status="oauth_required")],
                    },
                ],
            },
        )
        self.assertEqual(connect_result["body"]["result"]["structuredContent"]["status"], "oauth_required")
        self.assertIn("provider.example.com/oauth/authorize", connect_result["body"]["result"]["structuredContent"]["authorization_url"])
        self.assertNotIn("state", callback_result["body"]["result"]["structuredContent"]["flow"])
        self.assertTrue(callback_result["body"]["result"]["structuredContent"]["flow"]["state_hash"])
        self.assertEqual(callback_result["body"]["result"]["structuredContent"]["flow"]["status"], "oauth_required")
        self.assertFalse(callback_result["body"]["result"]["structuredContent"]["callback_received"])

    def test_cloud_provider_connect_start_returns_secure_setup_url_for_api_key_provider(self) -> None:
        result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 111,
                    "method": "tools/call",
                    "params": {"name": "provider_connect_start", "arguments": {"provider_id": "gemini", "auth_method": "oauth"}},
                },
                "fetchResponses": [
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/provider_connections", "status": 201, "body": [{}]},
                ],
            },
        )
        payload = result["body"]["result"]["structuredContent"]
        self.assertEqual(payload["status"], "api_key_required")
        self.assertEqual(payload["auth_method"], "api_key")
        self.assertIn("/providers/gemini/setup", payload["setup_url"])

    def test_cloud_google_vertex_connect_start_returns_provider_required_without_metadata(self) -> None:
        result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 112,
                    "method": "tools/call",
                    "params": {
                        "name": "provider_connect_start",
                        "arguments": {"provider_id": "google_vertex_ai", "auth_method": "oauth"},
                    },
                },
            },
        )
        payload = result["body"]["result"]["structuredContent"]
        self.assertEqual(payload["status"], "provider_required")
        self.assertEqual(payload["auth_method"], "oauth")
        self.assertIn("MYSTIC_PROVIDER_GOOGLE_VERTEX_CLIENT_SECRET", payload["required_secret_names"])

    def test_cloud_google_vertex_connect_start_returns_google_authorization_url_when_metadata_exists(self) -> None:
        result = run_worker_helper(
            "simulateRequest",
            {
                "env": {
                    **self.env,
                    "MYSTIC_PROVIDER_GOOGLE_VERTEX_OAUTH_ENABLED": "true",
                    "MYSTIC_PROVIDER_GOOGLE_VERTEX_CLIENT_ID": "google-client-id",
                    "MYSTIC_PROVIDER_GOOGLE_VERTEX_CLIENT_SECRET": "google-client-secret",
                    "MYSTIC_PROVIDER_GOOGLE_VERTEX_PROJECT_ID": "vertex-project",
                    "MYSTIC_PROVIDER_GOOGLE_VERTEX_LOCATION": "us-central1",
                },
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 113,
                    "method": "tools/call",
                    "params": {
                        "name": "provider_connect_start",
                        "arguments": {"provider_id": "google_vertex_ai", "auth_method": "oauth"},
                    },
                },
                "fetchResponses": [
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/provider_auth_flows", "status": 201, "body": [{}]},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/provider_connections", "status": 201, "body": [{}]},
                ],
            },
        )
        payload = result["body"]["result"]["structuredContent"]
        self.assertEqual(payload["status"], "oauth_required")
        self.assertIn("accounts.google.com/o/oauth2/v2/auth", payload["authorization_url"])
        self.assertNotIn("google-client-secret", json.dumps(payload))

    def test_provider_pages_and_secret_route_never_expose_secret_values(self) -> None:
        setup_result = run_worker_helper(
            "simulateRequest",
            {
                "env": {**self.env, "MYSTIC_PROVIDER_OPENAI_COMPAT_API_KEY": "sk-secret-live"},
                "requestUrl": "https://mystic.dexproject.workers.dev/providers/openai_compatible/setup",
                "method": "GET",
                "fetchResponses": [
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/provider_connections", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/provider_oauth_tokens", "status": 200, "body": []},
                ],
            },
        )
        secret_post = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": "https://mystic.dexproject.workers.dev/providers/openai_compatible/secret",
                "method": "POST",
                "headers": {"Content-Type": "application/json"},
                "rawBody": json.dumps({"secret_name": "MYSTIC_PROVIDER_OPENAI_COMPAT_API_KEY", "secret_value": "sk-secret-live"}),
                "fetchResponses": [
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/provider_connections", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/provider_oauth_tokens", "status": 200, "body": []},
                ],
            },
        )
        self.assertEqual(setup_result["status"], 200)
        self.assertIn("MYSTIC_PROVIDER_OPENAI_COMPAT_API_KEY", setup_result["body"])
        self.assertNotIn("sk-secret-live", setup_result["body"])
        self.assertEqual(secret_post["status"], 501)
        self.assertNotIn("sk-secret-live", json.dumps(secret_post["body"]))

    def test_provider_status_route_returns_safe_json(self) -> None:
        result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": "https://mystic.dexproject.workers.dev/providers/openai_compatible/status",
                "method": "GET",
                "fetchResponses": [
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/provider_connections", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/provider_oauth_tokens", "status": 200, "body": []},
                ],
            },
        )
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["body"]["provider_id"], "openai_compatible")
        self.assertIn("/providers/openai_compatible/setup", result["body"]["setup_url"])

    def test_google_vertex_callback_rejects_invalid_or_missing_state_without_exposing_code(self) -> None:
        mismatch_result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": "https://mystic.dexproject.workers.dev/providers/oauth/callback?provider_id=google_vertex_ai&flow_id=flow-1&state=wrong&code=secret-code",
                "method": "GET",
                "fetchResponses": [
                    {
                        "methodPrefix": "GET https://example.supabase.co/rest/v1/provider_auth_flows",
                        "status": 200,
                        "body": [
                            {
                                "flow_id": "flow-1",
                                "provider_id": "google_vertex_ai",
                                "auth_method": "oauth",
                                "status": "oauth_required",
                                "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?response_type=code",
                                "redirect_url": "https://mystic.dexproject.workers.dev/providers/oauth/callback?provider_id=google_vertex_ai",
                                "state": "",
                                "state_hash": "60e0b9b14540af0cbeb5255ac71b2f842c5130f748e3ae2358145d6d8d005c76",
                                "code_challenge": "challenge-1",
                                "code_challenge_method": "S256",
                                "callback_received_at": None,
                                "failure_reason": "",
                                "metadata": {},
                                "created_at": "2026-07-06T01:01:01Z",
                                "updated_at": "2026-07-06T01:01:01Z",
                            }
                        ],
                    },
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/provider_auth_flows", "status": 201, "body": [{}]},
                ],
            },
        )
        missing_state_result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": "https://mystic.dexproject.workers.dev/providers/oauth/callback?provider_id=google_vertex_ai&flow_id=flow-2&code=secret-code",
                "method": "GET",
                "fetchResponses": [
                    {
                        "methodPrefix": "GET https://example.supabase.co/rest/v1/provider_auth_flows",
                        "status": 200,
                        "body": [
                            {
                                "flow_id": "flow-2",
                                "provider_id": "google_vertex_ai",
                                "auth_method": "oauth",
                                "status": "oauth_required",
                                "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?response_type=code",
                                "redirect_url": "https://mystic.dexproject.workers.dev/providers/oauth/callback?provider_id=google_vertex_ai",
                                "state": "",
                                "state_hash": "60e0b9b14540af0cbeb5255ac71b2f842c5130f748e3ae2358145d6d8d005c76",
                                "code_challenge": "challenge-1",
                                "code_challenge_method": "S256",
                                "callback_received_at": None,
                                "failure_reason": "",
                                "metadata": {},
                                "created_at": "2026-07-06T01:01:01Z",
                                "updated_at": "2026-07-06T01:01:01Z",
                            }
                        ],
                    },
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/provider_auth_flows", "status": 201, "body": [{}]},
                ],
            },
        )
        self.assertEqual(mismatch_result["status"], 400)
        self.assertEqual(missing_state_result["status"], 400)
        self.assertNotIn("secret-code", mismatch_result["body"])
        self.assertNotIn("secret-code", missing_state_result["body"])

    def test_google_vertex_callback_returns_token_storage_required_without_encryption_key(self) -> None:
        result = run_worker_helper(
            "simulateRequest",
            {
                "env": {
                    **self.env,
                    "MYSTIC_PROVIDER_GOOGLE_VERTEX_OAUTH_ENABLED": "true",
                    "MYSTIC_PROVIDER_GOOGLE_VERTEX_CLIENT_ID": "google-client-id",
                    "MYSTIC_PROVIDER_GOOGLE_VERTEX_CLIENT_SECRET": "google-client-secret",
                    "MYSTIC_PROVIDER_GOOGLE_VERTEX_PROJECT_ID": "vertex-project",
                    "MYSTIC_PROVIDER_GOOGLE_VERTEX_LOCATION": "us-central1",
                },
                "requestUrl": "https://mystic.dexproject.workers.dev/providers/oauth/callback?provider_id=google_vertex_ai&flow_id=flow-3&state=good-state&code=secret-code",
                "method": "GET",
                "fetchResponses": [
                    {
                        "methodPrefix": "GET https://example.supabase.co/rest/v1/provider_auth_flows",
                        "status": 200,
                        "body": [
                            {
                                "flow_id": "flow-3",
                                "provider_id": "google_vertex_ai",
                                "auth_method": "oauth",
                                "status": "oauth_required",
                                "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?response_type=code",
                                "redirect_url": "https://mystic.dexproject.workers.dev/providers/oauth/callback?provider_id=google_vertex_ai",
                                "state": "",
                                "state_hash": "aab27fa344587b4fe185e55703daafbcf3934e06b04f920fdb13aa440c25468f",
                                "code_challenge": "challenge-1",
                                "code_challenge_method": "S256",
                                "callback_received_at": None,
                                "failure_reason": "",
                                "metadata": {},
                                "created_at": "2026-07-06T01:01:01Z",
                                "updated_at": "2026-07-06T01:01:01Z",
                            }
                        ],
                    },
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/provider_auth_flows", "status": 201, "body": [{}]},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/provider_connections", "status": 200, "body": []},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/provider_connections", "status": 201, "body": [{}]},
                ],
            },
        )
        self.assertEqual(result["status"], 200)
        self.assertIn("token_storage_required", result["body"])
        self.assertNotIn("secret-code", result["body"])
        self.assertNotIn("google-client-secret", result["body"])

    def test_google_vertex_callback_stores_encrypted_token_when_key_exists(self) -> None:
        result = run_worker_helper(
            "simulateRequest",
            {
                "env": {
                    **self.env,
                    "MYSTIC_PROVIDER_GOOGLE_VERTEX_OAUTH_ENABLED": "true",
                    "MYSTIC_PROVIDER_GOOGLE_VERTEX_CLIENT_ID": "google-client-id",
                    "MYSTIC_PROVIDER_GOOGLE_VERTEX_CLIENT_SECRET": "google-client-secret",
                    "MYSTIC_PROVIDER_GOOGLE_VERTEX_PROJECT_ID": "vertex-project",
                    "MYSTIC_PROVIDER_GOOGLE_VERTEX_LOCATION": "us-central1",
                    "MYSTIC_PROVIDER_TOKEN_ENCRYPTION_KEY": "provider-token-encryption-key",
                },
                "requestUrl": "https://mystic.dexproject.workers.dev/providers/oauth/callback?provider_id=google_vertex_ai&flow_id=flow-4&state=good-state&code=secret-code",
                "method": "GET",
                "fetchResponses": [
                    {
                        "methodPrefix": "GET https://example.supabase.co/rest/v1/provider_auth_flows",
                        "status": 200,
                        "body": [
                            {
                                "flow_id": "flow-4",
                                "provider_id": "google_vertex_ai",
                                "auth_method": "oauth",
                                "status": "oauth_required",
                                "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?response_type=code",
                                "redirect_url": "https://mystic.dexproject.workers.dev/providers/oauth/callback?provider_id=google_vertex_ai",
                                "state": "",
                                "state_hash": "aab27fa344587b4fe185e55703daafbcf3934e06b04f920fdb13aa440c25468f",
                                "code_challenge": "challenge-1",
                                "code_challenge_method": "S256",
                                "callback_received_at": None,
                                "failure_reason": "",
                                "metadata": {"code_verifier": "verifier-123"},
                                "created_at": "2026-07-06T01:01:01Z",
                                "updated_at": "2026-07-06T01:01:01Z",
                            }
                        ],
                    },
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/provider_auth_flows", "status": 201, "body": [{}]},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/provider_connections", "status": 200, "body": []},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/provider_connections", "status": 201, "body": [{}]},
                    {
                        "methodPrefix": "POST https://oauth2.googleapis.com/token",
                        "status": 200,
                        "body": {
                            "access_token": "vertex-access-token",
                            "refresh_token": "vertex-refresh-token",
                            "id_token": "vertex-id-token",
                            "token_type": "Bearer",
                            "scope": "openid profile https://www.googleapis.com/auth/cloud-platform",
                            "expires_in": 3600,
                        },
                    },
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/provider_oauth_tokens", "status": 200, "body": []},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/provider_oauth_tokens", "status": 201, "body": [{}]},
                ],
            },
        )
        self.assertEqual(result["status"], 200)
        self.assertIn("<code>connected</code>", result["body"])
        self.assertNotIn("vertex-access-token", result["body"])
        self.assertNotIn("vertex-refresh-token", result["body"])

    def test_cloud_gemini_remains_api_key_only_even_when_google_oauth_metadata_exists(self) -> None:
        result = run_worker_helper(
            "simulateRequest",
            {
                "env": {
                    **self.env,
                    "MYSTIC_PROVIDER_GEMINI_OAUTH_ENABLED": "true",
                    "MYSTIC_PROVIDER_GEMINI_CLIENT_ID": "legacy-google-client-id",
                    "MYSTIC_PROVIDER_GEMINI_CLIENT_SECRET": "legacy-google-client-secret",
                },
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 108,
                    "method": "tools/call",
                    "params": {"name": "provider_connect_start", "arguments": {"provider_id": "gemini", "auth_method": "oauth"}},
                },
                "fetchResponses": [
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/provider_connections", "status": 201, "body": [{}]},
                ],
            },
        )
        payload = result["body"]["result"]["structuredContent"]
        self.assertEqual(payload["status"], "api_key_required")
        self.assertEqual(payload["auth_method"], "api_key")
        self.assertNotIn("authorization_url", payload)
        self.assertNotIn("legacy-google-client-secret", json.dumps(payload))

    def test_cloud_provider_verify_disconnect_model_list_and_call_test_follow_foundation_contract(self) -> None:
        verify_result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 106,
                    "method": "tools/call",
                    "params": {"name": "provider_verify", "arguments": {"provider_id": "openai_compatible"}},
                },
                "fetchResponses": [
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/provider_connections", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/provider_oauth_tokens", "status": 200, "body": []},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/provider_connections", "status": 201, "body": [{}]},
                ],
            },
        )
        disconnect_result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 107,
                    "method": "tools/call",
                    "params": {"name": "provider_disconnect", "arguments": {"provider_id": "openai_compatible"}},
                },
                "fetchResponses": [
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/provider_connections", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/provider_oauth_tokens", "status": 200, "body": []},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/provider_connections", "status": 201, "body": [{}]},
                ],
            },
        )
        model_list_result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 108,
                    "method": "tools/call",
                    "params": {"name": "provider_model_list", "arguments": {"provider_id": "openai_compatible"}},
                },
                "fetchResponses": [
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/provider_connections", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/provider_oauth_tokens", "status": 200, "body": []},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/model_calls", "status": 201, "body": [{}]},
                ],
            },
        )
        call_test_result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 109,
                    "method": "tools/call",
                    "params": {
                        "name": "provider_call_test",
                        "arguments": {"provider_id": "openai_compatible", "prompt": "ping"},
                    },
                },
                "fetchResponses": [
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/provider_connections", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/provider_oauth_tokens", "status": 200, "body": []},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/model_calls", "status": 201, "body": [{}]},
                ],
            },
        )

        self.assertIn(
            verify_result["body"]["result"]["structuredContent"]["status"],
            {"not_configured", "api_key_required"},
        )
        self.assertEqual(disconnect_result["body"]["result"]["structuredContent"]["status"], "disconnected")
        self.assertIn(
            model_list_result["body"]["result"]["structuredContent"]["status"],
            {"not_configured", "api_key_required"},
        )
        self.assertIn(call_test_result["body"]["result"]["structuredContent"]["status"], {"provider_required", "api_key_required"})

    def test_cloud_google_vertex_verify_and_call_test_return_safe_oauth_states(self) -> None:
        verify_result = run_worker_helper(
            "simulateRequest",
            {
                "env": {
                    **self.env,
                    "MYSTIC_PROVIDER_GOOGLE_VERTEX_OAUTH_ENABLED": "true",
                    "MYSTIC_PROVIDER_GOOGLE_VERTEX_CLIENT_ID": "google-client-id",
                    "MYSTIC_PROVIDER_GOOGLE_VERTEX_CLIENT_SECRET": "google-client-secret",
                    "MYSTIC_PROVIDER_GOOGLE_VERTEX_PROJECT_ID": "vertex-project",
                    "MYSTIC_PROVIDER_GOOGLE_VERTEX_LOCATION": "us-central1",
                },
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 114,
                    "method": "tools/call",
                    "params": {"name": "provider_verify", "arguments": {"provider_id": "google_vertex_ai"}},
                },
                "fetchResponses": [
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/provider_connections", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/provider_oauth_tokens", "status": 200, "body": []},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/provider_connections", "status": 201, "body": [{}]},
                ],
            },
        )
        call_test_result = run_worker_helper(
            "simulateRequest",
            {
                "env": {
                    **self.env,
                    "MYSTIC_PROVIDER_GOOGLE_VERTEX_OAUTH_ENABLED": "true",
                    "MYSTIC_PROVIDER_GOOGLE_VERTEX_CLIENT_ID": "google-client-id",
                    "MYSTIC_PROVIDER_GOOGLE_VERTEX_CLIENT_SECRET": "google-client-secret",
                    "MYSTIC_PROVIDER_GOOGLE_VERTEX_PROJECT_ID": "vertex-project",
                    "MYSTIC_PROVIDER_GOOGLE_VERTEX_LOCATION": "us-central1",
                },
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 115,
                    "method": "tools/call",
                    "params": {
                        "name": "provider_call_test",
                        "arguments": {"provider_id": "google_vertex_ai", "prompt": "ping"},
                    },
                },
                "fetchResponses": [
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/provider_connections", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/provider_oauth_tokens", "status": 200, "body": []},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/model_calls", "status": 201, "body": [{}]},
                ],
            },
        )
        verify_payload = verify_result["body"]["result"]["structuredContent"]
        call_payload = call_test_result["body"]["result"]["structuredContent"]
        self.assertEqual(verify_payload["status"], "oauth_required")
        self.assertFalse(verify_payload["metadata"]["oauth_token_storage_supported"])
        self.assertEqual(call_payload["status"], "oauth_required")
        self.assertIn("/providers/google_vertex_ai/connect", call_payload["connect_url"])

    def test_cloud_google_vertex_verify_reports_connected_when_encrypted_token_exists(self) -> None:
        verify_result = run_worker_helper(
            "simulateRequest",
            {
                "env": {
                    **self.env,
                    "MYSTIC_PROVIDER_GOOGLE_VERTEX_OAUTH_ENABLED": "true",
                    "MYSTIC_PROVIDER_GOOGLE_VERTEX_CLIENT_ID": "google-client-id",
                    "MYSTIC_PROVIDER_GOOGLE_VERTEX_CLIENT_SECRET": "google-client-secret",
                    "MYSTIC_PROVIDER_GOOGLE_VERTEX_PROJECT_ID": "vertex-project",
                    "MYSTIC_PROVIDER_GOOGLE_VERTEX_LOCATION": "us-central1",
                    "MYSTIC_PROVIDER_TOKEN_ENCRYPTION_KEY": "provider-token-encryption-key",
                },
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 117,
                    "method": "tools/call",
                    "params": {"name": "provider_verify", "arguments": {"provider_id": "google_vertex_ai"}},
                },
                "fetchResponses": [
                    {
                        "methodPrefix": "GET https://example.supabase.co/rest/v1/provider_connections",
                        "status": 200,
                        "body": [self._provider_connection_row("google_vertex_ai", status="oauth_callback_received")],
                    },
                    {
                        "methodPrefix": "GET https://example.supabase.co/rest/v1/provider_oauth_tokens",
                        "status": 200,
                        "body": [
                            {
                                "token_id": "oauth-token-google_vertex_ai",
                                "provider_id": "google_vertex_ai",
                                "connection_id": "provider-google_vertex_ai",
                                "encrypted_access_token": "mlabtok_v1:abc:def:ghi",
                                "encrypted_refresh_token": "",
                                "encrypted_id_token": "",
                                "token_type": "Bearer",
                                "scope_hash": "scope-hash",
                                "expires_at": "2026-07-06T02:01:01Z",
                                "status": "connected",
                                "metadata_safe": {"refresh_token_present": False},
                                "created_at": "2026-07-06T01:01:01Z",
                                "updated_at": "2026-07-06T01:01:01Z",
                            }
                        ],
                    },
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/provider_connections", "status": 201, "body": [{}]},
                ],
            },
        )
        payload = verify_result["body"]["result"]["structuredContent"]
        self.assertEqual(payload["status"], "connected")
        self.assertTrue(payload["metadata"]["oauth_token_recorded"])
        self.assertNotIn("encrypted_access_token", json.dumps(payload))

    def test_cloud_gemini_provider_call_test_still_returns_api_key_required_when_missing(self) -> None:
        result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 116,
                    "method": "tools/call",
                    "params": {
                        "name": "provider_call_test",
                        "arguments": {"provider_id": "gemini", "prompt": "ping"},
                    },
                },
                "fetchResponses": [
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/provider_connections", "status": 200, "body": []},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/model_calls", "status": 201, "body": [{}]},
                ],
            },
        )
        payload = result["body"]["result"]["structuredContent"]
        self.assertEqual(payload["status"], "api_key_required")
        self.assertIn("/providers/gemini/setup", payload["setup_url"])

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
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_turns", "status": 201, "body": [{}]},
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
        session_row = self._session_row(session_id)
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
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_turns", "status": 201, "body": [{}]},
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

    def test_cloud_phase1_lab_session_advance_returns_auth_required_turn_without_provider(self) -> None:
        session_id = "lab-advance"
        session_row = self._session_row(session_id)
        result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 11,
                    "method": "tools/call",
                    "params": {
                        "name": "lab_session_advance",
                        "arguments": {"session_id": session_id, "max_steps": 2, "use_model_arena": False, "use_verifier": False},
                    },
                },
                "fetchResponses": [
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_sessions", "status": 200, "body": [session_row]},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_turns", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/claims", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/failures", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/memory_edges", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/reports", "status": 200, "body": []},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_sessions", "status": 201, "body": [{}]},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_turns", "status": 201, "body": [{}]},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/lab_turns", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/claims", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/failures", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/memory_edges", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/reports", "status": 204},
                ],
            },
        )
        payload = result["body"]["result"]["structuredContent"]
        self.assertEqual(payload["updated_session"]["status"], "waiting_for_user")
        self.assertGreaterEqual(len(payload["new_turns"]), 2)
        self.assertEqual(payload["new_turns"][-1]["status"], "AUTH_REQUIRED")

    def test_cloud_phase1_lab_agent_run_returns_provider_required_turn(self) -> None:
        session_id = "lab-agent"
        session_row = self._session_row(session_id)
        result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 12,
                    "method": "tools/call",
                    "params": {
                        "name": "lab_agent_run",
                        "arguments": {
                            "session_id": session_id,
                            "agent_role": "Theorist",
                            "provider": "auto",
                            "task": "Scan the background assumptions.",
                            "context_ids": [],
                        },
                    },
                },
                "fetchResponses": [
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_sessions", "status": 200, "body": [session_row]},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_turns", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/claims", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/failures", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/memory_edges", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/reports", "status": 200, "body": []},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_sessions", "status": 201, "body": [{}]},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_turns", "status": 201, "body": [{}]},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/lab_turns", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/claims", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/failures", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/memory_edges", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/reports", "status": 204},
                ],
            },
        )
        payload = result["body"]["result"]["structuredContent"]
        self.assertEqual(payload["status"], "AUTH_REQUIRED")
        self.assertEqual(payload["provider_result"]["status"], "provider_required")

    def test_cloud_phase1_provider_call_test_maps_invalid_credentials_without_leaking_secret(self) -> None:
        env = {
            **self.env,
            "MYSTIC_PROVIDER_GEMINI_API_KEY": "gem-test-secret",
            "MYSTIC_PROVIDER_GEMINI_MODEL": "gemini-1.5-flash",
        }
        result = run_worker_helper(
            "simulateRequest",
            {
                "env": env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 120,
                    "method": "tools/call",
                    "params": {"name": "provider_call_test", "arguments": {"provider_id": "gemini", "prompt": "ping"}},
                },
                "fetchResponses": [
                    {
                        "methodPrefix": "POST https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent",
                        "status": 401,
                        "body": {"error": {"message": "bad gem-test-secret"}},
                    },
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/model_calls", "status": 201, "body": [{}]},
                ],
            },
        )
        payload = result["body"]["result"]["structuredContent"]
        self.assertEqual(payload["status"], "provider_auth_failed")
        self.assertNotIn("gem-test-secret", json.dumps(payload))

    def test_cloud_phase1_lab_agent_run_can_use_mock_provider_and_persist_model_call(self) -> None:
        session_id = "lab-agent-mock"
        session_row = self._session_row(session_id)
        result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 121,
                    "method": "tools/call",
                    "params": {
                        "name": "lab_agent_run",
                        "arguments": {
                            "session_id": session_id,
                            "agent_role": "Theorist",
                            "provider": "mock",
                            "task": "State one observation.",
                            "context_ids": [],
                        },
                    },
                },
                "fetchResponses": [
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_sessions", "status": 200, "body": [session_row]},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_turns", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/claims", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/failures", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/memory_edges", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/reports", "status": 200, "body": []},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/model_calls", "status": 201, "body": [{}]},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_sessions", "status": 201, "body": [{}]},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/lab_turns", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/claims", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/failures", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/memory_edges", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/reports", "status": 204},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_turns", "status": 201, "body": [{}]},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/claims", "status": 201, "body": [{}]},
                ],
            },
        )
        payload = result["body"]["result"]["structuredContent"]
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["provider_result"]["status"], "completed")

    def test_cloud_phase1_lab_referee_review_can_use_mock_provider(self) -> None:
        session_id = "lab-referee-mock"
        session_row = self._session_row(session_id)
        claim_row = {
            "session_id": session_id,
            "text": "A positive integer pair exists.",
            "claim_type": "result",
            "status": "HEURISTIC",
            "confidence": "low",
            "source_turn_id": "manual",
            "supporting_evidence": [],
            "refuting_evidence": [],
            "related_experiments": [],
            "related_failures": [],
            "created_at": "2026-07-06T01:02:01Z",
            "updated_at": "2026-07-06T01:02:01Z",
            "claim_id": "claim-1",
        }
        result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 122,
                    "method": "tools/call",
                    "params": {
                        "name": "lab_referee_review",
                        "arguments": {
                            "session_id": session_id,
                            "claim_id": "claim-1",
                            "text": "A positive integer pair exists.",
                            "strictness": "hostile",
                            "provider": "mock",
                        },
                    },
                },
                "fetchResponses": [
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_sessions", "status": 200, "body": [session_row]},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_turns", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/claims", "status": 200, "body": [claim_row]},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/failures", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/memory_edges", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/reports", "status": 200, "body": []},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/model_calls", "status": 201, "body": [{}]},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_sessions", "status": 201, "body": [{}]},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/lab_turns", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/claims", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/failures", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/memory_edges", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/reports", "status": 204},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_turns", "status": 201, "body": [{}]},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/claims", "status": 201, "body": [{}]},
                ],
            },
        )
        payload = result["body"]["result"]["structuredContent"]
        self.assertEqual(payload["provider_result"]["status"], "completed")
        self.assertIn(payload["verdict"], {"UNKNOWN", "VALID"})

    def test_cloud_phase1_lab_referee_review_returns_deferred_result(self) -> None:
        session_id = "lab-referee"
        session_row = self._session_row(session_id)
        result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 13,
                    "method": "tools/call",
                    "params": {
                        "name": "lab_referee_review",
                        "arguments": {
                            "session_id": session_id,
                            "text": "(2,4,8)",
                            "strictness": "hostile",
                        },
                    },
                },
                "fetchResponses": [
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_sessions", "status": 200, "body": [session_row]},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_turns", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/claims", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/failures", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/memory_edges", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/reports", "status": 200, "body": []},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_sessions", "status": 201, "body": [{}]},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_turns", "status": 201, "body": [{}]},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/lab_turns", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/claims", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/failures", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/memory_edges", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/reports", "status": 204},
                ],
            },
        )
        payload = result["body"]["result"]["structuredContent"]
        self.assertEqual(payload["verdict"], "DEFERRED")
        self.assertEqual(payload["deferred"]["status"], "deferred")

    def test_cloud_phase1_lab_memory_write_and_search_work(self) -> None:
        session_id = "lab-memory"
        session_row = self._session_row(session_id)
        write_result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 14,
                    "method": "tools/call",
                    "params": {
                        "name": "lab_memory_write",
                        "arguments": {
                            "session_id": session_id,
                            "kind": "claim",
                            "payload": {
                                "text": "A cloud-written claim",
                                "claim_type": "observation",
                                "status": "HEURISTIC",
                                "confidence": "low",
                                "source_turn_id": "manual",
                            },
                        },
                    },
                },
                "fetchResponses": [
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_sessions", "status": 200, "body": [session_row]},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_turns", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/claims", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/failures", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/memory_edges", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/reports", "status": 200, "body": []},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_sessions", "status": 201, "body": [{}]},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_turns", "status": 201, "body": [{}]},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/lab_turns", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/claims", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/failures", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/memory_edges", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/reports", "status": 204},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/claims", "status": 201, "body": [{}]},
                ],
            },
        )
        self.assertTrue(write_result["body"]["result"]["structuredContent"]["written_object_id"])

        session_row_with_claim = dict(session_row)
        session_row_with_claim["updated_at"] = "2026-07-06T01:02:01Z"
        search_result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 15,
                    "method": "tools/call",
                    "params": {"name": "lab_memory_search", "arguments": {"query": "cloud-written", "limit": 5}},
                },
                "fetchResponses": [
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_sessions", "status": 200, "body": [session_row_with_claim]},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_turns", "status": 200, "body": []},
                    {
                        "methodPrefix": "GET https://example.supabase.co/rest/v1/claims",
                        "status": 200,
                        "body": [
                            {
                                "session_id": session_id,
                                "text": "A cloud-written claim",
                                "claim_type": "observation",
                                "status": "HEURISTIC",
                                "confidence": "low",
                                "source_turn_id": "manual",
                                "supporting_evidence": [],
                                "refuting_evidence": [],
                                "related_experiments": [],
                                "related_failures": [],
                                "created_at": "2026-07-06T01:02:01Z",
                                "updated_at": "2026-07-06T01:02:01Z",
                                "claim_id": "claim-1",
                            }
                        ],
                    },
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/failures", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/memory_edges", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/reports", "status": 200, "body": []},
                ],
            },
        )
        payload = search_result["body"]["result"]["structuredContent"]
        self.assertEqual(payload["claims"][0]["claim_id"], "claim-1")

    def test_cloud_phase1_lab_experiment_create_and_run_return_deferred_execution(self) -> None:
        session_id = "lab-experiment"
        session_row = self._session_row(session_id)
        session_row["experiments_json"] = []
        create_result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 16,
                    "method": "tools/call",
                    "params": {
                        "name": "lab_experiment_create",
                        "arguments": {
                            "session_id": session_id,
                            "claim_id": "claim-1",
                            "question": "Test the cloud claim",
                            "method": "python_bruteforce",
                            "inputs": {"candidate_answer": "x=1"},
                        },
                    },
                },
                "fetchResponses": [
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_sessions", "status": 200, "body": [session_row]},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_turns", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/claims", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/failures", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/memory_edges", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/reports", "status": 200, "body": []},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_sessions", "status": 201, "body": [{}]},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_turns", "status": 201, "body": [{}]},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/lab_turns", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/claims", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/failures", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/memory_edges", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/reports", "status": 204},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/memory_edges", "status": 201, "body": [{}]},
                ],
            },
        )
        experiment_id = create_result["body"]["result"]["structuredContent"]["experiment_id"]
        session_row_with_experiment = self._session_row(session_id)
        session_row_with_experiment["experiments_json"] = [
            {
                "session_id": session_id,
                "claim_id": "claim-1",
                "question": "Test the cloud claim",
                "method": "python_bruteforce",
                "inputs": {"candidate_answer": "x=1"},
                "outputs": {},
                "tool_name": "",
                "verdict": "inconclusive",
                "evidence_summary": "",
                "created_at": "2026-07-06T01:01:01Z",
                "experiment_id": experiment_id,
            }
        ]
        run_result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 17,
                    "method": "tools/call",
                    "params": {
                        "name": "lab_experiment_run",
                        "arguments": {"session_id": session_id, "experiment_id": experiment_id},
                    },
                },
                "fetchResponses": [
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_sessions", "status": 200, "body": [session_row_with_experiment]},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_turns", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/claims", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/failures", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/memory_edges", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/reports", "status": 200, "body": []},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_sessions", "status": 201, "body": [{}]},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/lab_turns", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/claims", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/failures", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/memory_edges", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/reports", "status": 204},
                ],
            },
        )
        payload = run_result["body"]["result"]["structuredContent"]
        self.assertEqual(payload["deferred"]["status"], "deferred")
        self.assertEqual(payload["experiment_id"], experiment_id)

    def test_cloud_phase1_lab_models_debate_returns_api_key_required_when_unconfigured(self) -> None:
        session_id = "lab-debate"
        session_row = self._session_row(session_id)
        result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 18,
                    "method": "tools/call",
                    "params": {
                        "name": "lab_models_debate",
                        "arguments": {
                            "session_id": session_id,
                            "question": "Debate the claim",
                            "participants": ["openai_compatible"],
                            "rounds": ["independent_discovery"],
                            "use_existing_research_table": True,
                        },
                    },
                },
                "fetchResponses": [
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_sessions", "status": 200, "body": [session_row]},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_turns", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/claims", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/failures", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/memory_edges", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/reports", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/provider_connections", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/provider_oauth_tokens", "status": 200, "body": []},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_sessions", "status": 201, "body": [{}]},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_turns", "status": 201, "body": [{}]},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/lab_turns", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/claims", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/failures", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/memory_edges", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/reports", "status": 204},
                ],
            },
        )
        payload = result["body"]["result"]["structuredContent"]
        self.assertEqual(payload["provider_result"]["status"], "api_key_required")

    def test_cloud_phase1_lab_models_debate_can_use_mock_providers(self) -> None:
        session_id = "lab-debate-mock"
        session_row = self._session_row(session_id)
        result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 123,
                    "method": "tools/call",
                    "params": {
                        "name": "lab_models_debate",
                        "arguments": {
                            "session_id": session_id,
                            "question": "Debate whether x + y = 5 has positive integer solutions.",
                            "participants": ["mock:mock-one", "mock:mock-two"],
                            "rounds": ["independent_discovery", "cross_critique"],
                            "use_existing_research_table": True,
                        },
                    },
                },
                "fetchResponses": [
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_sessions", "status": 200, "body": [session_row]},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_turns", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/claims", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/failures", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/memory_edges", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/reports", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/provider_connections", "status": 200, "body": []},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/model_calls", "status": 201, "body": [{}]},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/model_calls", "status": 201, "body": [{}]},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/model_calls", "status": 201, "body": [{}]},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_sessions", "status": 201, "body": [{}]},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/lab_turns", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/claims", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/failures", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/memory_edges", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/reports", "status": 204},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_turns", "status": 201, "body": [{}]},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/claims", "status": 201, "body": [{}]},
                ],
            },
        )
        payload = result["body"]["result"]["structuredContent"]
        self.assertEqual(payload["research_table_session_id"], "")
        self.assertEqual(len(payload["transcript"]), 2)
        self.assertTrue(payload["final_synthesis"])

    def test_cloud_phase1_scene_crud_tools_use_supabase(self) -> None:
        session_id = "lab-scene"
        scene_id = "scene-123"
        session_row = self._session_row(session_id)
        create_result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 19,
                    "method": "tools/call",
                    "params": {
                        "name": "create_lab_scene",
                        "arguments": {
                            "session_id": session_id,
                            "title": "Projectile baseline",
                            "description": "Cloud scene",
                            "parameters": {"gravity": 9.81},
                        },
                    },
                },
                "fetchResponses": [
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_sessions", "status": 200, "body": [session_row]},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_turns", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/claims", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/failures", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/memory_edges", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/reports", "status": 200, "body": []},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_scenes", "status": 201, "body": [{}]},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/lab_scene_objects", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/lab_simulations", "status": 204},
                ],
            },
        )
        created_scene_id = create_result["body"]["result"]["structuredContent"]["scene_id"]
        scene_row = self._scene_row(created_scene_id, session_id)
        add_result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 20,
                    "method": "tools/call",
                    "params": {
                        "name": "add_lab_object",
                        "arguments": {
                            "scene_id": created_scene_id,
                            "object": {
                                "id": "ball-1",
                                "type": "rigid_body",
                                "label": "Projectile",
                                "position": {"x": 0, "y": 1, "z": 0},
                                "rotation": {"x": 0, "y": 0, "z": 0},
                                "scale": {"x": 1, "y": 1, "z": 1},
                                "geometry": {"kind": "sphere"},
                                "material": {"color": "#ff7a59"},
                                "data": {"mass": 0.2, "velocity": {"x": 5, "y": 8, "z": 0}},
                                "metadata": {"source": "test"},
                            },
                        },
                    },
                },
                "fetchResponses": [
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_scenes", "status": 200, "body": [scene_row]},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_scene_objects", "status": 200, "body": []},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_simulations", "status": 200, "body": []},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_scenes", "status": 201, "body": [{}]},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/lab_scene_objects", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/lab_simulations", "status": 204},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_scene_objects", "status": 201, "body": [{}]},
                ],
            },
        )
        object_row = {
            "scene_id": created_scene_id,
            "id": "ball-1",
            "type": "rigid_body",
            "label": "Projectile",
            "position": {"x": 0, "y": 1, "z": 0},
            "rotation": {"x": 0, "y": 0, "z": 0},
            "scale": {"x": 1, "y": 1, "z": 1},
            "geometry": {"kind": "sphere"},
            "material": {"color": "#ff7a59"},
            "data": {"mass": 0.2, "velocity": {"x": 5, "y": 8, "z": 0}},
            "metadata": {"source": "test"},
            "created_at": "2026-07-06T01:01:01Z",
            "updated_at": "2026-07-06T01:01:01Z",
        }
        update_result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 21,
                    "method": "tools/call",
                    "params": {
                        "name": "update_lab_object",
                        "arguments": {"scene_id": created_scene_id, "object_id": "ball-1", "patch": {"label": "Projectile A"}},
                    },
                },
                "fetchResponses": [
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_scenes", "status": 200, "body": [scene_row]},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_scene_objects", "status": 200, "body": [object_row]},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_simulations", "status": 200, "body": []},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_scenes", "status": 201, "body": [{}]},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/lab_scene_objects", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/lab_simulations", "status": 204},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_scene_objects", "status": 201, "body": [{}]},
                ],
            },
        )
        get_result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {"jsonrpc": "2.0", "id": 22, "method": "tools/call", "params": {"name": "get_lab_scene", "arguments": {"scene_id": created_scene_id}}},
                "fetchResponses": [
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_scenes", "status": 200, "body": [scene_row]},
                    {
                        "methodPrefix": "GET https://example.supabase.co/rest/v1/lab_scene_objects",
                        "status": 200,
                        "body": [{**object_row, "label": "Projectile A"}],
                    },
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_simulations", "status": 200, "body": []},
                ],
            },
        )
        remove_result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 23,
                    "method": "tools/call",
                    "params": {"name": "remove_lab_object", "arguments": {"scene_id": created_scene_id, "object_id": "ball-1"}},
                },
                "fetchResponses": [
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_scenes", "status": 200, "body": [scene_row]},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_scene_objects", "status": 200, "body": [object_row]},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_simulations", "status": 200, "body": []},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_scenes", "status": 201, "body": [{}]},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/lab_scene_objects", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/lab_simulations", "status": 204},
                ],
            },
        )

        self.assertTrue(created_scene_id.startswith("scene-"))
        self.assertEqual(add_result["body"]["result"]["structuredContent"]["object_id"], "ball-1")
        self.assertEqual(update_result["body"]["result"]["structuredContent"]["object"]["label"], "Projectile A")
        self.assertEqual(get_result["body"]["result"]["structuredContent"]["objects"][0]["label"], "Projectile A")
        self.assertEqual(remove_result["body"]["result"]["structuredContent"]["removed_object_id"], "ball-1")

    def test_cloud_phase1_scene_simulation_export_and_report_tools_work(self) -> None:
        session_id = "lab-scene-sim"
        scene_id = "scene-456"
        scene_row = self._scene_row(scene_id, session_id)
        object_row = {
            "scene_id": scene_id,
            "id": "ball-1",
            "type": "rigid_body",
            "label": "Projectile",
            "position": {"x": 0, "y": 1, "z": 0},
            "rotation": {"x": 0, "y": 0, "z": 0},
            "scale": {"x": 1, "y": 1, "z": 1},
            "geometry": {"kind": "sphere"},
            "material": {"color": "#ff7a59"},
            "data": {"mass": 0.2, "velocity": {"x": 4, "y": 6, "z": 0}},
            "metadata": {},
            "created_at": "2026-07-06T01:01:01Z",
            "updated_at": "2026-07-06T01:01:01Z",
        }
        math_fetch_responses = [
            {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_scenes", "status": 200, "body": [scene_row]},
            {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_scene_objects", "status": 200, "body": [object_row]},
            {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_simulations", "status": 200, "body": []},
            {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_scenes", "status": 201, "body": [{}]},
            {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/lab_scene_objects", "status": 204},
            {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/lab_simulations", "status": 204},
            {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_scene_objects", "status": 201, "body": [{}]},
            {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_simulations", "status": 201, "body": [{}]},
        ]
        math_result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 24,
                    "method": "tools/call",
                    "params": {
                        "name": "run_lab_simulation",
                        "arguments": {"scene_id": scene_id, "adapter_id": "math.sympy", "inputs": {"operation": "evaluate", "expression": "2^3 + 1"}},
                    },
                },
                "fetchResponses": math_fetch_responses,
            },
        )
        substitute_result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 29,
                    "method": "tools/call",
                    "params": {
                        "name": "run_lab_simulation",
                        "arguments": {
                            "scene_id": scene_id,
                            "adapter_id": "math.sympy",
                            "inputs": {"operation": "substitute", "expression": "2*x + y", "variables": {"x": 3, "y": 4}},
                        },
                    },
                },
                "fetchResponses": math_fetch_responses,
            },
        )
        solve_result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 30,
                    "method": "tools/call",
                    "params": {
                        "name": "run_lab_simulation",
                        "arguments": {
                            "scene_id": scene_id,
                            "adapter_id": "math.sympy",
                            "inputs": {"operation": "solve_linear", "equation": "2*x + 3 = 7", "variable": "x"},
                        },
                    },
                },
                "fetchResponses": math_fetch_responses,
            },
        )
        unsupported_result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 31,
                    "method": "tools/call",
                    "params": {
                        "name": "run_lab_simulation",
                        "arguments": {
                            "scene_id": scene_id,
                            "adapter_id": "math.sympy",
                            "inputs": {"operation": "evaluate", "expression": "sqrt(9)"},
                        },
                    },
                },
                "fetchResponses": math_fetch_responses,
            },
        )
        projectile_result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 25,
                    "method": "tools/call",
                    "params": {
                        "name": "run_lab_simulation",
                        "arguments": {
                            "scene_id": scene_id,
                            "adapter_id": "physics.simple_projectile",
                            "inputs": {"object_id": "ball-1", "duration": 1.0, "time_step": 0.25},
                        },
                    },
                },
                "fetchResponses": [
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_scenes", "status": 200, "body": [scene_row]},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_scene_objects", "status": 200, "body": [object_row]},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_simulations", "status": 200, "body": []},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_scenes", "status": 201, "body": [{}]},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/lab_scene_objects", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/lab_simulations", "status": 204},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_scene_objects", "status": 201, "body": [{}]},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_simulations", "status": 201, "body": [{}]},
                ],
            },
        )
        simulation_id = projectile_result["body"]["result"]["structuredContent"]["simulation_id"]
        simulation_row = {
            "simulation_id": simulation_id,
            "scene_id": scene_id,
            "session_id": session_id,
            "adapter_id": "physics.simple_projectile",
            "status": "completed",
            "inputs": {"object_id": "ball-1", "duration": 1.0, "time_step": 0.25},
            "outputs": {
                "object_id": "ball-1",
                "trajectory": [{"time": 0.0, "position": {"x": 0, "y": 1, "z": 0}, "velocity": {"x": 4, "y": 6, "z": 0}}],
                "final_position": {"x": 4, "y": 2, "z": 0},
                "final_velocity": {"x": 4, "y": -3.81, "z": 0},
                "max_height": 2.0,
                "duration_used": 1.0,
            },
            "evidence": {"equations": ["p = p0 + vt + 0.5at^2"]},
            "warnings": [],
            "errors": [],
            "attached_object_ids": ["ball-1"],
            "metadata": {"engine_status": "completed", "scene_adapter": "scene.three_json"},
            "created_at": "2026-07-06T01:01:01Z",
            "updated_at": "2026-07-06T01:01:01Z",
        }
        attach_result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 26,
                    "method": "tools/call",
                    "params": {
                        "name": "attach_simulation_to_scene",
                        "arguments": {
                            "scene_id": scene_id,
                            "simulation_id": simulation_id,
                            "object_ids": ["ball-1"],
                            "evidence_refs": [],
                            "report_refs": [],
                            "apply_object_updates": True,
                        },
                    },
                },
                "fetchResponses": [
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_scenes", "status": 200, "body": [scene_row]},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_scene_objects", "status": 200, "body": [object_row]},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_simulations", "status": 200, "body": [simulation_row]},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_scenes", "status": 201, "body": [{}]},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/lab_scene_objects", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/lab_simulations", "status": 204},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_scene_objects", "status": 201, "body": [{}]},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_simulations", "status": 201, "body": [{}]},
                ],
            },
        )
        export_result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 27,
                    "method": "tools/call",
                    "params": {
                        "name": "export_lab_snapshot",
                        "arguments": {"scene_id": scene_id, "adapter_id": "scene.three_json", "include_simulations": True},
                    },
                },
                "fetchResponses": [
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_scenes", "status": 200, "body": [scene_row]},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_scene_objects", "status": 200, "body": [object_row]},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_simulations", "status": 200, "body": [simulation_row]},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_scenes", "status": 201, "body": [{}]},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/lab_scene_objects", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/lab_simulations", "status": 204},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_scene_objects", "status": 201, "body": [{}]},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_simulations", "status": 201, "body": [{}]},
                ],
            },
        )
        report_result = run_worker_helper(
            "simulateRequest",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": self.auth_headers,
                "body": {
                    "jsonrpc": "2.0",
                    "id": 28,
                    "method": "tools/call",
                    "params": {
                        "name": "generate_lab_report",
                        "arguments": {
                            "scene_id": scene_id,
                            "format": "markdown",
                            "include_objects": True,
                            "include_simulations": True,
                        },
                    },
                },
                "fetchResponses": [
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_scenes", "status": 200, "body": [scene_row]},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_scene_objects", "status": 200, "body": [object_row]},
                    {"methodPrefix": "GET https://example.supabase.co/rest/v1/lab_simulations", "status": 200, "body": [simulation_row]},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_scenes", "status": 201, "body": [{}]},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/lab_scene_objects", "status": 204},
                    {"methodPrefix": "DELETE https://example.supabase.co/rest/v1/lab_simulations", "status": 204},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_scene_objects", "status": 201, "body": [{}]},
                    {"methodPrefix": "POST https://example.supabase.co/rest/v1/lab_simulations", "status": 201, "body": [{}]},
                ],
            },
        )

        self.assertEqual(math_result["body"]["result"]["structuredContent"]["status"], "completed")
        self.assertEqual(math_result["body"]["result"]["structuredContent"]["result"]["outputs"]["result"], 9)
        self.assertEqual(substitute_result["body"]["result"]["structuredContent"]["status"], "completed")
        self.assertEqual(substitute_result["body"]["result"]["structuredContent"]["result"]["outputs"]["result"], 10)
        self.assertEqual(solve_result["body"]["result"]["structuredContent"]["status"], "completed")
        self.assertEqual(solve_result["body"]["result"]["structuredContent"]["result"]["outputs"]["solution"], 2)
        self.assertEqual(unsupported_result["body"]["result"]["structuredContent"]["status"], "unsupported_expression")
        self.assertEqual(projectile_result["body"]["result"]["structuredContent"]["status"], "completed")
        self.assertEqual(attach_result["body"]["result"]["structuredContent"]["attached_object_ids"], ["ball-1"])
        self.assertEqual(export_result["body"]["result"]["structuredContent"]["status"], "completed")
        self.assertEqual(export_result["body"]["result"]["structuredContent"]["snapshot"]["scene"]["name"], "Projectile baseline")
        self.assertIn("Projectile baseline", report_result["body"]["result"]["structuredContent"]["markdown"])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from mystic.mcp.server import MysticMCPServer


class _StubToolbox:
    def mystic_status(self) -> dict:
        return {"ok": True}

    def health_check(self) -> dict:
        return {"status": "ok"}

    def mystic_verify_answer(self, **_: object) -> dict:
        return {"verdict": "VALID", "saved_artifact_path": "mystic_data/runs/verify.json"}

    def mystic_call_model(self, **_: object) -> dict:
        return {"status": "CRITIQUE_ONLY", "artifact_path": "mystic_data/runs/model.json"}

    def mystic_compare_models(self, **_: object) -> dict:
        return {"final_status": "VALID", "saved_artifact_path": "mystic_data/runs/compare.json"}

    def mystic_run_research_table(self, **_: object) -> dict:
        return {"final_status": "UNKNOWN", "saved_artifact_path": "mystic_data/research_table_sessions/test/session.json"}

    def lab_session_create(self, **_: object) -> dict:
        return {"session_id": "lab-test"}

    def lab_session_get(self, **_: object) -> dict:
        return {"session": {"session_id": "lab-test"}}

    def lab_session_advance(self, **_: object) -> dict:
        return {"updated_session": {"session_id": "lab-test"}}

    def lab_agent_run(self, **_: object) -> dict:
        return {"turn_id": "turn-1"}

    def lab_referee_review(self, **_: object) -> dict:
        return {"verdict": "UNKNOWN"}

    def lab_experiment_create(self, **_: object) -> dict:
        return {"experiment_id": "exp-1"}

    def lab_experiment_run(self, **_: object) -> dict:
        return {"experiment_id": "exp-1", "verdict": "inconclusive"}

    def lab_memory_search(self, **_: object) -> dict:
        return {"matching_sessions": []}

    def lab_memory_write(self, **_: object) -> dict:
        return {"written_object_id": "note"}

    def lab_models_debate(self, **_: object) -> dict:
        return {"research_table_session_id": "research-1"}

    def lab_report_generate(self, **_: object) -> dict:
        return {"report_path": "mystic_data/lab_sessions/lab-test/report.md"}

    def create_lab_scene(self, **_: object) -> dict:
        return {"scene_id": "scene-1"}

    def get_lab_scene(self, **_: object) -> dict:
        return {"scene": {"scene_id": "scene-1"}}

    def add_lab_object(self, **_: object) -> dict:
        return {"object_id": "obj-1"}

    def update_lab_object(self, **_: object) -> dict:
        return {"object_id": "obj-1"}

    def remove_lab_object(self, **_: object) -> dict:
        return {"removed_object_id": "obj-1"}

    def set_lab_parameters(self, **_: object) -> dict:
        return {"scene_id": "scene-1"}

    def run_lab_simulation(self, **_: object) -> dict:
        return {"simulation_id": "sim-1", "status": "completed"}

    def attach_simulation_to_scene(self, **_: object) -> dict:
        return {"simulation_id": "sim-1"}

    def export_lab_snapshot(self, **_: object) -> dict:
        return {"status": "completed"}

    def generate_lab_report(self, **_: object) -> dict:
        return {"report_path": "mystic_data/lab_scenes/scene-1/report.md"}

    def provider_list(self, **_: object) -> dict:
        return {"providers": []}

    def provider_status(self, **_: object) -> dict:
        return {"provider_id": "openai_compatible", "status": "not_configured"}

    def provider_connect_start(self, **_: object) -> dict:
        return {"provider_id": "openai_compatible", "status": "api_key_required"}

    def provider_connect_callback_status(self, **_: object) -> dict:
        return {"flow": {"flow_id": "flow-1", "status": "oauth_required"}}

    def provider_configure_secret_instructions(self, **_: object) -> dict:
        return {"provider_id": "openai_compatible", "secret_names": []}

    def provider_verify(self, **_: object) -> dict:
        return {"provider_id": "openai_compatible", "status": "not_configured"}

    def provider_disconnect(self, **_: object) -> dict:
        return {"provider_id": "openai_compatible", "status": "disconnected"}

    def provider_model_list(self, **_: object) -> dict:
        return {"provider_id": "openai_compatible", "model_list": []}

    def provider_call_test(self, **_: object) -> dict:
        return {"provider_id": "openai_compatible", "status": "provider_required"}


class MCPServerTests(unittest.TestCase):
    def test_initialize_returns_server_capabilities(self):
        server = MysticMCPServer(toolbox=_StubToolbox())
        response = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        assert response is not None
        self.assertEqual(response["result"]["serverInfo"]["name"], "mystic-mcp")
        self.assertIn("tools", response["result"]["capabilities"])

    def test_tools_list_exposes_mystic_tools(self):
        server = MysticMCPServer(toolbox=_StubToolbox())
        response = server.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        assert response is not None
        names = [tool["name"] for tool in response["result"]["tools"]]
        self.assertIn("mystic_status", names)
        self.assertIn("mystic_call_model", names)
        self.assertIn("mystic_run_research_table", names)
        self.assertEqual(
            names,
            [
                "mystic_status",
                "health_check",
                "mystic_verify_answer",
                "mystic_call_model",
                "mystic_compare_models",
                "mystic_run_research_table",
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

    def test_tools_call_returns_structured_content(self):
        server = MysticMCPServer(toolbox=_StubToolbox())
        response = server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "mystic_status", "arguments": {}},
            }
        )
        assert response is not None
        self.assertEqual(response["result"]["structuredContent"], {"ok": True})
        self.assertFalse(response["result"]["isError"])

    def test_tools_call_rejects_invalid_arguments_by_schema(self):
        server = MysticMCPServer(toolbox=_StubToolbox())
        response = server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "mystic_call_model",
                    "arguments": {"model_id": "local_raven", "role": "critique", "task": "Critique"},
                },
            }
        )
        assert response is not None
        self.assertEqual(response["error"]["code"], -32000)
        self.assertIn("$.problem is required", response["error"]["message"])

    def test_tools_call_allows_null_for_nullable_lab_fields(self):
        server = MysticMCPServer(toolbox=_StubToolbox())
        response = server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "lab_referee_review",
                    "arguments": {
                        "session_id": "lab-test",
                        "claim_id": None,
                        "text": "candidate text",
                        "strictness": "hostile",
                    },
                },
            }
        )
        assert response is not None
        self.assertEqual(response["result"]["structuredContent"], {"verdict": "UNKNOWN"})


if __name__ == "__main__":
    unittest.main()

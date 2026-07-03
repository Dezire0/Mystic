from __future__ import annotations

import unittest

from mystic.mcp.server import MysticMCPServer


class _StubToolbox:
    def mystic_status(self) -> dict:
        return {"ok": True}

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

    def test_handle_payload_supports_batch_requests_and_omits_notifications(self):
        server = MysticMCPServer(toolbox=_StubToolbox())
        response = server.handle_payload(
            [
                {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
                {"jsonrpc": "2.0", "id": 1, "method": "initialize"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            ]
        )
        assert response is not None
        self.assertIsInstance(response, list)
        self.assertEqual([item["id"] for item in response], [1, 2])

    def test_handle_payload_rejects_non_object_entries(self):
        server = MysticMCPServer(toolbox=_StubToolbox())
        response = server.handle_payload([{"jsonrpc": "2.0", "id": 1, "method": "ping"}, "bad-entry"])
        assert response is not None
        self.assertIsInstance(response, list)
        self.assertEqual(response[1]["error"]["code"], -32600)


if __name__ == "__main__":
    unittest.main()

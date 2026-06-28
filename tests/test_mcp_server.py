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


if __name__ == "__main__":
    unittest.main()

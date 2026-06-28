from __future__ import annotations

import unittest

from mystic.mcp.server import MysticMCPServer


class _StubToolbox:
    def mystic_status(self) -> dict:
        return {"ok": True}


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


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import sys
from typing import Any

from mystic.mcp.schemas import PUBLIC_TOOL_DEFINITIONS, PUBLIC_TOOL_NAMES, TOOL_SCHEMAS
from mystic.mcp.tools import MysticToolbox
from mystic.mcp.validation import validate_json_schema


class MysticMCPServer:
    def __init__(self, toolbox: MysticToolbox | None = None) -> None:
        self.toolbox = toolbox or MysticToolbox()
        self.server_info = {
            "name": "mystic-mcp",
            "version": "0.1.0",
        }

    def handle_request(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        method = payload.get("method")
        request_id = payload.get("id")

        if method == "notifications/initialized":
            return None
        if method == "initialize":
            return self._response(
                request_id,
                {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {"tools": {}},
                    "serverInfo": self.server_info,
                },
            )
        if method == "ping":
            return self._response(request_id, {})
        if method == "tools/list":
            return self._response(request_id, {"tools": PUBLIC_TOOL_DEFINITIONS})
        if method == "tools/call":
            params = payload.get("params", {})
            name = params.get("name")
            arguments = params.get("arguments", {})
            try:
                result = self._call_tool(str(name), dict(arguments))
            except Exception as exc:
                return self._error_response(request_id, code=-32000, message=str(exc))
            return self._response(
                request_id,
                {
                    "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}],
                    "structuredContent": result,
                    "isError": False,
                },
            )
        return self._error_response(request_id, code=-32601, message=f"Unknown method: {method}")

    def serve_stdio(self) -> int:
        for line in sys.stdin:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                self._write_message(self._error_response(None, code=-32700, message=str(exc)))
                continue
            response = self.handle_request(payload)
            if response is not None:
                self._write_message(response)
        return 0

    def _call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name not in PUBLIC_TOOL_NAMES:
            raise KeyError(f"Unknown tool: {name}")
        if not isinstance(arguments, dict):
            raise ValueError("Tool arguments must be a JSON object.")
        errors = validate_json_schema(arguments, TOOL_SCHEMAS[name])
        if errors:
            raise ValueError("Invalid params: " + "; ".join(errors))
        handler = getattr(self.toolbox, name, None)
        if handler is None:
            raise KeyError(f"Unknown tool: {name}")
        return handler(**arguments)

    @staticmethod
    def _response(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    @staticmethod
    def _error_response(request_id: Any, *, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}

    @staticmethod
    def _write_message(payload: dict[str, Any]) -> None:
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        sys.stdout.flush()

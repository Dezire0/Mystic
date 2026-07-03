from __future__ import annotations

import json
import logging
import sys
from typing import Any

from mystic.mcp.schemas import PUBLIC_TOOL_DEFINITIONS, PUBLIC_TOOL_NAMES, TOOL_SCHEMAS
from mystic.mcp.tools import MysticToolbox
from mystic.mcp.validation import validate_json_schema

logger = logging.getLogger(__name__)


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
            self._log_event(
                "tool_call_start",
                request_id=request_id,
                tool_name=name,
                argument_keys=sorted(arguments.keys()) if isinstance(arguments, dict) else [],
            )
            try:
                result = self._call_tool(str(name), dict(arguments))
            except Exception as exc:
                logger.exception(
                    "mcp_tool_call_failed tool_name=%s request_id=%s",
                    name,
                    request_id,
                )
                return self._error_response(request_id, code=-32000, message=str(exc))
            self._log_event(
                "tool_call_success",
                request_id=request_id,
                tool_name=name,
                result_keys=sorted(result.keys()) if isinstance(result, dict) else [],
            )
            return self._response(
                request_id,
                {
                    "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}],
                    "structuredContent": result,
                    "isError": False,
                },
            )
        return self._error_response(request_id, code=-32601, message=f"Unknown method: {method}")

    def handle_payload(self, payload: Any) -> dict[str, Any] | list[dict[str, Any]] | None:
        if isinstance(payload, list):
            if not payload:
                return self._error_response(None, code=-32600, message="Invalid Request")
            responses: list[dict[str, Any]] = []
            for item in payload:
                if not isinstance(item, dict):
                    responses.append(self._error_response(None, code=-32600, message="Invalid Request"))
                    continue
                response = self.handle_request(item)
                if response is not None:
                    responses.append(response)
            return responses or None
        if not isinstance(payload, dict):
            return self._error_response(None, code=-32600, message="Invalid Request")
        return self.handle_request(payload)

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
        normalized_arguments = self._normalize_optional_nulls(name, arguments)
        errors = validate_json_schema(normalized_arguments, TOOL_SCHEMAS[name])
        if errors:
            raise ValueError("Invalid params: " + "; ".join(errors))
        handler = getattr(self.toolbox, name, None)
        if handler is None:
            raise KeyError(f"Unknown tool: {name}")
        return handler(**normalized_arguments)

    @staticmethod
    def _log_event(event: str, **payload: Any) -> None:
        logger.info(
            "mcp_event %s",
            json.dumps({"event": event, **payload}, ensure_ascii=True, default=str),
        )

    @staticmethod
    def _normalize_optional_nulls(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        nullable_fields = {
            "lab_session_advance": {"target_phase"},
            "lab_referee_review": {"claim_id"},
            "lab_memory_search": {"domain", "status_filter"},
        }
        allowed = nullable_fields.get(name)
        if not allowed:
            return dict(arguments)
        normalized = dict(arguments)
        for field_name in allowed:
            if normalized.get(field_name) is None:
                normalized.pop(field_name, None)
        return normalized

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

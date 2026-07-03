from __future__ import annotations

import json
import tempfile
import unittest
from unittest.mock import patch

from mystic.mcp.schemas import PUBLIC_TOOL_DEFINITIONS
from scripts import check_chatgpt_action_discovery_compatibility as compatibility


def _mcp_success(request_id: int, result: dict[str, object]) -> dict[str, object]:
    return {"status": 200, "headers": {}, "body": {"jsonrpc": "2.0", "id": request_id, "result": result}}


class ChatGPTActionDiscoveryCompatibilityTests(unittest.TestCase):
    def test_valid_tool_descriptor_passes(self) -> None:
        tool = {
            "name": "health_check",
            "description": "Return current Mystic health.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            "securitySchemes": [{"type": "oauth2", "scopes": ["tools:read"]}],
        }
        summary = compatibility.evaluate_tool_descriptor(tool, set())
        self.assertEqual(summary["blockers"], [])

    def test_missing_description_fails(self) -> None:
        tool = {
            "name": "health_check",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            "securitySchemes": [{"type": "oauth2", "scopes": ["tools:read"]}],
        }
        summary = compatibility.evaluate_tool_descriptor(tool, set())
        self.assertIn("TOOL_MISSING_DESCRIPTION", summary["blockers"])

    def test_missing_input_schema_fails(self) -> None:
        tool = {
            "name": "health_check",
            "description": "Return current Mystic health.",
            "securitySchemes": [{"type": "oauth2", "scopes": ["tools:read"]}],
        }
        summary = compatibility.evaluate_tool_descriptor(tool, set())
        self.assertIn("TOOL_MISSING_INPUT_SCHEMA", summary["blockers"])

    def test_input_schema_without_object_type_fails(self) -> None:
        tool = {
            "name": "health_check",
            "description": "Return current Mystic health.",
            "inputSchema": {"type": "string"},
            "securitySchemes": [{"type": "oauth2", "scopes": ["tools:read"]}],
        }
        summary = compatibility.evaluate_tool_descriptor(tool, set())
        self.assertIn("INPUT_SCHEMA_NOT_OBJECT", summary["blockers"])

    def test_missing_properties_object_fails(self) -> None:
        tool = {
            "name": "health_check",
            "description": "Return current Mystic health.",
            "inputSchema": {"type": "object"},
            "securitySchemes": [{"type": "oauth2", "scopes": ["tools:read"]}],
        }
        summary = compatibility.evaluate_tool_descriptor(tool, set())
        self.assertIn("INPUT_SCHEMA_PROPERTIES_MISSING", summary["blockers"])

    def test_duplicate_tool_names_fail(self) -> None:
        seen = {"health_check"}
        tool = {
            "name": "health_check",
            "description": "Return current Mystic health.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            "securitySchemes": [{"type": "oauth2", "scopes": ["tools:read"]}],
        }
        summary = compatibility.evaluate_tool_descriptor(tool, seen)
        self.assertIn("DUPLICATE_TOOL_NAME", summary["blockers"])

    def test_unsupported_schema_constructs_fail(self) -> None:
        tool = {
            "name": "health_check",
            "description": "Return current Mystic health.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "mode": {
                        "anyOf": [{"type": "string"}, {"type": "integer"}],
                    }
                },
            },
            "securitySchemes": [{"type": "oauth2", "scopes": ["tools:read"]}],
        }
        summary = compatibility.evaluate_tool_descriptor(tool, set())
        self.assertIn("TOOL_SCHEMA_TOO_COMPLEX", summary["blockers"])

    def test_real_mystic_public_tool_descriptors_pass(self) -> None:
        seen: set[str] = set()
        summaries = [compatibility.evaluate_tool_descriptor(tool, seen) for tool in PUBLIC_TOOL_DEFINITIONS]
        self.assertTrue(summaries)
        for summary in summaries:
            self.assertEqual(summary["blockers"], [], msg=json.dumps(summary, indent=2))

    def test_bearer_token_not_written_to_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = compatibility.Path(temp_dir) / "summary.json"
            responses = {
                1: _mcp_success(1, {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}}}),
                2: _mcp_success(2, {"tools": PUBLIC_TOOL_DEFINITIONS}),
            }
            with patch.object(
                compatibility,
                "mcp_request",
                side_effect=lambda *args, **kwargs: responses[kwargs["request_id"]],
            ):
                report = compatibility.check_chatgpt_action_discovery_compatibility(
                    "https://mystic.dexproject.workers.dev/mcp",
                    bearer_token="secret-token",
                    timeout_seconds=5,
                    output_path=output_path,
                )
            self.assertTrue(report["likely_chatgpt_visible"])
            self.assertNotIn("secret-token", output_path.read_text(encoding="utf-8"))

    def test_missing_security_schemes_fail(self) -> None:
        tool = {
            "name": "health_check",
            "description": "Return current Mystic health.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        }
        summary = compatibility.evaluate_tool_descriptor(tool, set())
        self.assertIn("TOOL_SECURITY_SCHEMES_MISSING", summary["blockers"])


if __name__ == "__main__":
    unittest.main()

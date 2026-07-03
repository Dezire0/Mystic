from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_remote_mcp_lab_smoke import mcp_request, now_iso, validate_mcp_success

DEFAULT_SCHEMA_BYTE_LIMIT = 16_384
DEFAULT_PROTOCOL_VERSION = "2025-06-18"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check ChatGPT action discovery compatibility for a remote Mystic MCP endpoint.")
    parser.add_argument("--endpoint", required=True, help="Full MCP endpoint URL.")
    parser.add_argument("--bearer-token", default="", help="Bearer token for OAuth-protected /mcp access.")
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument(
        "--output",
        default="",
        help="Optional output path. Defaults to mystic_data/e2e/chatgpt_action_discovery/summary.json.",
    )
    return parser


def default_output_path(root_path: Path) -> Path:
    return root_path / "mystic_data" / "e2e" / "chatgpt_action_discovery" / "summary.json"


def write_json(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return payload


def request_headers(bearer_token: str) -> dict[str, str] | None:
    if not bearer_token:
        return None
    return {"Authorization": f"Bearer {bearer_token}"}


def initialize_request(endpoint: str, *, bearer_token: str, timeout_seconds: int) -> dict[str, Any]:
    return mcp_request(
        endpoint,
        request_id=1,
        method="initialize",
        params={
            "protocolVersion": DEFAULT_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "chatgpt-action-discovery-checker", "version": "1.0"},
        },
        timeout_seconds=timeout_seconds,
        headers=request_headers(bearer_token),
    )


def tools_list_request(endpoint: str, *, bearer_token: str, timeout_seconds: int) -> dict[str, Any]:
    return mcp_request(
        endpoint,
        request_id=2,
        method="tools/list",
        params={},
        timeout_seconds=timeout_seconds,
        headers=request_headers(bearer_token),
    )


def extract_tools(response: dict[str, Any]) -> list[dict[str, Any]]:
    body = response.get("body")
    if not isinstance(body, dict):
        return []
    result = body.get("result")
    if not isinstance(result, dict):
        return []
    tools = result.get("tools")
    if not isinstance(tools, list):
        return []
    return [tool for tool in tools if isinstance(tool, dict)]


def _collect_schema_constructs(schema: Any, flags: set[str]) -> None:
    if isinstance(schema, dict):
        for key, value in schema.items():
            if key in {"anyOf", "oneOf", "allOf", "const", "patternProperties", "$ref"}:
                flags.add(key)
            if key == "type" and isinstance(value, list) and "null" in value:
                flags.add("nullable")
            _collect_schema_constructs(value, flags)
    elif isinstance(schema, list):
        for value in schema:
            _collect_schema_constructs(value, flags)


def schema_constructs(schema: dict[str, Any] | None) -> list[str]:
    if not isinstance(schema, dict):
        return []
    flags: set[str] = set()
    _collect_schema_constructs(schema, flags)
    return sorted(flags)


def schema_property_keys(schema: dict[str, Any] | None) -> list[str]:
    if not isinstance(schema, dict):
        return []
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return []
    return sorted(str(key) for key in properties)


def tool_shape_summary(tool: dict[str, Any]) -> dict[str, Any]:
    schema = tool.get("inputSchema")
    if not isinstance(schema, dict):
        schema = tool.get("input_schema")
    schema_bytes = 0
    if isinstance(schema, dict):
        schema_bytes = len(json.dumps(schema, ensure_ascii=True, sort_keys=True).encode("utf-8"))
    return {
        "name": tool.get("name"),
        "title": tool.get("title"),
        "has_name": isinstance(tool.get("name"), str) and bool(tool.get("name")),
        "has_description": isinstance(tool.get("description"), str) and bool(tool.get("description")),
        "has_inputSchema": isinstance(schema, dict),
        "input_schema_key": "inputSchema" if "inputSchema" in tool else ("input_schema" if "input_schema" in tool else ""),
        "input_schema_type": schema.get("type") if isinstance(schema, dict) else None,
        "input_schema_properties_keys": schema_property_keys(schema if isinstance(schema, dict) else None),
        "input_schema_required": schema.get("required") if isinstance(schema, dict) else None,
        "schema_byte_size": schema_bytes,
        "schema_constructs": schema_constructs(schema if isinstance(schema, dict) else None),
        "has_annotations": "annotations" in tool,
        "has_meta": "_meta" in tool,
        "has_security_schemes": isinstance(tool.get("securitySchemes"), list),
    }


def evaluate_tool_descriptor(
    tool: dict[str, Any],
    seen_names: set[str],
    *,
    schema_byte_limit: int = DEFAULT_SCHEMA_BYTE_LIMIT,
    require_security_schemes: bool = True,
) -> dict[str, Any]:
    summary = tool_shape_summary(tool)
    blockers: list[str] = []
    warnings: list[str] = []

    name = tool.get("name")
    if not summary["has_name"]:
        blockers.append("TOOL_MISSING_NAME")
    elif name in seen_names:
        blockers.append("DUPLICATE_TOOL_NAME")
    else:
        seen_names.add(str(name))

    if not summary["has_description"]:
        blockers.append("TOOL_MISSING_DESCRIPTION")

    if not summary["has_inputSchema"]:
        blockers.append("TOOL_MISSING_INPUT_SCHEMA")
    else:
        schema = tool.get("inputSchema")
        if not isinstance(schema, dict):
            schema = tool.get("input_schema")
        if schema.get("type") != "object":
            blockers.append("INPUT_SCHEMA_NOT_OBJECT")
        properties = schema.get("properties")
        if not isinstance(properties, dict):
            blockers.append("INPUT_SCHEMA_PROPERTIES_MISSING")
        required = schema.get("required")
        if required is not None and not isinstance(required, list):
            blockers.append("INPUT_SCHEMA_REQUIRED_INVALID")
        constructs = summary["schema_constructs"]
        if constructs:
            blockers.append("TOOL_SCHEMA_TOO_COMPLEX")
            warnings.append("SCHEMA_USES_UNSUPPORTED_CONSTRUCTS")
        if int(summary["schema_byte_size"]) > schema_byte_limit:
            warnings.append("TOOL_SCHEMA_LARGE")

    if require_security_schemes and not summary["has_security_schemes"]:
        blockers.append("TOOL_SECURITY_SCHEMES_MISSING")

    try:
        json.dumps(tool, ensure_ascii=True)
    except TypeError:
        blockers.append("TOOL_DESCRIPTOR_NOT_JSON_SERIALIZABLE")

    summary["warnings"] = warnings
    summary["blockers"] = blockers
    return summary


def recommendations_from_blockers(blockers: list[str]) -> list[str]:
    mapping = {
        "MCP_INITIALIZE_FAILED": "Ensure the public /mcp endpoint can answer initialize over authenticated POST.",
        "MCP_TOOLS_LIST_FAILED": "Ensure the public /mcp endpoint can answer tools/list over authenticated POST.",
        "TOOL_MISSING_DESCRIPTION": "Add a non-empty description to every public tool.",
        "TOOL_MISSING_INPUT_SCHEMA": "Add an inputSchema object to every public tool.",
        "INPUT_SCHEMA_NOT_OBJECT": "Make every public tool inputSchema an object schema.",
        "INPUT_SCHEMA_PROPERTIES_MISSING": "Ensure every inputSchema has a properties object, even when empty.",
        "TOOL_SCHEMA_TOO_COMPLEX": "Remove anyOf/oneOf/allOf/nullable/const/patternProperties/$ref from public tool schemas.",
        "TOOL_SECURITY_SCHEMES_MISSING": "Declare per-tool securitySchemes so ChatGPT knows the OAuth policy for each action.",
        "DUPLICATE_TOOL_NAME": "Ensure all public tool names are unique.",
    }
    return [mapping[blocker] for blocker in blockers if blocker in mapping]


def check_chatgpt_action_discovery_compatibility(
    endpoint: str,
    *,
    bearer_token: str = "",
    timeout_seconds: int = 30,
    output_path: Path | None = None,
) -> dict[str, Any]:
    output_path = output_path or default_output_path(ROOT)
    report: dict[str, Any] = {
        "endpoint": endpoint,
        "checked_at": now_iso(),
        "tools_count": 0,
        "tool_names": [],
        "compatible_tools": [],
        "incompatible_tools": [],
        "warnings": [],
        "blockers": [],
        "likely_chatgpt_visible": False,
        "recommendations": [],
        "initialize_ok": False,
        "tools_list_ok": False,
        "tool_summaries": [],
    }

    initialize = initialize_request(endpoint, bearer_token=bearer_token, timeout_seconds=timeout_seconds)
    init_errors = validate_mcp_success(initialize, expected_id=1)
    if init_errors:
        report["blockers"].append("MCP_INITIALIZE_FAILED")
        report["warnings"].extend(init_errors)
        report["recommendations"] = recommendations_from_blockers(report["blockers"])
        return write_json(output_path, report)
    report["initialize_ok"] = True

    tools_list = tools_list_request(endpoint, bearer_token=bearer_token, timeout_seconds=timeout_seconds)
    tools_errors = validate_mcp_success(tools_list, expected_id=2)
    if tools_errors:
        report["blockers"].append("MCP_TOOLS_LIST_FAILED")
        report["warnings"].extend(tools_errors)
        report["recommendations"] = recommendations_from_blockers(report["blockers"])
        return write_json(output_path, report)
    report["tools_list_ok"] = True

    seen_names: set[str] = set()
    tools = extract_tools(tools_list)
    report["tools_count"] = len(tools)
    report["tool_names"] = [str(tool.get("name")) for tool in tools if isinstance(tool.get("name"), str)]

    for tool in tools:
        summary = evaluate_tool_descriptor(tool, seen_names)
        report["tool_summaries"].append(summary)
        if summary["blockers"]:
            report["incompatible_tools"].append({"name": summary["name"], "blockers": summary["blockers"]})
        else:
            report["compatible_tools"].append(summary["name"])
        report["warnings"].extend(summary["warnings"])
        report["blockers"].extend(summary["blockers"])

    report["warnings"] = sorted(set(report["warnings"]))
    report["blockers"] = sorted(set(report["blockers"]))
    report["recommendations"] = recommendations_from_blockers(report["blockers"])
    report["likely_chatgpt_visible"] = bool(report["tools_count"]) and not report["blockers"]
    return write_json(output_path, report)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_path = Path(args.output) if args.output else default_output_path(ROOT)
    report = check_chatgpt_action_discovery_compatibility(
        args.endpoint,
        bearer_token=args.bearer_token,
        timeout_seconds=args.timeout_seconds,
        output_path=output_path,
    )
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

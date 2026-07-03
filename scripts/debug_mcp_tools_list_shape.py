from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_chatgpt_action_discovery_compatibility import (
    default_output_path as compatibility_default_output_path,
    extract_tools,
    initialize_request,
    tool_shape_summary,
    tools_list_request,
    write_json,
)
from scripts.run_remote_mcp_lab_smoke import now_iso, validate_mcp_success


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Print a redacted summary of Mystic MCP tools/list descriptors.")
    parser.add_argument("--endpoint", required=True, help="Full MCP endpoint URL.")
    parser.add_argument("--bearer-token", default="", help="Bearer token for OAuth-protected /mcp access.")
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument(
        "--output",
        default="",
        help="Optional output path. Defaults to mystic_data/e2e/chatgpt_action_discovery/tools_list_shape.json.",
    )
    parser.add_argument("--verbose-redacted", action="store_true", help="Include the redacted raw tools/list payload.")
    return parser


def default_output_path(root_path: Path) -> Path:
    return compatibility_default_output_path(root_path).with_name("tools_list_shape.json")


def debug_mcp_tools_list_shape(
    endpoint: str,
    *,
    bearer_token: str = "",
    timeout_seconds: int = 30,
    output_path: Path | None = None,
    verbose_redacted: bool = False,
) -> dict[str, Any]:
    output_path = output_path or default_output_path(ROOT)
    report: dict[str, Any] = {
        "endpoint": endpoint,
        "checked_at": now_iso(),
        "initialize_ok": False,
        "tools_list_ok": False,
        "tools_count": 0,
        "tool_names": [],
        "tools": [],
        "errors": [],
    }

    initialize = initialize_request(endpoint, bearer_token=bearer_token, timeout_seconds=timeout_seconds)
    initialize_errors = validate_mcp_success(initialize, expected_id=1)
    if initialize_errors:
        report["errors"].extend(initialize_errors)
        return write_json(output_path, report)
    report["initialize_ok"] = True
    report["initialize_result"] = initialize.get("body", {}).get("result", {})

    tools_list = tools_list_request(endpoint, bearer_token=bearer_token, timeout_seconds=timeout_seconds)
    tools_errors = validate_mcp_success(tools_list, expected_id=2)
    if tools_errors:
        report["errors"].extend(tools_errors)
        return write_json(output_path, report)
    report["tools_list_ok"] = True

    tools = extract_tools(tools_list)
    report["tools_count"] = len(tools)
    report["tool_names"] = [str(tool.get("name")) for tool in tools if isinstance(tool.get("name"), str)]
    report["tools"] = [tool_shape_summary(tool) for tool in tools]
    if verbose_redacted:
        report["tools_list_result"] = {
            "tools": [
                {
                    "name": tool.get("name"),
                    "title": tool.get("title"),
                    "description": tool.get("description"),
                    "inputSchema": tool.get("inputSchema", tool.get("input_schema")),
                    "securitySchemes": tool.get("securitySchemes"),
                    "annotations": tool.get("annotations"),
                    "_meta": tool.get("_meta"),
                }
                for tool in tools
            ]
        }
    return write_json(output_path, report)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_path = Path(args.output) if args.output else default_output_path(ROOT)
    report = debug_mcp_tools_list_shape(
        args.endpoint,
        bearer_token=args.bearer_token,
        timeout_seconds=args.timeout_seconds,
        output_path=output_path,
        verbose_redacted=args.verbose_redacted,
    )
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

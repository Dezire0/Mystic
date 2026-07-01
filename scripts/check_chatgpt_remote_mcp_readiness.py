from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_remote_mcp_lab_smoke import (
    LAB_TOOLS,
    auth_status_from_response,
    base_url_from_endpoint,
    extract_tool_names,
    http_json_request,
    mcp_request,
    now_iso,
    validate_mcp_success,
)


DEFAULT_PUBLIC_ENDPOINT = "https://mystic.dexproject.workers.dev"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check whether Mystic is import-ready as a ChatGPT remote MCP server.")
    parser.add_argument("--public-endpoint", default=DEFAULT_PUBLIC_ENDPOINT, help="Public Mystic base URL or /mcp URL.")
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument(
        "--output",
        default="",
        help="Optional output path. Defaults to mystic_data/e2e/remote_mcp_lab_smoke/chatgpt_remote_mcp_readiness.json.",
    )
    return parser


def default_output_path(root_path: Path) -> Path:
    return root_path / "mystic_data" / "e2e" / "remote_mcp_lab_smoke" / "chatgpt_remote_mcp_readiness.json"


def write_json(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return payload


def _protected_resource_metadata_url(public_endpoint: str) -> str:
    base_url = base_url_from_endpoint(public_endpoint)
    return f"{base_url.rstrip('/')}/.well-known/oauth-protected-resource"


def _oauth_authorization_server_url(auth_server: str) -> str:
    return f"{auth_server.rstrip('/')}/.well-known/oauth-authorization-server"


def _openid_configuration_url(auth_server: str) -> str:
    return f"{auth_server.rstrip('/')}/.well-known/openid-configuration"


def _looks_like_oauth_metadata(body: Any) -> bool:
    return (
        isinstance(body, dict)
        and isinstance(body.get("resource"), str)
        and isinstance(body.get("authorization_servers"), list)
        and bool(body.get("authorization_servers"))
    )


def _looks_like_auth_server_metadata(body: Any) -> bool:
    return (
        isinstance(body, dict)
        and isinstance(body.get("authorization_endpoint"), str)
        and isinstance(body.get("token_endpoint"), str)
    )


def _check_oauth_configuration(public_endpoint: str, timeout_seconds: int) -> tuple[bool, list[str]]:
    warnings: list[str] = []
    protected_resource = http_json_request(
        _protected_resource_metadata_url(public_endpoint),
        method="GET",
        timeout_seconds=timeout_seconds,
    )
    if int(protected_resource.get("status") or 0) != 200 or not _looks_like_oauth_metadata(protected_resource.get("body")):
        warnings.append("Protected resource metadata is missing or invalid.")
        return False, warnings

    authorization_servers = protected_resource["body"]["authorization_servers"]
    for auth_server in authorization_servers:
        oauth_metadata = http_json_request(
            _oauth_authorization_server_url(str(auth_server)),
            method="GET",
            timeout_seconds=timeout_seconds,
        )
        if int(oauth_metadata.get("status") or 0) == 200 and _looks_like_auth_server_metadata(oauth_metadata.get("body")):
            return True, warnings

        openid_metadata = http_json_request(
            _openid_configuration_url(str(auth_server)),
            method="GET",
            timeout_seconds=timeout_seconds,
        )
        if int(openid_metadata.get("status") or 0) == 200 and _looks_like_auth_server_metadata(openid_metadata.get("body")):
            return True, warnings

    warnings.append("Authorization server discovery metadata is missing or invalid.")
    return False, warnings


def check_chatgpt_remote_mcp_readiness(
    public_endpoint: str,
    *,
    timeout_seconds: int = 30,
    output_path: Path | None = None,
) -> dict[str, Any]:
    endpoint = public_endpoint.rstrip("/")
    if not endpoint.endswith("/mcp"):
        endpoint = f"{endpoint}/mcp"
    base_url = base_url_from_endpoint(endpoint)

    report: dict[str, Any] = {
        "public_endpoint": base_url,
        "health_ok": False,
        "mcp_initialize_ok": False,
        "tools_list_ok": False,
        "lab_tools_visible": False,
        "oauth_configured": False,
        "oauth_required": False,
        "import_ready": False,
        "blockers": [],
        "next_actions": [],
        "checked_at": now_iso(),
    }

    health = http_json_request(f"{base_url}/health", method="GET", timeout_seconds=timeout_seconds)
    if int(health.get("status") or 0) == 200 and health.get("body") == {"status": "ok"}:
        report["health_ok"] = True
    else:
        report["blockers"].append("HEALTHCHECK_FAILED")
        report["next_actions"].append("Ensure the public Worker and local Mystic backend both serve GET /health.")

    initialize = mcp_request(endpoint, request_id=1, method="initialize", timeout_seconds=timeout_seconds)
    auth_required, oauth_required = auth_status_from_response(initialize)
    report["oauth_required"] = oauth_required

    if initialize.get("status") is None:
        report["blockers"].append("MCP_UNREACHABLE")
        report["next_actions"].append("Expose the public /mcp endpoint and verify it accepts MCP JSON-RPC POST requests.")
    elif auth_required:
        report["blockers"].append("MCP_AUTH_REQUIRED")
        report["mcp_initialize_ok"] = False
    else:
        initialize_errors = validate_mcp_success(initialize, expected_id=1)
        if initialize_errors:
            report["blockers"].append("MCP_INITIALIZE_FAILED")
            report["next_actions"].append("Fix MCP initialize so the public endpoint returns a valid JSON-RPC success result.")
        else:
            report["mcp_initialize_ok"] = True

    tools_list = mcp_request(endpoint, request_id=2, method="tools/list", timeout_seconds=timeout_seconds)
    tools_errors = validate_mcp_success(tools_list, expected_id=2)
    if tools_errors:
        report["blockers"].append("TOOLS_LIST_FAILED")
        report["next_actions"].append("Fix tools/list on the public MCP endpoint.")
    else:
        report["tools_list_ok"] = True
        tool_names = extract_tool_names(tools_list)
        report["lab_tools_visible"] = LAB_TOOLS.issubset(tool_names)
        if not report["lab_tools_visible"]:
            report["blockers"].append("LAB_TOOLS_NOT_VISIBLE")
            report["next_actions"].append("Expose lab_* tools from tools/list on the public MCP endpoint.")

    oauth_configured, oauth_warnings = _check_oauth_configuration(base_url, timeout_seconds)
    report["oauth_configured"] = oauth_configured
    if not oauth_configured:
        report["blockers"].append("OAUTH_NOT_CONFIGURED")
        report["next_actions"].append(
            "Add /.well-known/oauth-protected-resource and OAuth authorization server discovery metadata before attempting ChatGPT import."
        )
    for warning in oauth_warnings:
        if warning not in report["next_actions"]:
            report["next_actions"].append(warning)

    report["blockers"] = list(dict.fromkeys(report["blockers"]))
    report["next_actions"] = list(dict.fromkeys(report["next_actions"]))
    report["import_ready"] = (
        report["health_ok"]
        and report["mcp_initialize_ok"]
        and report["tools_list_ok"]
        and report["lab_tools_visible"]
        and report["oauth_configured"]
    )

    destination = output_path or default_output_path(ROOT)
    return write_json(destination, report)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_path = Path(args.output) if args.output else default_output_path(ROOT)
    report = check_chatgpt_remote_mcp_readiness(
        args.public_endpoint,
        timeout_seconds=args.timeout_seconds,
        output_path=output_path,
    )
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0 if report["import_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

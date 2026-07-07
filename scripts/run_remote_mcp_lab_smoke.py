from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


EXISTING_TOOLS = {
    "mystic_status",
    "health_check",
}

LAB_TOOLS = {
    "lab_session_create",
    "lab_session_get",
    "lab_report_generate",
}

OPTIONAL_LAB_TOOLS = {
    "lab_session_advance",
    "lab_referee_review",
}

READY_LOCAL = "READY_LOCAL_MCP_LAB"
READY_PUBLIC = "READY_PUBLIC_MCP_LAB"
AUTH_REQUIRED = "AUTH_REQUIRED"
OAUTH_REQUIRED = "OAUTH_REQUIRED_FOR_CHATGPT_IMPORT"
MISSING_LAB_TOOLS = "MISSING_LAB_TOOLS"
MCP_PROTOCOL_ERROR = "MCP_PROTOCOL_ERROR"
BACKEND_UNREACHABLE = "BACKEND_UNREACHABLE"
FAILED = "FAILED"


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run MCP lab smoke checks against a local or public Mystic MCP endpoint.")
    parser.add_argument("--endpoint", required=True, help="Full MCP endpoint URL, such as http://127.0.0.1:8765/mcp.")
    parser.add_argument("--public-endpoint", default="", help="Optional public endpoint URL for reporting context.")
    parser.add_argument("--bearer-token", default="", help="Optional bearer token for OAuth-protected /mcp access.")
    parser.add_argument(
        "--auth-mode",
        default="none",
        choices=["none", "bearer", "expect-auth-required"],
        help="Authentication expectation for the endpoint under test.",
    )
    parser.add_argument(
        "--session-problem",
        default="Find all positive integer triples x <= y <= z such that 1/x + 1/y + 1/z = 1",
    )
    parser.add_argument("--domain", default="math")
    parser.add_argument("--mode", default="proof_critical")
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument(
        "--output",
        default="",
        help="Optional summary output path. Defaults to mystic_data/e2e/remote_mcp_lab_smoke/summary.json.",
    )
    parser.add_argument("--allow-auth-required", action="store_true")
    return parser


def base_url_from_endpoint(endpoint: str) -> str:
    value = endpoint.rstrip("/")
    if value.endswith("/mcp"):
        return value[:-4]
    return value


def default_output_path(root_path: Path) -> Path:
    return root_path / "mystic_data" / "e2e" / "remote_mcp_lab_smoke" / "summary.json"


def is_local_endpoint(endpoint: str) -> bool:
    hostname = urlparse(endpoint).hostname or ""
    return hostname in {"127.0.0.1", "localhost"}


def http_json_request(
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    method: str = "POST",
    timeout_seconds: int = 30,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request_headers = {"User-Agent": "Mystic Remote MCP Smoke", "Accept": "application/json"}
    if data is not None:
        request_headers["Content-Type"] = "application/json"
    if headers:
        request_headers.update(headers)
    request = Request(url, data=data, headers=request_headers, method=method)
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            body_text = response.read().decode("utf-8")
            body = json.loads(body_text) if body_text.strip() else None
            return {"ok": True, "status": response.status, "headers": dict(response.headers.items()), "body": body}
    except HTTPError as exc:
        body_text = exc.read().decode("utf-8")
        try:
            body = json.loads(body_text) if body_text.strip() else None
        except json.JSONDecodeError:
            body = {"raw": body_text}
        return {"ok": False, "status": exc.code, "headers": dict(exc.headers.items()), "body": body}
    except URLError as exc:
        return {"ok": False, "status": None, "headers": {}, "body": {"error": str(exc.reason)}}


def mcp_request(
    endpoint: str,
    *,
    request_id: int,
    method: str,
    params: dict[str, Any] | None = None,
    timeout_seconds: int = 30,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        payload["params"] = params
    return http_json_request(endpoint, payload=payload, timeout_seconds=timeout_seconds, headers=headers)


def auth_status_from_response(response: dict[str, Any]) -> tuple[bool, bool]:
    headers = {key.lower(): value for key, value in response.get("headers", {}).items()}
    if int(response.get("status") or 0) != 401:
        return False, False
    challenge = headers.get("www-authenticate", "")
    oauth_required = "resource_metadata=" in challenge or "bearer" in challenge.lower()
    return True, oauth_required


def extract_tool_names(response: dict[str, Any]) -> set[str]:
    body = response.get("body")
    if not isinstance(body, dict):
        return set()
    result = body.get("result")
    if not isinstance(result, dict):
        return set()
    tools = result.get("tools")
    if not isinstance(tools, list):
        return set()
    names: set[str] = set()
    for item in tools:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            names.add(item["name"])
    return names


def validate_mcp_success(response: dict[str, Any], *, expected_id: int | None = None) -> list[str]:
    errors: list[str] = []
    body = response.get("body")
    if int(response.get("status") or 0) != 200:
        errors.append(f"unexpected_http_status={response.get('status')}")
        return errors
    if not isinstance(body, dict):
        return ["response body is not a JSON object"]
    if body.get("jsonrpc") != "2.0":
        errors.append("jsonrpc version mismatch")
    if expected_id is not None and body.get("id") != expected_id:
        errors.append(f"response id mismatch: expected {expected_id}, got {body.get('id')}")
    if "error" in body:
        errors.append(f"jsonrpc error: {body['error']}")
    if "result" not in body:
        errors.append("missing result")
    return errors


def run_remote_mcp_lab_smoke(
    *,
    endpoint: str,
    public_endpoint: str = "",
    bearer_token: str = "",
    auth_mode: str = "none",
    session_problem: str,
    domain: str,
    mode: str,
    timeout_seconds: int,
    output_path: Path,
    allow_auth_required: bool = False,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "endpoint": endpoint,
        "public_endpoint": public_endpoint,
        "auth_mode": auth_mode,
        "checked_at": now_iso(),
        "initialize_ok": False,
        "tools_list_ok": False,
        "existing_tools_present": False,
        "lab_tools_present": False,
        "optional_lab_tools_present": False,
        "missing_tools": [],
        "session_created": False,
        "session_id": "",
        "advance_ok": None,
        "advance_supported": False,
        "get_ok": False,
        "report_ok": False,
        "persisted_paths": [],
        "auth_required": False,
        "oauth_required": False,
        "errors": [],
        "final_status": FAILED,
    }
    request_headers = {"Authorization": f"Bearer {bearer_token}"} if bearer_token else None
    if auth_mode == "bearer" and not bearer_token:
        summary["errors"].append("auth_mode=bearer requires --bearer-token")
        return write_summary(output_path, summary)

    initialize = mcp_request(
        endpoint,
        request_id=1,
        method="initialize",
        timeout_seconds=timeout_seconds,
        headers=request_headers,
    )
    if initialize.get("status") is None:
        summary["errors"].append(f"backend unreachable: {initialize.get('body', {}).get('error', 'unknown error')}")
        summary["final_status"] = BACKEND_UNREACHABLE
        return write_summary(output_path, summary)
    auth_required, oauth_required = auth_status_from_response(initialize)
    summary["auth_required"] = auth_required
    summary["oauth_required"] = oauth_required
    if auth_required:
        if not allow_auth_required:
            summary["errors"].append("endpoint requires authentication")
        summary["final_status"] = OAUTH_REQUIRED if oauth_required else AUTH_REQUIRED
        return write_summary(output_path, summary)
    if auth_mode == "expect-auth-required":
        summary["errors"].append("endpoint accepted unauthenticated MCP requests when auth-required behavior was expected")
        return write_summary(output_path, summary)

    errors = validate_mcp_success(initialize, expected_id=1)
    if errors:
        summary["errors"].extend(errors)
        summary["final_status"] = MCP_PROTOCOL_ERROR
        return write_summary(output_path, summary)
    summary["initialize_ok"] = True

    tools_list = mcp_request(
        endpoint,
        request_id=2,
        method="tools/list",
        timeout_seconds=timeout_seconds,
        headers=request_headers,
    )
    errors = validate_mcp_success(tools_list, expected_id=2)
    if errors:
        summary["errors"].extend(errors)
        summary["final_status"] = MCP_PROTOCOL_ERROR
        return write_summary(output_path, summary)
    summary["tools_list_ok"] = True
    tool_names = extract_tool_names(tools_list)
    missing_tools = sorted((EXISTING_TOOLS | LAB_TOOLS).difference(tool_names))
    summary["existing_tools_present"] = EXISTING_TOOLS.issubset(tool_names)
    summary["lab_tools_present"] = LAB_TOOLS.issubset(tool_names)
    summary["optional_lab_tools_present"] = OPTIONAL_LAB_TOOLS.issubset(tool_names)
    summary["missing_tools"] = missing_tools
    if not summary["lab_tools_present"]:
        summary["errors"].append("required lab tools are missing from tools/list")
        summary["final_status"] = MISSING_LAB_TOOLS
        return write_summary(output_path, summary)

    create_response = mcp_request(
        endpoint,
        request_id=3,
        method="tools/call",
        params={
            "name": "lab_session_create",
            "arguments": {
                "problem": session_problem,
                "domain": domain,
                "goal": "Prove external MCP clients can create and advance a real lab session.",
                "mode": mode,
                "participants": ["local_prime", "local_raven"],
            },
        },
        timeout_seconds=timeout_seconds,
        headers=request_headers,
    )
    errors = validate_mcp_success(create_response, expected_id=3)
    if errors:
        summary["errors"].extend(errors)
        summary["final_status"] = FAILED
        return write_summary(output_path, summary)
    create_payload = create_response["body"]["result"]["structuredContent"]
    session_id = str(create_payload.get("session_id", "")).strip()
    if not session_id:
        summary["errors"].append("lab_session_create did not return session_id")
        return write_summary(output_path, summary)
    summary["session_created"] = True
    summary["session_id"] = session_id
    if isinstance(create_payload.get("paths"), dict):
        summary["persisted_paths"].extend(str(value) for value in create_payload["paths"].values())

    if "lab_session_advance" in tool_names:
        summary["advance_supported"] = True
        advance_response = mcp_request(
            endpoint,
            request_id=4,
            method="tools/call",
            params={
                "name": "lab_session_advance",
                "arguments": {
                    "session_id": session_id,
                    "max_steps": 1,
                    "use_model_arena": False,
                    "use_verifier": True,
                },
            },
            timeout_seconds=timeout_seconds,
            headers=request_headers,
        )
        errors = validate_mcp_success(advance_response, expected_id=4)
        if errors:
            summary["errors"].extend(errors)
        else:
            advance_payload = advance_response["body"]["result"]["structuredContent"]
            summary["advance_ok"] = isinstance(advance_payload, dict) and "updated_session" in advance_payload
            if isinstance(advance_payload.get("paths"), dict):
                summary["persisted_paths"].extend(str(value) for value in advance_payload["paths"].values())

    get_response = mcp_request(
        endpoint,
        request_id=5,
        method="tools/call",
        params={"name": "lab_session_get", "arguments": {"session_id": session_id}},
        timeout_seconds=timeout_seconds,
        headers=request_headers,
    )
    errors = validate_mcp_success(get_response, expected_id=5)
    if errors:
        summary["errors"].extend(errors)
    else:
        get_payload = get_response["body"]["result"]["structuredContent"]
        summary["get_ok"] = isinstance(get_payload, dict) and get_payload.get("session", {}).get("session_id") == session_id
        for key in ("notebook_path", "report_path"):
            value = get_payload.get(key)
            if isinstance(value, str) and value:
                summary["persisted_paths"].append(value)

    report_response = mcp_request(
        endpoint,
        request_id=6,
        method="tools/call",
        params={
            "name": "lab_report_generate",
            "arguments": {
                "session_id": session_id,
                "format": "markdown",
                "include_failures": True,
                "include_next_actions": True,
            },
        },
        timeout_seconds=timeout_seconds,
        headers=request_headers,
    )
    errors = validate_mcp_success(report_response, expected_id=6)
    if errors:
        summary["errors"].extend(errors)
    else:
        report_payload = report_response["body"]["result"]["structuredContent"]
        summary["report_ok"] = isinstance(report_payload, dict) and bool(report_payload.get("report_path"))
        if isinstance(report_payload.get("report_path"), str):
            summary["persisted_paths"].append(report_payload["report_path"])

    persisted_paths = []
    for item in dict.fromkeys(summary["persisted_paths"]):
        if item:
            persisted_paths.append(item)
    summary["persisted_paths"] = persisted_paths
    if not persisted_paths:
        summary["errors"].append("no persisted artifact paths were returned")
    for path_text in persisted_paths:
        if "://" in path_text:
            continue
        if not Path(path_text).exists():
            summary["errors"].append(f"persisted path missing on disk: {path_text}")

    if summary["errors"]:
        summary["final_status"] = FAILED
    else:
        summary["final_status"] = READY_LOCAL if is_local_endpoint(endpoint) else READY_PUBLIC
    return write_summary(output_path, summary)


def write_summary(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_path = Path(args.output) if args.output else default_output_path(ROOT)
    summary = run_remote_mcp_lab_smoke(
        endpoint=args.endpoint,
        public_endpoint=args.public_endpoint,
        bearer_token=args.bearer_token,
        auth_mode=args.auth_mode,
        session_problem=args.session_problem,
        domain=args.domain,
        mode=args.mode,
        timeout_seconds=args.timeout_seconds,
        output_path=output_path,
        allow_auth_required=args.allow_auth_required,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=True))
    if summary["final_status"] in {READY_LOCAL, READY_PUBLIC}:
        return 0
    if args.allow_auth_required and summary["final_status"] in {AUTH_REQUIRED, OAUTH_REQUIRED}:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

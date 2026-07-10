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
    "lab_session_advance",
    "lab_agent_run",
    "lab_referee_review",
    "lab_experiment_create",
    "lab_experiment_run",
    "lab_memory_search",
    "lab_memory_write",
    "lab_models_debate",
    "lab_session_get",
    "lab_report_generate",
    "create_lab_scene",
    "get_lab_scene",
    "add_lab_object",
    "update_lab_object",
    "remove_lab_object",
    "set_lab_parameters",
    "run_lab_simulation",
    "attach_simulation_to_scene",
    "export_lab_snapshot",
    "generate_lab_report",
}

PROVIDER_CONNECT_TOOLS = {
    "provider_list",
    "provider_status",
    "provider_connect_start",
    "provider_connect_callback_status",
    "provider_configure_secret_instructions",
    "provider_verify",
    "provider_disconnect",
    "provider_model_list",
    "provider_call_test",
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


def extract_structured_content(response: dict[str, Any]) -> dict[str, Any]:
    body = response.get("body")
    if not isinstance(body, dict):
        return {}
    result = body.get("result")
    if not isinstance(result, dict):
        return {}
    payload = result.get("structuredContent")
    return payload if isinstance(payload, dict) else {}


def tool_status(value: Any) -> str:
    if isinstance(value, dict):
        status = value.get("status")
        if isinstance(status, str):
            return status
    return ""


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
        "missing_tools": [],
        "tool_names": [],
        "session_created": False,
        "session_id": "",
        "scene_created": False,
        "scene_id": "",
        "advance_supported": False,
        "advance_ok": None,
        "tool_calls": {},
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
    summary["tool_names"] = sorted(tool_names)
    expected_tools = EXISTING_TOOLS | LAB_TOOLS | PROVIDER_CONNECT_TOOLS
    missing_tools = sorted(expected_tools.difference(tool_names))
    summary["existing_tools_present"] = EXISTING_TOOLS.issubset(tool_names)
    summary["lab_tools_present"] = (LAB_TOOLS | PROVIDER_CONNECT_TOOLS).issubset(tool_names)
    summary["missing_tools"] = missing_tools
    if not summary["lab_tools_present"]:
        summary["errors"].append("required lab tools are missing from tools/list")
        summary["final_status"] = MISSING_LAB_TOOLS
        return write_summary(output_path, summary)

    mystic_status_response = mcp_request(
        endpoint,
        request_id=3,
        method="tools/call",
        params={"name": "mystic_status", "arguments": {}},
        timeout_seconds=timeout_seconds,
        headers=request_headers,
    )
    errors = validate_mcp_success(mystic_status_response, expected_id=3)
    if errors:
        summary["errors"].extend(errors)
    else:
        payload = extract_structured_content(mystic_status_response)
        summary["tool_calls"]["mystic_status"] = {
            "ok": bool(payload.get("runtime_mode")),
            "status": tool_status(payload),
            "runtime_mode": payload.get("runtime_mode", ""),
        }

    health_response = mcp_request(
        endpoint,
        request_id=4,
        method="tools/call",
        params={"name": "health_check", "arguments": {}},
        timeout_seconds=timeout_seconds,
        headers=request_headers,
    )
    errors = validate_mcp_success(health_response, expected_id=4)
    if errors:
        summary["errors"].extend(errors)
    else:
        payload = extract_structured_content(health_response)
        summary["tool_calls"]["health_check"] = {
            "ok": payload.get("status") == "ok",
            "status": tool_status(payload),
        }

    create_response = mcp_request(
        endpoint,
        request_id=5,
        method="tools/call",
        params={
            "name": "lab_session_create",
            "arguments": {
                "problem": session_problem,
                "domain": domain,
                "goal": "Prove external MCP clients can create and operate a real cloud-native lab session.",
                "mode": mode,
                "participants": ["local_prime", "local_raven"],
            },
        },
        timeout_seconds=timeout_seconds,
        headers=request_headers,
    )
    errors = validate_mcp_success(create_response, expected_id=5)
    if errors:
        summary["errors"].extend(errors)
        summary["final_status"] = FAILED
        return write_summary(output_path, summary)
    create_payload = extract_structured_content(create_response)
    session_id = str(create_payload.get("session_id", "")).strip()
    if not session_id:
        summary["errors"].append("lab_session_create did not return session_id")
        return write_summary(output_path, summary)
    summary["session_created"] = True
    summary["session_id"] = session_id
    summary["tool_calls"]["lab_session_create"] = {"ok": True, "status": str(create_payload.get("status", ""))}
    if isinstance(create_payload.get("paths"), dict):
        summary["persisted_paths"].extend(str(value) for value in create_payload["paths"].values())

    claim_id = ""
    experiment_id = ""

    advance_response = mcp_request(
        endpoint,
        request_id=6,
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
    errors = validate_mcp_success(advance_response, expected_id=6)
    if errors:
        summary["errors"].extend(errors)
    else:
        advance_payload = extract_structured_content(advance_response)
        summary["advance_supported"] = True
        summary["advance_ok"] = isinstance(advance_payload.get("updated_session"), dict)
        summary["tool_calls"]["lab_session_advance"] = {
            "ok": summary["advance_ok"],
            "status": str(advance_payload.get("updated_session", {}).get("status", "")),
        }
        if isinstance(advance_payload.get("paths"), dict):
            summary["persisted_paths"].extend(str(value) for value in advance_payload["paths"].values())

    agent_response = mcp_request(
        endpoint,
        request_id=7,
        method="tools/call",
        params={
            "name": "lab_agent_run",
            "arguments": {
                "session_id": session_id,
                "agent_role": "Theorist",
                "provider": "local_backend",
                "task": "Propose one next research action.",
                "context_ids": [],
            },
        },
        timeout_seconds=timeout_seconds,
        headers=request_headers,
    )
    errors = validate_mcp_success(agent_response, expected_id=7)
    if errors:
        summary["errors"].extend(errors)
    else:
        agent_payload = extract_structured_content(agent_response)
        provider_result = agent_payload.get("provider_result")
        summary["tool_calls"]["lab_agent_run"] = {
            "ok": bool(agent_payload.get("turn_id"))
            and tool_status(provider_result) in {"completed", "provider_required", "local_backend_required", "deferred"},
            "status": str(agent_payload.get("status", "")),
            "provider_status": tool_status(provider_result),
        }

    referee_response = mcp_request(
        endpoint,
        request_id=8,
        method="tools/call",
        params={
            "name": "lab_referee_review",
            "arguments": {
                "session_id": session_id,
                "text": "Check whether the current cloud-native session state is reviewable.",
                "strictness": "hostile",
            },
        },
        timeout_seconds=timeout_seconds,
        headers=request_headers,
    )
    errors = validate_mcp_success(referee_response, expected_id=8)
    if errors:
        summary["errors"].extend(errors)
    else:
        referee_payload = extract_structured_content(referee_response)
        summary["tool_calls"]["lab_referee_review"] = {
            "ok": tool_status(referee_payload.get("deferred")) == "deferred",
            "status": str(referee_payload.get("verdict", "")),
            "deferred_status": tool_status(referee_payload.get("deferred")),
        }

    memory_write_response = mcp_request(
        endpoint,
        request_id=9,
        method="tools/call",
        params={
            "name": "lab_memory_write",
            "arguments": {
                "session_id": session_id,
                "kind": "claim",
                "payload": {
                    "text": "Cloud smoke claim for memory search coverage.",
                    "claim_type": "observation",
                    "status": "HEURISTIC",
                    "confidence": "low",
                    "source_turn_id": "smoke",
                },
            },
        },
        timeout_seconds=timeout_seconds,
        headers=request_headers,
    )
    errors = validate_mcp_success(memory_write_response, expected_id=9)
    if errors:
        summary["errors"].extend(errors)
    else:
        memory_write_payload = extract_structured_content(memory_write_response)
        claim_id = str(memory_write_payload.get("written_object_id", "")).strip()
        summary["tool_calls"]["lab_memory_write"] = {
            "ok": bool(claim_id),
            "status": str(memory_write_payload.get("status", "")),
            "written_object_id": claim_id,
        }

    memory_search_response = mcp_request(
        endpoint,
        request_id=10,
        method="tools/call",
        params={"name": "lab_memory_search", "arguments": {"query": "cloud smoke claim", "limit": 10}},
        timeout_seconds=timeout_seconds,
        headers=request_headers,
    )
    errors = validate_mcp_success(memory_search_response, expected_id=10)
    if errors:
        summary["errors"].extend(errors)
    else:
        memory_search_payload = extract_structured_content(memory_search_response)
        claims = memory_search_payload.get("claims")
        claim_ids = {str(item.get("claim_id", "")) for item in claims if isinstance(item, dict)} if isinstance(claims, list) else set()
        summary["tool_calls"]["lab_memory_search"] = {
            "ok": bool(claim_id) and claim_id in claim_ids,
            "claims_count": len(claims) if isinstance(claims, list) else 0,
        }

    experiment_create_response = mcp_request(
        endpoint,
        request_id=11,
        method="tools/call",
        params={
            "name": "lab_experiment_create",
            "arguments": {
                "session_id": session_id,
                "claim_id": claim_id or "smoke-claim",
                "question": "Check whether the smoke claim can be tested later.",
                "method": "python_bruteforce",
                "inputs": {"candidate_answer": "smoke"},
            },
        },
        timeout_seconds=timeout_seconds,
        headers=request_headers,
    )
    errors = validate_mcp_success(experiment_create_response, expected_id=11)
    if errors:
        summary["errors"].extend(errors)
    else:
        experiment_create_payload = extract_structured_content(experiment_create_response)
        experiment_id = str(experiment_create_payload.get("experiment_id", "")).strip()
        summary["tool_calls"]["lab_experiment_create"] = {
            "ok": bool(experiment_id),
            "status": str(experiment_create_payload.get("status", "")),
            "experiment_id": experiment_id,
        }

    experiment_run_response = mcp_request(
        endpoint,
        request_id=12,
        method="tools/call",
        params={
            "name": "lab_experiment_run",
            "arguments": {
                "session_id": session_id,
                "experiment_id": experiment_id or "smoke-experiment",
                "dry_run": False,
            },
        },
        timeout_seconds=timeout_seconds,
        headers=request_headers,
    )
    errors = validate_mcp_success(experiment_run_response, expected_id=12)
    if errors:
        summary["errors"].extend(errors)
    else:
        experiment_run_payload = extract_structured_content(experiment_run_response)
        summary["tool_calls"]["lab_experiment_run"] = {
            "ok": tool_status(experiment_run_payload.get("deferred")) == "deferred",
            "status": str(experiment_run_payload.get("verdict", "")),
            "deferred_status": tool_status(experiment_run_payload.get("deferred")),
        }

    debate_response = mcp_request(
        endpoint,
        request_id=13,
        method="tools/call",
        params={
            "name": "lab_models_debate",
            "arguments": {
                "session_id": session_id,
                "question": "Debate whether the smoke claim merits a follow-up.",
                "participants": ["openai_compatible"],
                "rounds": ["independent_discovery"],
                "use_existing_research_table": False,
            },
        },
        timeout_seconds=timeout_seconds,
        headers=request_headers,
    )
    errors = validate_mcp_success(debate_response, expected_id=13)
    if errors:
        summary["errors"].extend(errors)
    else:
        debate_payload = extract_structured_content(debate_response)
        provider_result = debate_payload.get("provider_result")
        deferred = debate_payload.get("deferred")
        summary["tool_calls"]["lab_models_debate"] = {
            "ok": bool(debate_payload.get("summary")) and (
                tool_status(provider_result)
                in {
                    "completed",
                    "provider_required",
                    "api_key_required",
                    "oauth_required",
                    "provider_auth_failed",
                    "rate_limited",
                    "provider_unavailable",
                    "deferred",
                }
                or tool_status(deferred) == "deferred"
            ),
            "provider_status": tool_status(provider_result),
            "deferred_status": tool_status(deferred),
        }

    get_response = mcp_request(
        endpoint,
        request_id=14,
        method="tools/call",
        params={"name": "lab_session_get", "arguments": {"session_id": session_id}},
        timeout_seconds=timeout_seconds,
        headers=request_headers,
    )
    errors = validate_mcp_success(get_response, expected_id=14)
    if errors:
        summary["errors"].extend(errors)
    else:
        get_payload = extract_structured_content(get_response)
        summary["get_ok"] = isinstance(get_payload, dict) and get_payload.get("session", {}).get("session_id") == session_id
        summary["tool_calls"]["lab_session_get"] = {"ok": summary["get_ok"]}
        for key in ("notebook_path", "report_path"):
            value = get_payload.get(key)
            if isinstance(value, str) and value:
                summary["persisted_paths"].append(value)

    report_response = mcp_request(
        endpoint,
        request_id=15,
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
    errors = validate_mcp_success(report_response, expected_id=15)
    if errors:
        summary["errors"].extend(errors)
    else:
        report_payload = extract_structured_content(report_response)
        summary["report_ok"] = isinstance(report_payload, dict) and bool(report_payload.get("report_path"))
        summary["tool_calls"]["lab_report_generate"] = {
            "ok": summary["report_ok"],
            "status": str(report_payload.get("status", "")),
        }
        if isinstance(report_payload.get("report_path"), str):
            summary["persisted_paths"].append(report_payload["report_path"])

    scene_id = ""
    simulation_id = ""

    scene_create_response = mcp_request(
        endpoint,
        request_id=16,
        method="tools/call",
        params={
            "name": "create_lab_scene",
            "arguments": {
                "session_id": session_id,
                "title": "Smoke Scene",
                "description": "Remote smoke scene",
                "units": {"length": "m", "time": "s"},
                "parameters": {"gravity": 9.81},
                "metadata": {"source": "remote_smoke"},
            },
        },
        timeout_seconds=timeout_seconds,
        headers=request_headers,
    )
    errors = validate_mcp_success(scene_create_response, expected_id=16)
    if errors:
        summary["errors"].extend(errors)
    else:
        scene_create_payload = extract_structured_content(scene_create_response)
        scene_id = str(scene_create_payload.get("scene_id", "")).strip()
        summary["scene_created"] = bool(scene_id)
        summary["scene_id"] = scene_id
        summary["tool_calls"]["create_lab_scene"] = {"ok": bool(scene_id)}
        if isinstance(scene_create_payload.get("paths"), dict):
            summary["persisted_paths"].extend(str(value) for value in scene_create_payload["paths"].values())

    add_object_response = mcp_request(
        endpoint,
        request_id=17,
        method="tools/call",
        params={
            "name": "add_lab_object",
            "arguments": {
                "scene_id": scene_id or "smoke-scene",
                "object": {
                    "id": "ball-1",
                    "type": "rigid_body",
                    "label": "Projectile",
                    "position": {"x": 0, "y": 1, "z": 0},
                    "rotation": {"x": 0, "y": 0, "z": 0},
                    "scale": {"x": 1, "y": 1, "z": 1},
                    "geometry": {"kind": "sphere"},
                    "material": {"color": "#ff7a59"},
                    "data": {"mass": 0.2, "velocity": {"x": 4, "y": 6, "z": 0}},
                    "metadata": {"source": "remote_smoke"},
                },
            },
        },
        timeout_seconds=timeout_seconds,
        headers=request_headers,
    )
    errors = validate_mcp_success(add_object_response, expected_id=17)
    if errors:
        summary["errors"].extend(errors)
    else:
        add_object_payload = extract_structured_content(add_object_response)
        summary["tool_calls"]["add_lab_object"] = {"ok": str(add_object_payload.get("object_id", "")) == "ball-1"}

    update_object_response = mcp_request(
        endpoint,
        request_id=18,
        method="tools/call",
        params={
            "name": "update_lab_object",
            "arguments": {
                "scene_id": scene_id or "smoke-scene",
                "object_id": "ball-1",
                "patch": {"label": "Projectile A"},
            },
        },
        timeout_seconds=timeout_seconds,
        headers=request_headers,
    )
    errors = validate_mcp_success(update_object_response, expected_id=18)
    if errors:
        summary["errors"].extend(errors)
    else:
        update_object_payload = extract_structured_content(update_object_response)
        updated_object = update_object_payload.get("object")
        summary["tool_calls"]["update_lab_object"] = {
            "ok": isinstance(updated_object, dict) and updated_object.get("label") == "Projectile A",
        }

    set_parameters_response = mcp_request(
        endpoint,
        request_id=19,
        method="tools/call",
        params={
            "name": "set_lab_parameters",
            "arguments": {
                "scene_id": scene_id or "smoke-scene",
                "parameters": {"gravity": 9.5, "air_resistance": False},
                "metadata": {"updated_by": "remote_smoke"},
            },
        },
        timeout_seconds=timeout_seconds,
        headers=request_headers,
    )
    errors = validate_mcp_success(set_parameters_response, expected_id=19)
    if errors:
        summary["errors"].extend(errors)
    else:
        set_parameters_payload = extract_structured_content(set_parameters_response)
        summary["tool_calls"]["set_lab_parameters"] = {
            "ok": isinstance(set_parameters_payload.get("parameters"), dict) and "gravity" in set_parameters_payload["parameters"],
        }

    simulation_response = mcp_request(
        endpoint,
        request_id=20,
        method="tools/call",
        params={
            "name": "run_lab_simulation",
            "arguments": {
                "scene_id": scene_id or "smoke-scene",
                "adapter_id": "physics.simple_projectile",
                "inputs": {"object_id": "ball-1", "duration": 1.0, "time_step": 0.25},
            },
        },
        timeout_seconds=timeout_seconds,
        headers=request_headers,
    )
    errors = validate_mcp_success(simulation_response, expected_id=20)
    if errors:
        summary["errors"].extend(errors)
    else:
        simulation_payload = extract_structured_content(simulation_response)
        simulation_id = str(simulation_payload.get("simulation_id", "")).strip()
        summary["tool_calls"]["run_lab_simulation"] = {
            "ok": simulation_payload.get("status") == "completed" and bool(simulation_id),
            "status": str(simulation_payload.get("status", "")),
        }

    attach_response = mcp_request(
        endpoint,
        request_id=21,
        method="tools/call",
        params={
            "name": "attach_simulation_to_scene",
            "arguments": {
                "scene_id": scene_id or "smoke-scene",
                "simulation_id": simulation_id or "smoke-sim",
                "object_ids": ["ball-1"],
                "evidence_refs": [],
                "report_refs": [],
                "apply_object_updates": True,
            },
        },
        timeout_seconds=timeout_seconds,
        headers=request_headers,
    )
    errors = validate_mcp_success(attach_response, expected_id=21)
    if errors:
        summary["errors"].extend(errors)
    else:
        attach_payload = extract_structured_content(attach_response)
        attached_object_ids = attach_payload.get("attached_object_ids")
        summary["tool_calls"]["attach_simulation_to_scene"] = {
            "ok": isinstance(attached_object_ids, list) and "ball-1" in attached_object_ids,
        }

    snapshot_response = mcp_request(
        endpoint,
        request_id=22,
        method="tools/call",
        params={
            "name": "export_lab_snapshot",
            "arguments": {
                "scene_id": scene_id or "smoke-scene",
                "adapter_id": "scene.three_json",
                "include_simulations": True,
            },
        },
        timeout_seconds=timeout_seconds,
        headers=request_headers,
    )
    errors = validate_mcp_success(snapshot_response, expected_id=22)
    if errors:
        summary["errors"].extend(errors)
    else:
        snapshot_payload = extract_structured_content(snapshot_response)
        summary["tool_calls"]["export_lab_snapshot"] = {
            "ok": snapshot_payload.get("status") == "completed" and isinstance(snapshot_payload.get("snapshot"), dict),
            "status": str(snapshot_payload.get("status", "")),
        }

    scene_get_response = mcp_request(
        endpoint,
        request_id=23,
        method="tools/call",
        params={"name": "get_lab_scene", "arguments": {"scene_id": scene_id or "smoke-scene"}},
        timeout_seconds=timeout_seconds,
        headers=request_headers,
    )
    errors = validate_mcp_success(scene_get_response, expected_id=23)
    if errors:
        summary["errors"].extend(errors)
    else:
        scene_get_payload = extract_structured_content(scene_get_response)
        summary["tool_calls"]["get_lab_scene"] = {
            "ok": isinstance(scene_get_payload.get("scene"), dict) and scene_get_payload["scene"].get("scene_id") == scene_id,
        }
        for key in ("report_path", "snapshot_path"):
            value = scene_get_payload.get(key)
            if isinstance(value, str) and value:
                summary["persisted_paths"].append(value)

    scene_report_response = mcp_request(
        endpoint,
        request_id=24,
        method="tools/call",
        params={
            "name": "generate_lab_report",
            "arguments": {
                "scene_id": scene_id or "smoke-scene",
                "format": "markdown",
                "include_objects": True,
                "include_simulations": True,
            },
        },
        timeout_seconds=timeout_seconds,
        headers=request_headers,
    )
    errors = validate_mcp_success(scene_report_response, expected_id=24)
    if errors:
        summary["errors"].extend(errors)
    else:
        scene_report_payload = extract_structured_content(scene_report_response)
        summary["tool_calls"]["generate_lab_report"] = {
            "ok": bool(scene_report_payload.get("report_path")) and isinstance(scene_report_payload.get("markdown"), str),
        }
        if isinstance(scene_report_payload.get("report_path"), str):
            summary["persisted_paths"].append(scene_report_payload["report_path"])

    remove_object_response = mcp_request(
        endpoint,
        request_id=25,
        method="tools/call",
        params={
            "name": "remove_lab_object",
            "arguments": {"scene_id": scene_id or "smoke-scene", "object_id": "ball-1"},
        },
        timeout_seconds=timeout_seconds,
        headers=request_headers,
    )
    errors = validate_mcp_success(remove_object_response, expected_id=25)
    if errors:
        summary["errors"].extend(errors)
    else:
        remove_object_payload = extract_structured_content(remove_object_response)
        summary["tool_calls"]["remove_lab_object"] = {
            "ok": str(remove_object_payload.get("removed_object_id", "")) == "ball-1",
        }

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

    for tool_name in sorted(EXISTING_TOOLS | LAB_TOOLS):
        call_summary = summary["tool_calls"].get(tool_name)
        if not isinstance(call_summary, dict) or not call_summary.get("ok"):
            summary["errors"].append(f"{tool_name} did not produce an acceptable smoke result")

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

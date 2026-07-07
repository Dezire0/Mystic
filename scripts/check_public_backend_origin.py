from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_remote_mcp_lab_smoke import (  # noqa: E402
    EXISTING_TOOLS,
    LAB_TOOLS,
    auth_status_from_response,
    base_url_from_endpoint,
    extract_tool_names,
    mcp_request,
    now_iso,
    validate_mcp_success,
)
from scripts.check_chatgpt_remote_mcp_readiness import http_json_request  # noqa: E402


PHASE1_REQUIRED_TOOLS = EXISTING_TOOLS | LAB_TOOLS


OK = "OK"
PUBLIC_WORKER_UNREACHABLE = "PUBLIC_WORKER_UNREACHABLE"
BACKEND_ORIGIN_DEAD = "BACKEND_ORIGIN_DEAD"
BACKEND_HEALTH_FAILED = "BACKEND_HEALTH_FAILED"
OAUTH_AUTH_REQUIRED_MISSING = "OAUTH_AUTH_REQUIRED_MISSING"
BEARER_MCP_FAILED = "BEARER_MCP_FAILED"
UNKNOWN = "UNKNOWN"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check whether the public Mystic MCP Worker is backed by a healthy origin.")
    parser.add_argument("--public-endpoint", required=True, help="Public Mystic base URL or /mcp URL.")
    parser.add_argument("--backend-url", default="", help="Optional direct backend base URL or /health URL.")
    parser.add_argument("--expect-oauth", action="store_true", help="Require no-token /mcp to return an auth-required response.")
    parser.add_argument("--bearer-token", default="", help="Optional bearer token used to validate authenticated /mcp access.")
    parser.add_argument(
        "--output",
        default="",
        help="Optional output path. Defaults to mystic_data/e2e/backend_origin_health/summary.json.",
    )
    parser.add_argument("--timeout-seconds", type=int, default=30)
    return parser


def default_output_path(root_path: Path) -> Path:
    return root_path / "mystic_data" / "e2e" / "backend_origin_health" / "summary.json"


def _health_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/health"):
        return normalized
    return f"{normalized}/health"


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    try:
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
    except TypeError:
        return str(value)


def _redact_text(value: str, secrets: list[str]) -> str:
    redacted = value
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "[redacted]")
    return redacted


def _redact_payload(value: Any, secrets: list[str]) -> Any:
    if isinstance(value, str):
        return _redact_text(value, secrets)
    if isinstance(value, list):
        return [_redact_payload(item, secrets) for item in value]
    if isinstance(value, dict):
        return {key: _redact_payload(item, secrets) for key, item in value.items()}
    return value


def _body_text(response: dict[str, Any]) -> str:
    return _stringify(response.get("body"))


def _is_health_ok(response: dict[str, Any]) -> bool:
    return int(response.get("status") or 0) == 200 and response.get("body") == {"status": "ok"}


def _looks_like_origin_dead(response: dict[str, Any]) -> bool:
    status = int(response.get("status") or 0)
    headers = {str(key).lower(): str(value) for key, value in response.get("headers", {}).items()}
    body_text = _body_text(response).lower()
    if status == 530 and ("origin dns error" in body_text or "error 1016" in body_text):
        return True
    if status in {502, 503} and (
        "origin dns error" in body_text
        or "error 1016" in body_text
        or "upstream or external service errors" in body_text
        or "mystic origin unavailable" in body_text
    ):
        return True
    if status in {502, 530} and "x-mystic-public-origin" in headers:
        return True
    return False


def write_json(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return payload


def check_public_backend_origin(
    public_endpoint: str,
    *,
    backend_url: str = "",
    expect_oauth: bool = False,
    bearer_token: str = "",
    timeout_seconds: int = 30,
    output_path: Path | None = None,
) -> dict[str, Any]:
    endpoint = public_endpoint.rstrip("/")
    if not endpoint.endswith("/mcp"):
        endpoint = f"{endpoint}/mcp"
    base_url = base_url_from_endpoint(endpoint)
    secrets = [bearer_token]

    summary: dict[str, Any] = {
        "public_endpoint": base_url,
        "backend_url_checked": backend_url.rstrip("/"),
        "checked_at": now_iso(),
        "public_health_ok": False,
        "mcp_auth_required_ok": False,
        "bearer_mcp_ok": None,
        "likely_worker_ok": False,
        "likely_backend_ok": None,
        "likely_origin_dead": False,
        "failure_category": UNKNOWN,
        "errors": [],
        "recommendations": [],
        "public_health_status": None,
        "backend_health_status": None,
        "oauth_required": False,
        "bearer_initialize_ok": False,
        "bearer_tools_list_ok": False,
        "lab_tools_visible": False,
    }

    public_health = http_json_request(_health_url(base_url), method="GET", timeout_seconds=timeout_seconds)
    summary["public_health_status"] = public_health.get("status")
    summary["likely_worker_ok"] = public_health.get("status") is not None
    summary["public_health_ok"] = _is_health_ok(public_health)
    summary["likely_origin_dead"] = _looks_like_origin_dead(public_health)
    if not summary["public_health_ok"]:
        summary["errors"].append(
            f"public /health failed: status={public_health.get('status')} body={_body_text(public_health)}"
        )

    if backend_url:
        backend_health = http_json_request(_health_url(backend_url), method="GET", timeout_seconds=timeout_seconds)
        summary["backend_url_checked"] = backend_url.rstrip("/")
        summary["backend_health_status"] = backend_health.get("status")
        summary["likely_backend_ok"] = _is_health_ok(backend_health)
        if not summary["likely_backend_ok"]:
            summary["errors"].append(
                f"backend /health failed: status={backend_health.get('status')} body={_body_text(backend_health)}"
            )

    unauth_initialize = mcp_request(endpoint, request_id=1, method="initialize", timeout_seconds=timeout_seconds)
    auth_required, oauth_required = auth_status_from_response(unauth_initialize)
    summary["oauth_required"] = oauth_required
    summary["mcp_auth_required_ok"] = auth_required and (oauth_required or not expect_oauth)
    if expect_oauth and not summary["mcp_auth_required_ok"]:
        summary["errors"].append(
            f"no-token /mcp did not return expected auth-required response: status={unauth_initialize.get('status')}"
        )

    if bearer_token:
        headers = {"Authorization": f"Bearer {bearer_token}"}
        authed_initialize = mcp_request(
            endpoint,
            request_id=2,
            method="initialize",
            timeout_seconds=timeout_seconds,
            headers=headers,
        )
        initialize_errors = validate_mcp_success(authed_initialize, expected_id=2)
        summary["bearer_initialize_ok"] = not initialize_errors
        if initialize_errors:
            summary["bearer_mcp_ok"] = False
            summary["errors"].append("bearer initialize failed: " + "; ".join(initialize_errors))
        else:
            tools_list = mcp_request(
                endpoint,
                request_id=3,
                method="tools/list",
                timeout_seconds=timeout_seconds,
                headers=headers,
            )
            tools_errors = validate_mcp_success(tools_list, expected_id=3)
            summary["bearer_tools_list_ok"] = not tools_errors
            if tools_errors:
                summary["errors"].append("bearer tools/list failed: " + "; ".join(tools_errors))
            else:
                tool_names = extract_tool_names(tools_list)
                summary["lab_tools_visible"] = PHASE1_REQUIRED_TOOLS.issubset(tool_names)
                if not summary["lab_tools_visible"]:
                    missing_tools = sorted(PHASE1_REQUIRED_TOOLS.difference(tool_names))
                    summary["errors"].append("bearer tools/list missing lab tools: " + ", ".join(missing_tools))
            summary["bearer_mcp_ok"] = summary["bearer_initialize_ok"] and summary["bearer_tools_list_ok"] and summary["lab_tools_visible"]
    else:
        summary["bearer_mcp_ok"] = None

    if not summary["likely_worker_ok"]:
        summary["failure_category"] = PUBLIC_WORKER_UNREACHABLE
        summary["recommendations"].append("Check the Cloudflare Worker deployment, DNS, and network reachability first.")
    elif summary["likely_origin_dead"]:
        summary["failure_category"] = BACKEND_ORIGIN_DEAD
        summary["recommendations"].append(
            "The public Worker is reachable but its backend origin appears dead. Replace the quick tunnel with a named tunnel or other stable backend and update MYSTIC_BACKEND_URL."
        )
    elif summary["likely_backend_ok"] is False:
        summary["failure_category"] = BACKEND_HEALTH_FAILED
        summary["recommendations"].append(
            "Restore direct backend /health before relying on the public Worker, then rerun the public MCP smoke checks."
        )
    elif expect_oauth and not summary["mcp_auth_required_ok"]:
        summary["failure_category"] = OAUTH_AUTH_REQUIRED_MISSING
        summary["recommendations"].append(
            "Ensure public no-token POST /mcp returns 401 with a Bearer WWW-Authenticate challenge."
        )
    elif bearer_token and summary["bearer_mcp_ok"] is not True:
        summary["failure_category"] = BEARER_MCP_FAILED
        summary["recommendations"].append(
            "Validate the bearer token and confirm authenticated initialize/tools/list succeed on the public /mcp endpoint."
        )
    elif summary["public_health_ok"] and (summary["mcp_auth_required_ok"] or not expect_oauth):
        summary["failure_category"] = OK
        summary["recommendations"].append(
            "Public Worker checks are healthy. For long-lived reliability, replace the quick tunnel backend with a named tunnel or another stable origin."
        )
    else:
        summary["failure_category"] = UNKNOWN
        summary["recommendations"].append(
            "Inspect the public Worker response bodies and direct backend health to separate Worker errors from backend-origin failures."
        )

    summary["errors"] = _dedupe([_redact_text(str(error), secrets) for error in summary["errors"]])
    summary["recommendations"] = _dedupe([_redact_text(str(item), secrets) for item in summary["recommendations"]])
    redacted_summary = _redact_payload(summary, secrets)
    destination = output_path or default_output_path(ROOT)
    return write_json(destination, redacted_summary)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_path = Path(args.output) if args.output else default_output_path(ROOT)
    summary = check_public_backend_origin(
        args.public_endpoint,
        backend_url=args.backend_url,
        expect_oauth=args.expect_oauth,
        bearer_token=args.bearer_token,
        timeout_seconds=args.timeout_seconds,
        output_path=output_path,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=True))
    return 0 if summary["failure_category"] == OK else 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.mcp.import_verification import (  # noqa: E402
    default_verification_artifact_path,
    load_import_verification,
    validate_import_verification_artifact,
)
from scripts.run_remote_mcp_lab_smoke import (
    EXISTING_TOOLS,
    LAB_TOOLS,
    auth_status_from_response,
    base_url_from_endpoint,
    extract_tool_names,
    mcp_request,
    now_iso,
    validate_mcp_success,
)

PHASE1_REQUIRED_TOOLS = EXISTING_TOOLS | LAB_TOOLS

DEFAULT_PUBLIC_ENDPOINT = "https://mystic.dexproject.workers.dev"
CHATGPT_PUBLIC_CLIENT_ID = "mystic-chatgpt"
CHATGPT_CONNECTOR_CALLBACK = "https://chatgpt.com/connector/oauth/wpja_UKVNtTE"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check whether Mystic is import-ready as a ChatGPT remote MCP server.")
    parser.add_argument("--public-endpoint", default=DEFAULT_PUBLIC_ENDPOINT, help="Public Mystic base URL or /mcp URL.")
    parser.add_argument("--bearer-token", default="", help="Optional bearer token used to validate authenticated /mcp access.")
    parser.add_argument("--expect-oauth", action="store_true", help="Require OAuth metadata and auth-required MCP behavior.")
    parser.add_argument(
        "--require-dynamic-client-registration",
        action="store_true",
        help="Treat missing /oauth/register support as a blocker.",
    )
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument(
        "--output",
        default="",
        help="Optional output path. Defaults to mystic_data/e2e/remote_mcp_lab_smoke/chatgpt_remote_mcp_readiness.json.",
    )
    parser.add_argument(
        "--manual-import-verification-artifact",
        default="",
        help="Optional runtime artifact path used to mark import_ready=true after real manual ChatGPT verification.",
    )
    return parser


def default_output_path(root_path: Path) -> Path:
    return root_path / "mystic_data" / "e2e" / "remote_mcp_lab_smoke" / "chatgpt_remote_mcp_readiness.json"


def write_json(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return payload


def http_json_request(
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    method: str = "POST",
    timeout_seconds: int = 30,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request_headers = {"User-Agent": "Mystic Remote MCP Readiness", "Accept": "application/json, text/html;q=0.9, */*;q=0.8"}
    if data is not None:
        request_headers["Content-Type"] = "application/json"
    if headers:
        request_headers.update(headers)
    request = Request(url, data=data, headers=request_headers, method=method)
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return _decode_http_response(
                status=response.status,
                headers=dict(response.headers.items()),
                body_text=response.read().decode("utf-8"),
            )
    except HTTPError as exc:
        return _decode_http_response(
            status=exc.code,
            headers=dict(exc.headers.items()),
            body_text=exc.read().decode("utf-8"),
            ok=False,
        )
    except URLError as exc:
        return {"ok": False, "status": None, "headers": {}, "body": {"error": str(exc.reason)}}


def _decode_http_response(
    *,
    status: int | None,
    headers: dict[str, str],
    body_text: str,
    ok: bool = True,
) -> dict[str, Any]:
    content_type = str(headers.get("Content-Type", headers.get("content-type", ""))).lower()
    if "json" in content_type:
        try:
            body = json.loads(body_text) if body_text.strip() else None
        except json.JSONDecodeError:
            body = {"raw": body_text}
    else:
        body = {"raw": body_text} if body_text else None
    return {"ok": ok, "status": status, "headers": headers, "body": body}


def _protected_resource_metadata_urls(public_endpoint: str) -> list[str]:
    base_url = base_url_from_endpoint(public_endpoint)
    return [
        f"{base_url.rstrip('/')}/.well-known/oauth-protected-resource",
        f"{base_url.rstrip('/')}/.well-known/oauth-protected-resource/mcp",
    ]


def _oauth_authorization_server_url(auth_server: str) -> str:
    return f"{auth_server.rstrip('/')}/.well-known/oauth-authorization-server"


def _openid_configuration_url(auth_server: str) -> str:
    return f"{auth_server.rstrip('/')}/.well-known/openid-configuration"


def _authorize_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/oauth/authorize"


def _token_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/oauth/token"


def _register_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/oauth/register"


def _looks_like_protected_resource_metadata(body: Any) -> bool:
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


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _metadata_probe(base_url: str, timeout_seconds: int) -> tuple[dict[str, Any], list[str], list[str]]:
    blockers: list[str] = []
    next_actions: list[str] = []
    details: dict[str, Any] = {
        "oauth_configured": False,
        "oauth_metadata_ok": False,
        "oauth_authorize_ok": False,
        "oauth_token_ok": False,
        "dynamic_client_registration_ok": False,
        "authorization_server": "",
        "protected_resource_metadata_url": "",
    }

    protected_resource: dict[str, Any] | None = None
    for url in _protected_resource_metadata_urls(base_url):
        candidate = http_json_request(url, method="GET", timeout_seconds=timeout_seconds)
        if int(candidate.get("status") or 0) == 200 and _looks_like_protected_resource_metadata(candidate.get("body")):
            protected_resource = candidate
            details["protected_resource_metadata_url"] = url
            break
    if protected_resource is None:
        blockers.append("OAUTH_METADATA_MISSING")
        next_actions.append("Expose /.well-known/oauth-protected-resource for the public MCP resource.")
        return details, blockers, next_actions

    details["oauth_metadata_ok"] = True
    authorization_servers = protected_resource["body"]["authorization_servers"]
    authorization_server_metadata: dict[str, Any] | None = None
    for auth_server in authorization_servers:
        auth_server = str(auth_server)
        details["authorization_server"] = auth_server
        for discovery_url in (_oauth_authorization_server_url(auth_server), _openid_configuration_url(auth_server)):
            candidate = http_json_request(discovery_url, method="GET", timeout_seconds=timeout_seconds)
            if int(candidate.get("status") or 0) == 200 and _looks_like_auth_server_metadata(candidate.get("body")):
                authorization_server_metadata = candidate
                break
        if authorization_server_metadata is not None:
            break
    if authorization_server_metadata is None:
        blockers.append("OAUTH_METADATA_MISSING")
        next_actions.append("Expose OAuth authorization server discovery metadata.")
        return details, blockers, next_actions

    details["oauth_configured"] = True
    authorize_params = {
        "response_type": "code",
        "client_id": CHATGPT_PUBLIC_CLIENT_ID,
        "redirect_uri": CHATGPT_CONNECTOR_CALLBACK,
        "state": "mystic-state",
        "scope": "tools:read tools:execute",
        "code_challenge": "mystic-pkce-challenge",
        "code_challenge_method": "S256",
    }
    authorize_url = f"{_authorize_url(base_url)}?{urlencode(authorize_params)}"
    authorize_response = http_json_request(authorize_url, method="GET", timeout_seconds=timeout_seconds)
    if int(authorize_response.get("status") or 0) in {200, 302, 303}:
        details["oauth_authorize_ok"] = True
    else:
        blockers.append("OAUTH_AUTHORIZE_MISSING")
        next_actions.append("Implement /oauth/authorize so it serves a consent or redirect flow.")

    token_response = http_json_request(
        _token_url(base_url),
        payload=None,
        method="POST",
        timeout_seconds=timeout_seconds,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if int(token_response.get("status") or 0) in {200, 400, 401}:
        details["oauth_token_ok"] = True
    else:
        blockers.append("OAUTH_TOKEN_MISSING")
        next_actions.append("Implement /oauth/token so clients can exchange authorization codes for access tokens.")

    register_response = http_json_request(_register_url(base_url), method="POST", timeout_seconds=timeout_seconds)
    details["dynamic_client_registration_ok"] = int(register_response.get("status") or 0) in {200, 201}

    return details, blockers, next_actions


def check_chatgpt_remote_mcp_readiness(
    public_endpoint: str,
    *,
    bearer_token: str = "",
    expect_oauth: bool = False,
    require_dynamic_client_registration: bool = False,
    timeout_seconds: int = 30,
    output_path: Path | None = None,
    manual_import_verification_artifact_path: Path | None = None,
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
        "oauth_metadata_ok": False,
        "oauth_authorize_ok": False,
        "oauth_token_ok": False,
        "dynamic_client_registration_ok": False,
        "token_validation_ok": False,
        "oauth_required": False,
        "import_ready": False,
        "import_ready_candidate": False,
        "manual_import_verification_checked": False,
        "manual_import_verification_path": "",
        "manual_import_verified": False,
        "manual_import_verification_errors": [],
        "manual_import_verification_warnings": [],
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

    metadata_details, metadata_blockers, metadata_actions = _metadata_probe(base_url, timeout_seconds)
    report.update(metadata_details)
    report["blockers"].extend(metadata_blockers)
    report["next_actions"].extend(metadata_actions)

    unauth_initialize = mcp_request(endpoint, request_id=1, method="initialize", timeout_seconds=timeout_seconds)
    auth_required, oauth_required = auth_status_from_response(unauth_initialize)
    report["oauth_required"] = oauth_required

    if auth_required:
        report["token_validation_ok"] = True
    elif expect_oauth:
        report["blockers"].append("TOKEN_VALIDATION_MISSING")
        report["next_actions"].append("Enable bearer-token protection for /mcp when OAuth is enabled.")

    authed_initialize = unauth_initialize
    authed_tools_list: dict[str, Any] | None = None
    if bearer_token:
        auth_headers = {"Authorization": f"Bearer {bearer_token}"}
        authed_initialize = mcp_request(
            endpoint,
            request_id=2,
            method="initialize",
            timeout_seconds=timeout_seconds,
            headers=auth_headers,
        )
        initialize_errors = validate_mcp_success(authed_initialize, expected_id=2)
        if not initialize_errors:
            report["mcp_initialize_ok"] = True
            authed_tools_list = mcp_request(
                endpoint,
                request_id=3,
                method="tools/list",
                timeout_seconds=timeout_seconds,
                headers=auth_headers,
            )
            tools_errors = validate_mcp_success(authed_tools_list, expected_id=3)
            if not tools_errors:
                report["tools_list_ok"] = True
                tool_names = extract_tool_names(authed_tools_list)
                report["lab_tools_visible"] = PHASE1_REQUIRED_TOOLS.issubset(tool_names)
                report["token_validation_ok"] = True
            else:
                report["blockers"].append("TOKEN_VALIDATION_MISSING")
                report["next_actions"].append("Bearer token reached /mcp but tools/list did not succeed.")
        else:
            report["blockers"].append("TOKEN_VALIDATION_MISSING")
            report["next_actions"].append("Bearer token did not unlock /mcp initialize successfully.")
    else:
        if not auth_required:
            initialize_errors = validate_mcp_success(unauth_initialize, expected_id=1)
            if not initialize_errors:
                report["mcp_initialize_ok"] = True
                tools_list = mcp_request(endpoint, request_id=4, method="tools/list", timeout_seconds=timeout_seconds)
                tools_errors = validate_mcp_success(tools_list, expected_id=4)
                if not tools_errors:
                    report["tools_list_ok"] = True
                    tool_names = extract_tool_names(tools_list)
                    report["lab_tools_visible"] = PHASE1_REQUIRED_TOOLS.issubset(tool_names)
        elif expect_oauth:
            report["next_actions"].append("Provide --bearer-token to confirm authenticated tools/list behavior.")

    if require_dynamic_client_registration and not report["dynamic_client_registration_ok"]:
        report["blockers"].append("OAUTH_DYNAMIC_CLIENT_REGISTRATION_MISSING")
        report["next_actions"].append("Implement /oauth/register or disable the DCR requirement for this readiness check.")

    if expect_oauth and not report["oauth_configured"]:
        report["blockers"].append("OAUTH_NOT_CONFIGURED")
        report["next_actions"].append("Configure Worker OAuth environment variables and deploy the metadata/auth endpoints.")
    elif not report["oauth_configured"]:
        report["blockers"].append("OAUTH_NOT_CONFIGURED")
        report["next_actions"].append("OAuth is optional for public smoke, but ChatGPT import readiness requires it.")

    report["blockers"] = _dedupe(report["blockers"])
    report["next_actions"] = _dedupe(report["next_actions"])
    report["import_ready_candidate"] = (
        report["health_ok"]
        and report["oauth_configured"]
        and report["oauth_metadata_ok"]
        and report["oauth_authorize_ok"]
        and report["oauth_token_ok"]
        and report["token_validation_ok"]
        and report["mcp_initialize_ok"]
        and report["tools_list_ok"]
        and report["lab_tools_visible"]
        and (report["dynamic_client_registration_ok"] or not require_dynamic_client_registration)
    )
    artifact_path = manual_import_verification_artifact_path or default_verification_artifact_path(ROOT)
    report["manual_import_verification_path"] = str(artifact_path)
    report["manual_import_verification_checked"] = artifact_path.exists()
    artifact_payload = load_import_verification(artifact_path) if artifact_path.exists() else None
    if artifact_path.exists():
        if artifact_payload is None:
            report["manual_import_verification_errors"].append("artifact is missing or invalid JSON")
        else:
            artifact_validation = validate_import_verification_artifact(artifact_payload, public_endpoint=base_url)
            report["manual_import_verified"] = artifact_validation["verified"]
            report["manual_import_verification_errors"].extend(artifact_validation["errors"])
            report["manual_import_verification_warnings"].extend(artifact_validation["warnings"])
    report["import_ready"] = report["import_ready_candidate"] and report["manual_import_verified"]
    if report["import_ready_candidate"] and not report["manual_import_verified"]:
        report["blockers"].append("MANUAL_IMPORT_NOT_VERIFIED")
        report["next_actions"].append(
            "Run a real ChatGPT Developer Mode remote MCP import, create the manual verification artifact, and rerun readiness."
        )

    destination = output_path or default_output_path(ROOT)
    return write_json(destination, report)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_path = Path(args.output) if args.output else default_output_path(ROOT)
    artifact_path = (
        Path(args.manual_import_verification_artifact)
        if args.manual_import_verification_artifact
        else default_verification_artifact_path(ROOT)
    )
    report = check_chatgpt_remote_mcp_readiness(
        args.public_endpoint,
        bearer_token=args.bearer_token,
        expect_oauth=args.expect_oauth,
        require_dynamic_client_registration=args.require_dynamic_client_registration,
        timeout_seconds=args.timeout_seconds,
        output_path=output_path,
        manual_import_verification_artifact_path=artifact_path,
    )
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0 if report["import_ready"] or report["import_ready_candidate"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

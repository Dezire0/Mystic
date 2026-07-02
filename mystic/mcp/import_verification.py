from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_TOOLS = (
    "lab_session_create",
    "lab_session_advance",
    "lab_session_get",
    "lab_report_generate",
)

FORBIDDEN_FIELD_NAMES = {
    "token",
    "bearer_token",
    "access_token",
    "refresh_token",
    "client_secret",
    "signing_secret",
    "password",
    "secret",
}


def default_verification_artifact_path(root_path: str | Path) -> Path:
    return Path(root_path) / "mystic_data" / "e2e" / "chatgpt_remote_mcp_import" / "verification.json"


def load_import_verification(path: str | Path) -> dict[str, Any] | None:
    artifact_path = Path(path)
    if not artifact_path.exists():
        return None
    try:
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def artifact_contains_secret_like_fields(data: Any) -> bool:
    return bool(_find_secret_like_paths(data))


def validate_import_verification_artifact(
    data: Any,
    *,
    public_endpoint: str,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    normalized_public_endpoint = str(public_endpoint).rstrip("/")
    normalized_mcp_endpoint = f"{normalized_public_endpoint}/mcp"

    if not isinstance(data, dict):
        return {
            "valid": False,
            "verified": False,
            "errors": ["artifact must be a JSON object"],
            "warnings": [],
            "verified_at": "",
            "required_tools_visible": False,
            "manual_tool_calls_passed": False,
        }

    secret_like_paths = _find_secret_like_paths(data)
    if secret_like_paths:
        errors.append("artifact contains forbidden secret-like field names")

    if data.get("artifact_version") != 1:
        errors.append("artifact_version must be 1")

    verified_at = str(data.get("verified_at", "")).strip()
    if not verified_at:
        errors.append("verified_at is required")

    if str(data.get("verified_by", "")).strip() != "manual":
        errors.append("verified_by must be manual")

    if str(data.get("public_endpoint", "")).rstrip("/") != normalized_public_endpoint:
        errors.append("public_endpoint does not match the checked public endpoint")

    if str(data.get("mcp_endpoint", "")).rstrip("/") != normalized_mcp_endpoint:
        errors.append("mcp_endpoint must match the checked public endpoint /mcp path")

    for key in (
        "chatgpt_developer_mode_imported",
        "oauth_flow_completed",
        "tools_list_visible_in_chatgpt",
    ):
        if data.get(key) is not True:
            errors.append(f"{key} must be true")

    visible_tools = data.get("required_tools_visible")
    if not isinstance(visible_tools, list):
        errors.append("required_tools_visible must be a list")
        visible_tool_names: set[str] = set()
    else:
        visible_tool_names = {str(item).strip() for item in visible_tools if str(item).strip()}
        missing_visible_tools = [tool for tool in REQUIRED_TOOLS if tool not in visible_tool_names]
        if missing_visible_tools:
            errors.append(f"required_tools_visible is missing: {', '.join(missing_visible_tools)}")

    manual_results = data.get("manual_tool_call_results")
    if not isinstance(manual_results, dict):
        errors.append("manual_tool_call_results must be an object")
        manual_tool_calls_passed = False
    else:
        failed_tools = [
            tool for tool in REQUIRED_TOOLS if str(manual_results.get(tool, "")).strip().lower() != "passed"
        ]
        manual_tool_calls_passed = not failed_tools
        if failed_tools:
            errors.append(f"manual_tool_call_results must mark passed for: {', '.join(failed_tools)}")

    notes = data.get("notes")
    if notes is not None and not isinstance(notes, str):
        warnings.append("notes should be a string when present")

    required_tools_visible = isinstance(visible_tools, list) and all(tool in visible_tool_names for tool in REQUIRED_TOOLS)
    valid = not errors
    verified = valid and required_tools_visible and manual_tool_calls_passed
    return {
        "valid": valid,
        "verified": verified,
        "errors": errors,
        "warnings": warnings,
        "verified_at": verified_at,
        "required_tools_visible": required_tools_visible,
        "manual_tool_calls_passed": manual_tool_calls_passed,
    }


def summarize_import_verification(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {
            "artifact_version": None,
            "verified_at": "",
            "verified_by": "",
            "public_endpoint": "",
            "mcp_endpoint": "",
            "chatgpt_developer_mode_imported": False,
            "oauth_flow_completed": False,
            "tools_list_visible_in_chatgpt": False,
            "required_tools_visible": [],
            "manual_tool_call_results": {},
        }
    return {
        "artifact_version": data.get("artifact_version"),
        "verified_at": str(data.get("verified_at", "")).strip(),
        "verified_by": str(data.get("verified_by", "")).strip(),
        "public_endpoint": str(data.get("public_endpoint", "")).strip(),
        "mcp_endpoint": str(data.get("mcp_endpoint", "")).strip(),
        "chatgpt_developer_mode_imported": data.get("chatgpt_developer_mode_imported") is True,
        "oauth_flow_completed": data.get("oauth_flow_completed") is True,
        "tools_list_visible_in_chatgpt": data.get("tools_list_visible_in_chatgpt") is True,
        "required_tools_visible": [
            str(item).strip()
            for item in data.get("required_tools_visible", [])
            if str(item).strip()
        ]
        if isinstance(data.get("required_tools_visible"), list)
        else [],
        "manual_tool_call_results": {
            str(key): str(value)
            for key, value in data.get("manual_tool_call_results", {}).items()
        }
        if isinstance(data.get("manual_tool_call_results"), dict)
        else {},
    }


def _normalize_key(key: Any) -> str:
    return str(key).strip().lower().replace("-", "_").replace(" ", "_")


def _find_secret_like_paths(data: Any, prefix: str = "") -> list[str]:
    matches: list[str] = []
    if isinstance(data, dict):
        for key, value in data.items():
            normalized_key = _normalize_key(key)
            current_path = f"{prefix}.{key}" if prefix else str(key)
            if normalized_key in FORBIDDEN_FIELD_NAMES:
                matches.append(current_path)
            matches.extend(_find_secret_like_paths(value, current_path))
    elif isinstance(data, list):
        for index, item in enumerate(data):
            current_path = f"{prefix}[{index}]"
            matches.extend(_find_secret_like_paths(item, current_path))
    return matches

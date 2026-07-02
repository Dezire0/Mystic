from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.mcp.import_verification import (  # noqa: E402
    REQUIRED_TOOLS,
    artifact_contains_secret_like_fields,
    default_verification_artifact_path,
    validate_import_verification_artifact,
)
from scripts.run_remote_mcp_lab_smoke import now_iso  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a strict runtime artifact after manually verifying ChatGPT Developer Mode remote MCP import."
    )
    parser.add_argument("--root-path", default=str(ROOT), help="Mystic repository root path.")
    parser.add_argument("--public-endpoint", required=True, help="Public Mystic endpoint, without /mcp.")
    parser.add_argument("--output", default="", help="Optional output path for the runtime verification artifact.")
    parser.add_argument(
        "--notes",
        default="No secrets. No tokens. Manual verification only.",
        help="Optional operator note stored in the artifact.",
    )
    parser.add_argument("--confirm-imported", action="store_true", help="Confirm ChatGPT Developer Mode import succeeded.")
    parser.add_argument("--confirm-oauth-flow", action="store_true", help="Confirm OAuth flow completed successfully.")
    parser.add_argument("--confirm-tools-visible", action="store_true", help="Confirm required tools were visible.")
    parser.add_argument(
        "--confirm-tool-calls-passed",
        action="store_true",
        help="Confirm required manual tool calls passed in ChatGPT.",
    )
    return parser


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def build_artifact(public_endpoint: str, *, notes: str) -> dict[str, Any]:
    endpoint = public_endpoint.rstrip("/")
    return {
        "artifact_version": 1,
        "verified_at": now_iso(),
        "verified_by": "manual",
        "public_endpoint": endpoint,
        "mcp_endpoint": f"{endpoint}/mcp",
        "chatgpt_developer_mode_imported": True,
        "oauth_flow_completed": True,
        "tools_list_visible_in_chatgpt": True,
        "required_tools_visible": list(REQUIRED_TOOLS),
        "manual_tool_call_results": {tool: "passed" for tool in REQUIRED_TOOLS},
        "notes": notes,
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    missing_flags = [
        flag
        for flag, enabled in (
            ("--confirm-imported", args.confirm_imported),
            ("--confirm-oauth-flow", args.confirm_oauth_flow),
            ("--confirm-tools-visible", args.confirm_tools_visible),
            ("--confirm-tool-calls-passed", args.confirm_tool_calls_passed),
        )
        if not enabled
    ]
    if missing_flags:
        print(
            json.dumps(
                {
                    "created": False,
                    "error": "all manual confirmation flags are required",
                    "missing_flags": missing_flags,
                },
                indent=2,
                ensure_ascii=True,
            )
        )
        return 1

    root_path = Path(args.root_path)
    output_path = Path(args.output) if args.output else default_verification_artifact_path(root_path)
    artifact = build_artifact(args.public_endpoint, notes=args.notes)
    if artifact_contains_secret_like_fields(artifact):
        print(json.dumps({"created": False, "error": "artifact contains forbidden secret-like fields"}, indent=2))
        return 1

    validation = validate_import_verification_artifact(artifact, public_endpoint=args.public_endpoint)
    if not validation["verified"]:
        print(
            json.dumps(
                {
                    "created": False,
                    "error": "artifact validation failed",
                    "validation": validation,
                },
                indent=2,
                ensure_ascii=True,
            )
        )
        return 1

    write_json(output_path, artifact)
    print(
        json.dumps(
            {
                "created": True,
                "output_path": str(output_path),
                "verified_at": artifact["verified_at"],
                "public_endpoint": artifact["public_endpoint"],
                "required_tools_visible": artifact["required_tools_visible"],
            },
            indent=2,
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

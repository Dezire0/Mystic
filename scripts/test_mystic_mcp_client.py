from __future__ import annotations

import argparse
import json
from typing import Any
from urllib.request import Request, urlopen


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run HTTP MCP client checks against the Mystic /mcp endpoint.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8765", help="Base Mystic URL, without /mcp suffix.")
    parser.add_argument(
        "--scenario",
        default="public-tool-suite",
        choices=["ping", "public-tool-suite"],
        help="Which MCP verification flow to run.",
    )
    return parser


def post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Mystic MCP Client)",
        },
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8")
        return {"status": response.status, "body": json.loads(body)}


def mcp_request(base_url: str, *, request_id: int, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        payload["params"] = params
    return post_json(f"{base_url.rstrip('/')}/mcp", payload)


def run_ping(base_url: str) -> dict[str, Any]:
    initialize = mcp_request(base_url, request_id=1, method="initialize")
    ping = mcp_request(base_url, request_id=2, method="ping")
    return {"initialize": initialize, "ping": ping}


def run_public_tool_suite(base_url: str) -> dict[str, Any]:
    results = run_ping(base_url)
    results["tools_list"] = mcp_request(base_url, request_id=3, method="tools/list")
    results["status_call"] = mcp_request(
        base_url,
        request_id=4,
        method="tools/call",
        params={"name": "mystic_status", "arguments": {}},
    )
    results["verify_call"] = mcp_request(
        base_url,
        request_id=5,
        method="tools/call",
        params={
            "name": "mystic_verify_answer",
            "arguments": {
                "problem": "positive integers x, y satisfy x + y = 5",
                "candidate_answer": "Candidate solution: (2,3)",
            },
        },
    )
    results["call_model"] = mcp_request(
        base_url,
        request_id=6,
        method="tools/call",
        params={
            "name": "mystic_call_model",
            "arguments": {
                "model_id": "local_raven",
                "role": "critique",
                "task": "Critique the candidate answer.",
                "problem": "positive integers x, y satisfy x + y = 5. Candidate solution: (2,3).",
            },
        },
    )
    results["compare_models"] = mcp_request(
        base_url,
        request_id=7,
        method="tools/call",
        params={
            "name": "mystic_compare_models",
            "arguments": {
                "problem": "positive integers x, y satisfy x + y = 5. Candidate solution: (2,3).",
                "models": ["local_raven", "local_raven"],
                "task": "Critique whether the candidate solution is valid.",
                "include_verifier": True,
            },
        },
    )
    results["research_table"] = mcp_request(
        base_url,
        request_id=8,
        method="tools/call",
        params={
            "name": "mystic_run_research_table",
            "arguments": {
                "problem": "Investigate whether candidate solution (2,3) satisfies positive integers x, y with x + y = 5 and x <= y.",
                "participants": ["local_raven", "local_raven"],
                "mode": "discovery_debate",
                "max_rounds": 2,
                "enable_tools": True,
                "tools": ["mystic_verify_answer"],
            },
        },
    )
    return results


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.scenario == "ping":
        payload = run_ping(args.base_url)
    else:
        payload = run_public_tool_suite(args.base_url)
    print(json.dumps(payload, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import shutil
import sys
from typing import Any
import uuid

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mystic.mcp.tools import MysticToolbox
from mystic.research_table.storage import ResearchTableStorage


PROBLEM = "Find all positive integers x <= y such that x + y = 5."
PRESETS: dict[str, list[str]] = {
    "local-gemini": ["local_prime", "gemini_cli"],
    "local-claude": ["local_prime", "claude_cli"],
    "gemini-claude": ["gemini_cli", "claude_cli"],
    "local-gemini-claude": ["local_prime", "gemini_cli", "claude_cli"],
}
PHASE_ORDER = [
    "independent_discovery",
    "discovery_sharing",
    "cross_critique",
    "tool_verification",
    "revision_after_evidence",
    "final_synthesis",
    "interactive_follow_up",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run an optional Research Table CLI-provider smoke session.")
    parser.add_argument(
        "--root-path",
        default=str(REPO_ROOT),
        help="Mystic repository root. Defaults to the current workspace root.",
    )
    parser.add_argument(
        "--preset",
        default="local-gemini",
        choices=[*PRESETS.keys(), "all"],
        help="Participant preset to run. Use 'all' to run every preset sequentially.",
    )
    parser.add_argument(
        "--continue-auth-required",
        action="store_true",
        help="Include installed but unauthenticated CLI providers so the session records AUTH_REQUIRED turns.",
    )
    parser.add_argument(
        "--run-id",
        default="",
        help="Optional explicit run identifier. Defaults to a timestamped id.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root_path = Path(args.root_path)
    toolbox = MysticToolbox(root_path=root_path)
    if args.preset == "all":
        summaries = []
        batch_id = args.run_id or _default_run_id("all")
        for preset_name in PRESETS:
            summary = run_cli_smoke(
                root_path=root_path,
                preset_name=preset_name,
                continue_auth_required=args.continue_auth_required,
                toolbox=toolbox,
                run_id=f"{batch_id}-{preset_name}",
            )
            summaries.append(summary)
        print(json.dumps({"batch_run_id": batch_id, "summaries": summaries}, indent=2))
        return 0

    summary = run_cli_smoke(
        root_path=root_path,
        preset_name=args.preset,
        continue_auth_required=args.continue_auth_required,
        toolbox=toolbox,
        run_id=args.run_id or None,
    )
    print(json.dumps(summary, indent=2))
    return 0


def run_cli_smoke(
    *,
    root_path: Path,
    preset_name: str,
    continue_auth_required: bool,
    toolbox: MysticToolbox | Any | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    root_path = Path(root_path)
    toolbox = toolbox or MysticToolbox(root_path=root_path)
    if preset_name not in PRESETS:
        raise ValueError(f"unsupported preset: {preset_name}")

    requested = PRESETS[preset_name]
    status = toolbox.mystic_status()
    provider_statuses = {
        model_id: _compact_provider_status(status.get("models", {}).get(model_id, {}))
        for model_id in requested
    }
    selected, skipped = _select_participants(
        requested=requested,
        provider_statuses=provider_statuses,
        continue_auth_required=continue_auth_required,
    )

    summary: dict[str, Any] = {
        "preset": preset_name,
        "selected_participants": requested,
        "effective_participants": selected,
        "skipped_participants": skipped,
        "provider_auth_statuses": provider_statuses,
        "completed_phases": [],
        "auth_required_turns": [],
        "error_turns": [],
        "discoveries_count": 0,
        "verified_discoveries_count": 0,
        "refuted_discoveries_count": 0,
        "final_status": "SKIPPED",
        "final_decision_source": "not_run",
        "continue_auth_required": continue_auth_required,
    }

    scenario_dir = _scenario_dir(root_path=root_path, preset_name=preset_name, run_id=run_id)
    scenario_dir.mkdir(parents=True, exist_ok=True)

    if len(selected) < 2:
        summary["reason"] = "Not enough eligible participants to run a Research Table session."
        _write_summary(scenario_dir, summary)
        summary["summary_path"] = str((scenario_dir / "summary.json").resolve())
        return summary

    result = toolbox.mystic_run_research_table(
        problem=PROBLEM,
        participants=selected,
        mode="discovery_debate",
        max_rounds=2,
        enable_tools=True,
        tools=["mystic_verify_answer"],
        controller="gpt_controller",
    )
    session_id = str(result["session_id"])
    storage = ResearchTableStorage(root_path)
    session = storage.load_session(session_id)

    summary.update(
        {
            "session_id": session_id,
            "completed_phases": _completed_phases(session),
            "auth_required_turns": _compact_turns(session, status="AUTH_REQUIRED"),
            "error_turns": _compact_turns(session, status="ERROR"),
            "discoveries_count": len(session.get("discoveries", [])),
            "verified_discoveries_count": sum(
                1 for item in session.get("discoveries", []) if str(item.get("status", "")).lower() == "verified"
            ),
            "refuted_discoveries_count": sum(
                1 for item in session.get("discoveries", []) if str(item.get("status", "")).lower() == "refuted"
            ),
            "final_status": str(session.get("final_status", "UNKNOWN")),
            "final_decision_source": str(session.get("final_decision_source", "model_outputs")),
        }
    )

    session_dir = root_path / "mystic_data" / "research_table_sessions" / session_id
    shutil.copytree(session_dir, scenario_dir / "session", dirs_exist_ok=True)
    _write_summary(scenario_dir, summary)
    summary["summary_path"] = str((scenario_dir / "summary.json").resolve())
    return summary


def _select_participants(
    *,
    requested: list[str],
    provider_statuses: dict[str, dict[str, Any]],
    continue_auth_required: bool,
) -> tuple[list[str], list[dict[str, Any]]]:
    selected: list[str] = []
    skipped: list[dict[str, Any]] = []
    for model_id in requested:
        payload = provider_statuses.get(model_id, {})
        state = str(payload.get("state", "missing"))
        if state == "ready":
            selected.append(model_id)
            continue
        if state == "not_authenticated" and continue_auth_required:
            selected.append(model_id)
            continue
        skipped.append(
            {
                "model_id": model_id,
                "state": state,
                "message": str(payload.get("message", "")),
            }
        )
    return selected, skipped


def _compact_provider_status(payload: dict[str, Any]) -> dict[str, Any]:
    status = payload.get("status", {})
    return {
        "provider": str(payload.get("provider", "")),
        "model_name": str(payload.get("model_name", "")),
        "state": str(status.get("state", "missing")),
        "message": str(status.get("message", "")),
        "available": bool(status.get("available", False)),
        "authenticated": bool(status.get("authenticated", False)),
    }


def _completed_phases(session: dict[str, Any]) -> list[str]:
    return [phase for phase in PHASE_ORDER if any(str(turn.get("phase", "")) == phase for turn in session.get("turns", []))]


def _compact_turns(session: dict[str, Any], *, status: str) -> list[dict[str, Any]]:
    return [
        {
            "turn_id": str(turn.get("turn_id", "")),
            "phase": str(turn.get("phase", "")),
            "speaker_id": str(turn.get("speaker_id", "")),
            "provider": str(turn.get("provider", "")),
            "model_name": str(turn.get("model_name", "")),
            "role": str(turn.get("role", "")),
            "status": str(turn.get("status", "")),
            "content": str(turn.get("content", ""))[:240],
        }
        for turn in session.get("turns", [])
        if str(turn.get("status", "")) == status
    ]


def _scenario_dir(*, root_path: Path, preset_name: str, run_id: str | None) -> Path:
    label = run_id or _default_run_id(preset_name)
    return root_path / "mystic_data" / "e2e" / "cli_smoke" / label


def _default_run_id(label: str) -> str:
    return f"{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}-{label}"


def _write_summary(path: Path, payload: dict[str, Any]) -> None:
    (path / "summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())

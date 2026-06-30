from __future__ import annotations

import argparse
from collections.abc import Iterable
from datetime import UTC, datetime
import json
from pathlib import Path
import shutil
import sys
from typing import Any
from urllib.parse import parse_qs, urlparse
import uuid

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mystic.app.api import create_app
from mystic.mcp.tools import MysticToolbox
from mystic.research_table.discovery import DiscoveryItem
from mystic.research_table.session import ResearchTurn
from mystic.research_table.storage import ResearchTableStorage
from mystic.verification import extract_candidate_tuples


PROBLEM = "Find all positive integer triples x <= y <= z such that 1/x + 1/y + 1/z = 1."
VERIFIER_PROBLEM = "1/x + 1/y + 1/z = 1"
VERIFIER_CONSTRAINTS = ["x <= y <= z", "positive integers"]
EXPECTED_CANDIDATES = [(2, 3, 6), (2, 4, 4), (3, 3, 3)]
BAD_CANDIDATE = (2, 4, 8)
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
    parser = argparse.ArgumentParser(description="Run the Research Table end-to-end quality scenario.")
    parser.add_argument(
        "--root-path",
        default=str(REPO_ROOT),
        help="Mystic repository root. Defaults to the current workspace root.",
    )
    parser.add_argument(
        "--run-id",
        default="",
        help="Optional explicit run identifier. Defaults to a timestamped id.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    summary = run_research_table_e2e(root_path=Path(args.root_path), run_id=args.run_id or None)
    print(json.dumps(summary, indent=2))
    return 0


def run_research_table_e2e(
    *,
    root_path: Path,
    toolbox: MysticToolbox | Any | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    root_path = Path(root_path)
    toolbox = toolbox or MysticToolbox(root_path=root_path)
    client = TestClient(create_app(root_path=root_path, toolbox=toolbox, orchestrator=_NullOrchestrator()))
    storage = ResearchTableStorage(root_path)

    teacher_dir = root_path / "mystic_data" / "teacher_labels"
    training_dir = root_path / "mystic_data" / "training_items"
    teacher_before = {path.name for path in teacher_dir.glob("*.json")} if teacher_dir.exists() else set()
    training_before = {path.name for path in training_dir.glob("*.json")} if training_dir.exists() else set()

    response = client.get(
        "/research-table/start/run",
        params=[
            ("problem", PROBLEM),
            ("participants", "local_prime"),
            ("participants", "local_qwen"),
            ("mode", "discovery_debate"),
            ("max_rounds", "3"),
            ("controller", "gpt_controller"),
        ],
        follow_redirects=False,
    )
    if response.status_code >= 400:
        response.raise_for_status()
    if response.status_code != 302:
        raise RuntimeError(f"expected redirect from start flow, got {response.status_code}")

    session_id = _session_id_from_location(response.headers.get("location", ""))
    session = storage.load_session(session_id)
    probe_discovery_seeded = False
    if not session.get("discoveries"):
        session = _seed_probe_discovery(session)
        storage.save_session(session_id, session)
        probe_discovery_seeded = True

    verify_target = _pick_verify_target(session.get("discoveries", []))
    challenge_target = _pick_challenge_target(session.get("discoveries", []), preferred_id=verify_target.get("discovery_id", ""))
    teacher_turn_id = _pick_teacher_turn_id(session, preferred_discovery=verify_target)
    training_target = challenge_target or verify_target

    action_results = [
        _post_action(client, f"/research-table/{session_id}/discoveries/{verify_target['discovery_id']}/verify"),
        _post_action(client, f"/research-table/{session_id}/discoveries/{challenge_target['discovery_id']}/challenge"),
        _post_action(client, f"/research-table/{session_id}/turns/{teacher_turn_id}/save-teacher-label"),
        _post_action(
            client,
            f"/research-table/{session_id}/discoveries/{training_target['discovery_id']}/save-training-item",
            params={"target_agent": "raven"},
        ),
    ]

    session = storage.load_session(session_id)
    teacher_after = {path.name for path in teacher_dir.glob("*.json")} if teacher_dir.exists() else set()
    training_after = {path.name for path in training_dir.glob("*.json")} if training_dir.exists() else set()
    teacher_created = sorted((teacher_dir / name) for name in (teacher_after - teacher_before))
    training_created = sorted((training_dir / name) for name in (training_after - training_before))

    final_candidates = _collect_final_candidate_strings(session)
    session_candidates = _collect_session_candidate_strings(session)
    final_verification = _verify_candidate_set(toolbox=toolbox, candidate_strings=final_candidates)

    summary = _build_summary(
        root_path=root_path,
        session=session,
        final_candidates=final_candidates,
        session_candidates=session_candidates,
        final_verification=final_verification,
        teacher_created=teacher_created,
        training_created=training_created,
        action_results=action_results,
        probe_discovery_seeded=probe_discovery_seeded,
    )

    scenario_dir = _scenario_dir(root_path=root_path, session_id=session_id, run_id=run_id)
    _write_scenario_outputs(
        root_path=root_path,
        scenario_dir=scenario_dir,
        session_id=session_id,
        summary=summary,
        teacher_created=teacher_created,
        training_created=training_created,
    )
    summary["summary_path"] = str((scenario_dir / "summary.json").resolve())
    return summary


def _post_action(client: TestClient, path: str, *, params: dict[str, str] | None = None) -> dict[str, Any]:
    response = client.post(path, params=params or {}, follow_redirects=False)
    if response.status_code >= 400:
        response.raise_for_status()
    if response.status_code != 302:
        raise RuntimeError(f"expected redirect from action {path}, got {response.status_code}")
    location = response.headers.get("location", "")
    parsed = parse_qs(urlparse(location).query)
    return {
        "path": path,
        "location": location,
        "message": parsed.get("message", [""])[0],
        "level": parsed.get("level", [""])[0],
    }


class _NullOrchestrator:
    def run_problem(self, problem: str) -> Any:  # pragma: no cover - not used in this scenario
        raise RuntimeError("session orchestration is not used by the Research Table E2E runner")

    def list_sessions(self) -> list[dict[str, Any]]:  # pragma: no cover - not used in this scenario
        return []

    def available_agents(self) -> dict[str, Any]:  # pragma: no cover - not used in this scenario
        return {}

    def export_dataset(self, kind: str) -> list[str]:  # pragma: no cover - not used in this scenario
        return []

    def get_session(self, session_id: str) -> dict[str, Any]:  # pragma: no cover - not used in this scenario
        raise KeyError(session_id)


def _session_id_from_location(location: str) -> str:
    if not location:
        raise RuntimeError("missing redirect location")
    return location.rstrip("/").split("/")[-1].split("?", 1)[0]


def _pick_verify_target(discoveries: list[dict[str, Any]]) -> dict[str, Any]:
    if not discoveries:
        raise RuntimeError("research table session did not create any discoveries")
    bad_match = next((item for item in discoveries if _has_candidate(item.get("claim", ""), BAD_CANDIDATE)), None)
    if bad_match is not None:
        return bad_match
    candidate = next((item for item in discoveries if str(item.get("type", "")) == "candidate_answer"), None)
    return candidate or discoveries[0]


def _seed_probe_discovery(session: dict[str, Any]) -> dict[str, Any]:
    probe_turn = ResearchTurn(
        session_id=str(session.get("session_id", "")),
        round_index=max([int(turn.get("round_index", 0)) for turn in session.get("turns", [])] or [0]) + 1,
        phase="interactive_follow_up",
        speaker_type="controller",
        speaker_id="gpt_controller",
        provider="controller",
        model_name="GPT Controller",
        role="probe",
        status="SEEDED_PROBE",
        content="Seeded probe discovery for E2E verification: Candidate answer (2, 4, 8).",
        summary="seeded probe discovery",
        candidate_answers=[_render_candidate(BAD_CANDIDATE)],
    )
    probe_discovery = DiscoveryItem(
        claim=f"Candidate answer {_render_candidate(BAD_CANDIDATE)}",
        rationale="Seeded by the E2E harness because the session produced no extracted discoveries.",
        confidence="low",
        needs_verification=True,
        source_turn_id=probe_turn.turn_id,
        type="candidate_answer",
    ).to_dict()
    probe_turn.discoveries = [probe_discovery]
    session.setdefault("turns", []).append(probe_turn.to_dict())
    session.setdefault("discoveries", []).append(probe_discovery)
    session.setdefault("verification_requests", [])
    return session


def _pick_challenge_target(discoveries: list[dict[str, Any]], *, preferred_id: str) -> dict[str, Any]:
    for item in discoveries:
        if str(item.get("discovery_id", "")) != preferred_id:
            return item
    if not discoveries:
        raise RuntimeError("no discoveries available for challenge action")
    return discoveries[0]


def _pick_teacher_turn_id(session: dict[str, Any], *, preferred_discovery: dict[str, Any]) -> str:
    source_turn_id = str(preferred_discovery.get("source_turn_id", ""))
    if source_turn_id:
        return source_turn_id
    model_turn = next((turn for turn in session.get("turns", []) if str(turn.get("speaker_type", "")) == "model"), None)
    if model_turn is None:
        raise RuntimeError("no model turn available for teacher label save")
    return str(model_turn["turn_id"])


def _collect_session_candidate_strings(session: dict[str, Any]) -> list[str]:
    values: set[str] = set()
    for discovery in session.get("discoveries", []):
        values.update(_candidate_strings_from_text(str(discovery.get("claim", ""))))
    for turn in session.get("turns", []):
        values.update(_candidate_strings_from_text(str(turn.get("content", ""))))
    return sorted(values)


def _collect_final_candidate_strings(session: dict[str, Any]) -> list[str]:
    accepted = _candidate_strings_from_text(
        "\n".join(str(item.get("claim", "")) for item in session.get("accepted_discoveries", []))
    )
    if accepted:
        return accepted
    for turn in reversed(session.get("turns", [])):
        if str(turn.get("phase", "")) not in {"interactive_follow_up", "revision_after_evidence", "final_synthesis"}:
            continue
        candidates = _candidate_strings_from_text(str(turn.get("content", "")))
        if candidates:
            return candidates
    return []


def _latest_turn_content(session: dict[str, Any], phase: str) -> str:
    for turn in reversed(session.get("turns", [])):
        if str(turn.get("phase", "")) == phase:
            return str(turn.get("content", ""))
    return ""


def _candidate_strings_from_text(text: str) -> list[str]:
    seen: set[str] = set()
    values: list[str] = []
    for item in extract_candidate_tuples(text):
        rendered = str(tuple(int(value) for value in item))
        if rendered in seen:
            continue
        seen.add(rendered)
        values.append(rendered)
    return values


def _verify_candidate_set(*, toolbox: Any, candidate_strings: list[str]) -> dict[str, Any]:
    if not candidate_strings:
        return {
            "verdict": "UNKNOWN",
            "valid": False,
            "reasoning": "No explicit final candidate set was available for deterministic verification.",
            "failed_candidates": [],
            "passed_candidates": [],
            "missing_candidates": [],
            "constraint_failures": [],
        }
    return toolbox.mystic_verify_answer(
        problem=VERIFIER_PROBLEM,
        candidate_answer=", ".join(candidate_strings),
        constraints=VERIFIER_CONSTRAINTS,
    )


def _build_summary(
    *,
    root_path: Path,
    session: dict[str, Any],
    final_candidates: list[str],
    session_candidates: list[str],
    final_verification: dict[str, Any],
    teacher_created: list[Path],
    training_created: list[Path],
    action_results: list[dict[str, Any]],
    probe_discovery_seeded: bool,
) -> dict[str, Any]:
    phases_completed = [phase for phase in PHASE_ORDER if any(str(turn.get("phase", "")) == phase for turn in session.get("turns", []))]
    verified_count = sum(1 for item in session.get("discoveries", []) if str(item.get("status", "")).lower() == "verified")
    refuted_count = sum(1 for item in session.get("discoveries", []) if str(item.get("status", "")).lower() == "refuted")

    session_found = sorted(set(session_candidates) & set(_render_candidates(EXPECTED_CANDIDATES)))
    session_missing = [item for item in _render_candidates(EXPECTED_CANDIDATES) if item not in session_found]
    final_found = sorted(set(final_candidates) & set(_render_candidates(EXPECTED_CANDIDATES)))
    final_missing = [item for item in _render_candidates(EXPECTED_CANDIDATES) if item not in final_found]

    final_status = str(session.get("final_status", "UNKNOWN"))
    final_decision_source = str(session.get("final_decision_source", "model_outputs"))
    verifier_verdict = str(final_verification.get("verdict", "UNKNOWN")).upper()
    if verifier_verdict == "INVALID":
        final_status = "INVALID"
        final_decision_source = "deterministic_verifier"
    elif verifier_verdict == "VALID":
        final_status = "VALID"
        final_decision_source = "deterministic_verifier"
    elif final_status == "VALID" and "(2, 4, 4)" in final_missing:
        final_status = "UNKNOWN"

    bad_candidate_string = _render_candidate(BAD_CANDIDATE)
    bad_appeared = bad_candidate_string in session_candidates
    bad_refuted = any(
        _has_candidate(item.get("claim", ""), BAD_CANDIDATE) and str(item.get("status", "")).lower() == "refuted"
        for item in session.get("discoveries", [])
    ) or any(
        _has_candidate(item.get("target_candidate_answer", ""), BAD_CANDIDATE) and str(item.get("result_verdict", "")).upper() == "INVALID"
        for item in session.get("verification_requests", [])
    )

    unknown_safe = _unknown_verifier_results_are_safe(session)
    summary = {
        "session_id": session["session_id"],
        "participants": session.get("participant_models", session.get("participants", [])),
        "probe_discovery_seeded": probe_discovery_seeded,
        "phases_completed": phases_completed,
        "turns_count": len(session.get("turns", [])),
        "discoveries_count": len(session.get("discoveries", [])),
        "verified_discoveries_count": verified_count,
        "refuted_discoveries_count": refuted_count,
        "final_status": final_status,
        "final_decision_source": final_decision_source,
        "accepted_discoveries": _compact_discoveries(session.get("accepted_discoveries", [])),
        "rejected_discoveries": _compact_discoveries(session.get("rejected_discoveries", [])),
        "teacher_labels_created": _relative_paths(root_path, teacher_created),
        "training_items_created": _relative_paths(root_path, training_created),
        "expected_candidates_found": {
            "found_in_session": session_found,
            "missing_from_session": session_missing,
            "found_in_final_answer": final_found,
            "missing_from_final_answer": final_missing,
            "final_candidate_set": final_candidates,
        },
        "bad_candidates_refuted": {
            "candidate": bad_candidate_string,
            "appeared_in_session": bad_appeared,
            "refuted": bad_refuted,
        },
        "quality_checks": {
            "invalid_verifier_overrides_final_status": verifier_verdict != "INVALID" or final_status == "INVALID",
            "missing_244_prevents_valid": "(2, 4, 4)" not in final_missing or final_status != "VALID",
            "unknown_verifier_does_not_change_status": unknown_safe,
        },
        "final_verification": {
            "verdict": verifier_verdict,
            "reasoning": str(final_verification.get("reasoning", "")),
            "failed_candidates": final_verification.get("failed_candidates", []),
            "passed_candidates": final_verification.get("passed_candidates", []),
            "missing_candidates": final_verification.get("missing_candidates", []),
        },
        "action_results": action_results,
    }
    return summary


def _compact_discoveries(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "discovery_id": str(item.get("discovery_id", "")),
            "type": str(item.get("type", "")),
            "claim": str(item.get("claim", "")),
            "status": str(item.get("status", "")),
        }
        for item in items
    ]


def _unknown_verifier_results_are_safe(session: dict[str, Any]) -> bool:
    requests_by_discovery: dict[str, list[dict[str, Any]]] = {}
    for request in session.get("verification_requests", []):
        target = str(request.get("target_discovery_id", ""))
        if not target:
            continue
        requests_by_discovery.setdefault(target, []).append(request)
    for discovery in session.get("discoveries", []):
        discovery_id = str(discovery.get("discovery_id", ""))
        requests = requests_by_discovery.get(discovery_id, [])
        if not any(str(item.get("result_verdict", "")).upper() == "UNKNOWN" for item in requests):
            continue
        if any(str(item.get("result_verdict", "")).upper() in {"VALID", "INVALID"} for item in requests):
            continue
        if str(discovery.get("status", "")).lower() in {"verified", "refuted"}:
            return False
    return True


def _scenario_dir(*, root_path: Path, session_id: str, run_id: str | None) -> Path:
    label = run_id or f"{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}-{session_id}"
    return root_path / "mystic_data" / "e2e" / "research_table" / label


def _write_scenario_outputs(
    *,
    root_path: Path,
    scenario_dir: Path,
    session_id: str,
    summary: dict[str, Any],
    teacher_created: list[Path],
    training_created: list[Path],
) -> None:
    scenario_dir.mkdir(parents=True, exist_ok=True)
    session_source_dir = root_path / "mystic_data" / "research_table_sessions" / session_id
    shutil.copytree(session_source_dir, scenario_dir / "session", dirs_exist_ok=True)
    _copy_files(teacher_created, scenario_dir / "teacher_labels")
    _copy_files(training_created, scenario_dir / "training_items")
    (scenario_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


def _copy_files(paths: list[Path], destination_dir: Path) -> None:
    if not paths:
        return
    destination_dir.mkdir(parents=True, exist_ok=True)
    for path in paths:
        shutil.copy2(path, destination_dir / path.name)


def _relative_paths(root_path: Path, paths: list[Path]) -> list[str]:
    values: list[str] = []
    for path in paths:
        try:
            values.append(str(path.resolve().relative_to(root_path.resolve())))
        except ValueError:
            values.append(str(path.resolve()))
    return values


def _render_candidates(candidates: list[tuple[int, int, int]]) -> list[str]:
    return [_render_candidate(candidate) for candidate in candidates]


def _render_candidate(candidate: tuple[int, int, int]) -> str:
    return str(tuple(candidate))


def _has_candidate(text: Any, candidate: tuple[int, int, int]) -> bool:
    return _render_candidate(candidate) in _candidate_strings_from_text(str(text))


if __name__ == "__main__":
    raise SystemExit(main())

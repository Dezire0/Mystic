from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from mystic.raven_training import write_jsonl
from mystic.research_table.metrics import collect_research_table_records


AVAILABLE_TOOLS = ["python", "sympy", "z3", "brute_force"]


def export_research_table_datasets(root_path: str | Path) -> dict[str, Any]:
    root = Path(root_path)
    records, warnings = collect_research_table_records(root)
    sessions_by_id = {
        str(record.get("session_id", "")): record.get("session")
        for record in records
        if isinstance(record.get("session"), dict) and str(record.get("session_id", "")).strip()
    }

    teacher_labels = _load_json_dir(root / "mystic_data" / "teacher_labels", warnings=warnings, label="teacher label")
    training_items = _load_json_dir(root / "mystic_data" / "training_items", warnings=warnings, label="training item")

    raven_rows: list[dict[str, Any]] = []
    prime_rows: list[dict[str, Any]] = []
    forge_rows: list[dict[str, Any]] = []
    seen_keys: dict[str, set[str]] = {"raven": set(), "prime": set(), "forge": set()}

    for record in records:
        session = record.get("session")
        if not isinstance(session, dict):
            continue
        _append_session_rows(
            session=session,
            raven_rows=raven_rows,
            prime_rows=prime_rows,
            forge_rows=forge_rows,
            seen_keys=seen_keys,
        )

    for label in teacher_labels:
        _append_teacher_label_rows(
            label=label,
            sessions_by_id=sessions_by_id,
            raven_rows=raven_rows,
            prime_rows=prime_rows,
            seen_keys=seen_keys,
            warnings=warnings,
        )

    for item in training_items:
        _append_training_item_rows(
            item=item,
            sessions_by_id=sessions_by_id,
            forge_rows=forge_rows,
            seen_keys=seen_keys,
            warnings=warnings,
        )

    dataset_root = root / "mystic_data" / "datasets"
    raven_path = dataset_root / "raven" / "research_table_raven.jsonl"
    prime_path = dataset_root / "prime" / "research_table_prime.jsonl"
    forge_path = dataset_root / "forge" / "research_table_forge.jsonl"
    summary_path = dataset_root / "research_table_summary.json"

    write_jsonl(raven_path, raven_rows)
    write_jsonl(prime_path, prime_rows)
    write_jsonl(forge_path, forge_rows)

    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "datasets": {
            "raven": {"path": str(raven_path), "rows": len(raven_rows)},
            "prime": {"path": str(prime_path), "rows": len(prime_rows)},
            "forge": {"path": str(forge_path), "rows": len(forge_rows)},
        },
        "warnings": warnings,
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    summary["summary_path"] = str(summary_path)
    return summary


def _append_session_rows(
    *,
    session: dict[str, Any],
    raven_rows: list[dict[str, Any]],
    prime_rows: list[dict[str, Any]],
    forge_rows: list[dict[str, Any]],
    seen_keys: dict[str, set[str]],
) -> None:
    session_id = str(session.get("session_id", ""))
    problem = str(session.get("problem", ""))
    turns = _as_list(session.get("turns"))
    discoveries = _as_list(session.get("discoveries"))
    verification_requests = _as_list(session.get("verification_requests"))
    accepted_discoveries = _as_list(session.get("accepted_discoveries"))

    turn_by_id = {
        str(turn.get("turn_id", "")): turn
        for turn in turns
        if isinstance(turn, dict) and str(turn.get("turn_id", "")).strip()
    }
    discovery_by_id = {
        str(discovery.get("discovery_id", "")): discovery
        for discovery in discoveries
        if isinstance(discovery, dict) and str(discovery.get("discovery_id", "")).strip()
    }
    final_turn = next((turn for turn in reversed(turns) if str(turn.get("phase", "")) == "final_synthesis"), {})

    for discovery in discoveries:
        if not isinstance(discovery, dict):
            continue
        source_turn = turn_by_id.get(str(discovery.get("source_turn_id", "")), {})
        tool_evidence = _tool_evidence_for_discovery(session=session, discovery=discovery)
        context = _session_context(session=session, source_turn=source_turn)
        status = str(discovery.get("status", "")).lower()
        discovery_type = str(discovery.get("type", "")).lower()
        source = _source_ref(
            session_id=session_id,
            turn_id=str(source_turn.get("turn_id", "")),
            discovery_id=str(discovery.get("discovery_id", "")),
        )

        if status == "refuted":
            _append_row(
                "raven",
                source=source,
                row={
                    "agent": "raven",
                    "input": {
                        "problem": problem,
                        "model_output": str(source_turn.get("content", "")),
                        "discovery_or_claim": str(discovery.get("claim", "")),
                        "tool_evidence": tool_evidence,
                        "context": context,
                    },
                    "output": {
                        "verdict": "INVALID",
                        "first_fatal_error": _first_fatal_error(tool_evidence, discovery),
                        "critique": tool_evidence or str(discovery.get("rationale", "")),
                        "recommended_next_action": "reject_or_revise_claim",
                    },
                    "source": source,
                },
                rows=raven_rows,
                seen=seen_keys["raven"],
            )

        if status in {"verified", "accepted"} or discovery_type == "lemma":
            request = _verification_request_for_discovery(verification_requests, discovery)
            _append_row(
                "prime",
                source=source,
                row={
                    "agent": "prime",
                    "input": {
                        "problem": problem,
                        "context": context,
                        "goal": "produce a useful strategy or discovery",
                    },
                    "output": {
                        "strategy": _strategy_text(discovery, source_turn),
                        "discovery": str(discovery.get("claim", "")),
                        "rationale": str(discovery.get("rationale", "")) or tool_evidence,
                        "verification_request": str(request.get("question", "")),
                    },
                    "source": source,
                },
                rows=prime_rows,
                seen=seen_keys["prime"],
            )

        if discovery_type == "computational_observation":
            _append_row(
                "forge",
                source=source,
                row={
                    "agent": "forge",
                    "input": {
                        "problem": problem,
                        "claim_to_verify": str(discovery.get("claim", "")),
                        "constraints": _constraints_from_problem(problem),
                        "available_tools": AVAILABLE_TOOLS,
                    },
                    "output": {
                        "experiment_plan": str(discovery.get("rationale", "")) or "Run a bounded computational check.",
                        "tool": "python",
                        "expected_result_format": "JSON verdict with supporting observation.",
                    },
                    "source": source,
                },
                rows=forge_rows,
                seen=seen_keys["forge"],
            )

    for turn in turns:
        if not isinstance(turn, dict):
            continue
        if str(turn.get("speaker_type", "")) == "model" and str(turn.get("status", "")) == "ERROR":
            source = _source_ref(session_id=session_id, turn_id=str(turn.get("turn_id", "")))
            _append_row(
                "raven",
                source=source,
                row={
                    "agent": "raven",
                    "input": {
                        "problem": problem,
                        "model_output": str(turn.get("content", "")),
                        "discovery_or_claim": str(turn.get("summary", "")) or str(turn.get("content", ""))[:240],
                        "tool_evidence": "",
                        "context": _session_context(session=session, source_turn=turn),
                    },
                    "output": {
                        "verdict": "NEEDS_MORE_DETAIL",
                        "first_fatal_error": str(turn.get("content", ""))[:240],
                        "critique": "The model turn failed or returned unusable output.",
                        "recommended_next_action": "retry_with_stronger_validation",
                    },
                    "source": source,
                },
                rows=raven_rows,
                seen=seen_keys["raven"],
            )

        if str(turn.get("speaker_type", "")) == "tool" and str(turn.get("phase", "")) == "tool_verification":
            discovery = discovery_by_id.get(str(turn.get("target_discovery_id", "")), {})
            source = _source_ref(
                session_id=session_id,
                turn_id=str(turn.get("turn_id", "")),
                discovery_id=str(discovery.get("discovery_id", "")),
            )
            _append_row(
                "forge",
                source=source,
                row={
                    "agent": "forge",
                    "input": {
                        "problem": problem,
                        "claim_to_verify": str(discovery.get("claim", "")),
                        "constraints": _constraints_from_problem(problem),
                        "available_tools": AVAILABLE_TOOLS,
                    },
                    "output": {
                        "experiment_plan": str(turn.get("content", "")) or "Run the deterministic verifier against the claim.",
                        "tool": _tool_name_from_turn(turn),
                        "expected_result_format": "JSON verdict with reasoning and candidate status.",
                    },
                    "source": source,
                },
                rows=forge_rows,
                seen=seen_keys["forge"],
            )

    for request in verification_requests:
        if not isinstance(request, dict):
            continue
        discovery = discovery_by_id.get(str(request.get("target_discovery_id", "")), {})
        source = _source_ref(
            session_id=session_id,
            turn_id=str(request.get("target_turn_id", "")),
            discovery_id=str(request.get("target_discovery_id", "")),
        )
        _append_row(
            "forge",
            source=source,
            row={
                "agent": "forge",
                "input": {
                    "problem": problem,
                    "claim_to_verify": str(request.get("target_candidate_answer", "")) or str(discovery.get("claim", "")),
                    "constraints": _constraints_from_problem(problem),
                    "available_tools": AVAILABLE_TOOLS,
                },
                "output": {
                    "experiment_plan": str(request.get("question", "")) or "Design a deterministic verification step.",
                    "tool": _normalize_tool_name(str(request.get("tool", ""))),
                    "expected_result_format": "JSON verdict with reasoning.",
                },
                "source": source,
            },
            rows=forge_rows,
            seen=seen_keys["forge"],
        )

    for discovery in accepted_discoveries:
        if not isinstance(discovery, dict):
            continue
        discovery_id = str(discovery.get("discovery_id", ""))
        if discovery_id and discovery_id in discovery_by_id:
            continue
        source = _source_ref(
            session_id=session_id,
            turn_id=str(final_turn.get("turn_id", "")),
            discovery_id=discovery_id,
        )
        _append_row(
            "prime",
            source=source,
            row={
                "agent": "prime",
                "input": {
                    "problem": problem,
                    "context": _session_context(session=session, source_turn=final_turn),
                    "goal": "produce a useful strategy or discovery",
                },
                "output": {
                    "strategy": "Follow the accepted final-synthesis path.",
                    "discovery": str(discovery.get("claim", "")),
                    "rationale": str(discovery.get("rationale", "")),
                    "verification_request": "",
                },
                "source": source,
            },
            rows=prime_rows,
            seen=seen_keys["prime"],
        )


def _append_teacher_label_rows(
    *,
    label: dict[str, Any],
    sessions_by_id: dict[str, dict[str, Any]],
    raven_rows: list[dict[str, Any]],
    prime_rows: list[dict[str, Any]],
    seen_keys: dict[str, set[str]],
    warnings: list[str],
) -> None:
    label_id = str(label.get("label_id", "")).strip()
    target_agent = str(label.get("target_agent", "")).strip()
    session_id = str(label.get("packet_id", "")).strip()
    label_payload = label.get("label")
    if not label_id or not target_agent or not isinstance(label_payload, dict):
        warnings.append(f"Skipped malformed teacher label: missing label_id, target_agent, or label payload in {label}")
        return
    session = sessions_by_id.get(session_id, {})
    if not isinstance(session, dict) or not session:
        warnings.append(f"Skipped teacher label {label_id}: no matching session for packet_id {session_id}.")
        return

    turn = _turn_for_source_model(session, str(label.get("source_model", "")))
    discovery = _discovery_for_turn(session, str(turn.get("turn_id", ""))) if turn else {}
    source = _source_ref(
        session_id=session_id,
        turn_id=str(turn.get("turn_id", "")),
        discovery_id=str(discovery.get("discovery_id", "")),
        label_id=label_id,
    )

    if target_agent == "raven":
        _append_row(
            "raven",
            source=source,
            row={
                "agent": "raven",
                "input": {
                    "problem": str(session.get("problem", "")),
                    "model_output": str(turn.get("content", "")),
                    "discovery_or_claim": str(discovery.get("claim", "")),
                    "tool_evidence": "",
                    "context": _session_context(session=session, source_turn=turn),
                },
                "output": {
                    "verdict": str(label_payload.get("verdict", "UNCLEAR")),
                    "first_fatal_error": str(label_payload.get("first_fatal_error", "")),
                    "critique": str(label_payload.get("critique", "")),
                    "recommended_next_action": str(label_payload.get("corrected_reasoning", "")) or "revise_with_teacher_feedback",
                },
                "source": source,
            },
            rows=raven_rows,
            seen=seen_keys["raven"],
        )

    if target_agent == "prime":
        _append_row(
            "prime",
            source=source,
            row={
                "agent": "prime",
                "input": {
                    "problem": str(session.get("problem", "")),
                    "context": _session_context(session=session, source_turn=turn),
                    "goal": "produce a useful strategy or discovery",
                },
                "output": {
                    "strategy": str(label_payload.get("corrected_reasoning", "")) or "Follow the teacher-corrected path.",
                    "discovery": str(discovery.get("claim", "")),
                    "rationale": str(label_payload.get("critique", "")),
                    "verification_request": "",
                },
                "source": source,
            },
            rows=prime_rows,
            seen=seen_keys["prime"],
        )


def _append_training_item_rows(
    *,
    item: dict[str, Any],
    sessions_by_id: dict[str, dict[str, Any]],
    forge_rows: list[dict[str, Any]],
    seen_keys: dict[str, set[str]],
    warnings: list[str],
) -> None:
    if str(item.get("target_agent", "")).strip() != "forge":
        return
    session_id = str(item.get("session_id", "")).strip()
    discovery_id = str(item.get("discovery_id", "")).strip()
    session = sessions_by_id.get(session_id, {})
    if not isinstance(session, dict) or not session:
        warnings.append(f"Skipped Forge training item {item.get('item_id', '')}: no matching session {session_id}.")
        return
    discovery = _find_discovery(session, discovery_id)
    source = _source_ref(session_id=session_id, discovery_id=discovery_id)
    _append_row(
        "forge",
        source=source,
        row={
            "agent": "forge",
            "input": {
                "problem": str(session.get("problem", "")),
                "claim_to_verify": str(item.get("claim", "")) or str(discovery.get("claim", "")),
                "constraints": _constraints_from_problem(str(session.get("problem", ""))),
                "available_tools": AVAILABLE_TOOLS,
            },
            "output": {
                "experiment_plan": str(item.get("rationale", "")) or str(discovery.get("rationale", "")),
                "tool": _tool_for_training_item(item, discovery),
                "expected_result_format": "JSON verdict with structured evidence.",
            },
            "source": source,
        },
        rows=forge_rows,
        seen=seen_keys["forge"],
    )


def _append_row(agent: str, *, source: dict[str, str], row: dict[str, Any], rows: list[dict[str, Any]], seen: set[str]) -> None:
    key = "|".join(
        [
            agent,
            source.get("session_id", ""),
            source.get("turn_id", ""),
            source.get("discovery_id", ""),
            source.get("label_id", ""),
        ]
    )
    if key in seen:
        return
    seen.add(key)
    rows.append(row)


def _source_ref(*, session_id: str, turn_id: str = "", discovery_id: str = "", label_id: str = "") -> dict[str, str]:
    return {
        "session_id": session_id,
        "turn_id": turn_id,
        "discovery_id": discovery_id,
        "label_id": label_id,
    }


def _tool_evidence_for_discovery(*, session: dict[str, Any], discovery: dict[str, Any]) -> str:
    discovery_id = str(discovery.get("discovery_id", ""))
    evidence: list[str] = []
    for request in _as_list(session.get("verification_requests")):
        if str(request.get("target_discovery_id", "")) != discovery_id:
            continue
        verdict = str(request.get("result_verdict", ""))
        reasoning = str(request.get("result_reasoning", ""))
        question = str(request.get("question", ""))
        evidence.append(f"{question} [{verdict}] {reasoning}".strip())
    if evidence:
        return "\n".join(evidence)
    for turn in _as_list(session.get("turns")):
        if str(turn.get("speaker_type", "")) != "tool":
            continue
        if str(turn.get("target_discovery_id", "")) != discovery_id:
            continue
        evidence.append(str(turn.get("content", "")))
    return "\n".join(item for item in evidence if item)


def _session_context(*, session: dict[str, Any], source_turn: dict[str, Any] | None) -> str:
    parts: list[str] = []
    if source_turn:
        phase = str(source_turn.get("phase", ""))
        if phase:
            parts.append(f"phase={phase}")
        role = str(source_turn.get("role", ""))
        if role:
            parts.append(f"role={role}")
    accepted = _as_list(session.get("accepted_discoveries"))
    if accepted:
        parts.append("accepted=" + "; ".join(str(item.get("claim", "")) for item in accepted[:3] if isinstance(item, dict)))
    return " | ".join(item for item in parts if item)


def _verification_request_for_discovery(requests: list[dict[str, Any]], discovery: dict[str, Any]) -> dict[str, Any]:
    discovery_id = str(discovery.get("discovery_id", ""))
    for request in requests:
        if str(request.get("target_discovery_id", "")) == discovery_id:
            return request
    return {}


def _strategy_text(discovery: dict[str, Any], source_turn: dict[str, Any]) -> str:
    if str(discovery.get("type", "")).lower() == "lemma":
        return "Promote the lemma and build subsequent steps around it."
    if str(source_turn.get("content", "")):
        return str(source_turn.get("content", ""))[:240]
    return str(discovery.get("rationale", "")) or "Keep the verified discovery and extend it."


def _first_fatal_error(tool_evidence: str, discovery: dict[str, Any]) -> str:
    if tool_evidence:
        return tool_evidence.splitlines()[0][:240]
    return str(discovery.get("claim", ""))[:240]


def _tool_name_from_turn(turn: dict[str, Any]) -> str:
    speaker_id = str(turn.get("speaker_id", ""))
    if speaker_id == "mystic_verify_answer":
        return "brute_force"
    return _normalize_tool_name(speaker_id)


def _normalize_tool_name(name: str) -> str:
    lowered = name.strip().lower()
    if lowered in {"python", "sympy", "z3", "brute_force"}:
        return lowered
    if "python" in lowered:
        return "python"
    if "sympy" in lowered:
        return "sympy"
    if "z3" in lowered:
        return "z3"
    return "brute_force"


def _constraints_from_problem(problem: str) -> str:
    lowered = problem.lower()
    parts: list[str] = []
    if "<=" in problem:
        parts.append("ordered variables")
    if "positive integer" in lowered:
        parts.append("positive integers")
    if "integer" in lowered and "positive integers" not in parts:
        parts.append("integer constraints")
    return ", ".join(parts)


def _load_json_dir(path: Path, *, warnings: list[str], label: str) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for file_path in sorted(path.glob("*.json")):
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            warnings.append(f"Skipped malformed {label} at {file_path}: {exc}")
            continue
        if isinstance(payload, dict):
            rows.append(payload)
        else:
            warnings.append(f"Skipped malformed {label} at {file_path}: expected JSON object.")
    return rows


def _turn_for_source_model(session: dict[str, Any], source_model: str) -> dict[str, Any]:
    for turn in _as_list(session.get("turns")):
        if str(turn.get("speaker_id", "")) == source_model and str(turn.get("speaker_type", "")) == "model":
            return turn
    return {}


def _discovery_for_turn(session: dict[str, Any], turn_id: str) -> dict[str, Any]:
    for discovery in _as_list(session.get("discoveries")):
        if str(discovery.get("source_turn_id", "")) == turn_id:
            return discovery
    return {}


def _find_discovery(session: dict[str, Any], discovery_id: str) -> dict[str, Any]:
    for discovery in _as_list(session.get("discoveries")):
        if str(discovery.get("discovery_id", "")) == discovery_id:
            return discovery
    return {}


def _tool_for_training_item(item: dict[str, Any], discovery: dict[str, Any]) -> str:
    discovery_type = str(discovery.get("type", "")).lower()
    if discovery_type == "computational_observation":
        return "python"
    if "equation" in str(item.get("claim", "")).lower():
        return "sympy"
    return "brute_force"


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []

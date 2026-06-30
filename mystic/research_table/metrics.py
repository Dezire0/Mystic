from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any


PHASE_ORDER = [
    "independent_discovery",
    "discovery_sharing",
    "cross_critique",
    "tool_verification",
    "revision_after_evidence",
    "final_synthesis",
    "interactive_follow_up",
]


def summarize_research_table_metrics(root_path: str | Path) -> dict[str, Any]:
    root = Path(root_path)
    records, warnings = collect_research_table_records(root)

    session_metrics: list[dict[str, Any]] = []
    model_accumulators: dict[str, dict[str, Any]] = {}
    tool_accumulators: dict[str, dict[str, Any]] = {}

    for record in records:
        session_metric = _session_metric(record)
        session_metrics.append(session_metric)
        _update_model_metrics(model_accumulators, record, session_metric)
        _update_tool_metrics(tool_accumulators, record, session_metric)

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "sessions": sorted(
            (_public_session_metric(item) for item in session_metrics),
            key=lambda item: (str(item.get("created_at", "")), str(item.get("session_id", ""))),
        ),
        "models": sorted(
            (_finalize_model_metrics(item) for item in model_accumulators.values()),
            key=lambda item: str(item["model_id"]),
        ),
        "tools": sorted(
            (_finalize_tool_metrics(item) for item in tool_accumulators.values()),
            key=lambda item: str(item["tool_name"]),
        ),
        "warnings": warnings,
    }
    return payload


def write_research_table_metrics_reports(root_path: str | Path, payload: dict[str, Any]) -> dict[str, str]:
    root = Path(root_path)
    metrics_dir = root / "mystic_data" / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    json_path = metrics_dir / "research_table_metrics.json"
    markdown_path = metrics_dir / "research_table_metrics.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    markdown_path.write_text(render_research_table_metrics_markdown(payload), encoding="utf-8")
    return {
        "json": str(json_path),
        "markdown": str(markdown_path),
    }


def render_research_table_metrics_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Research Table Metrics",
        "",
        f"- Generated at: `{payload.get('generated_at', '')}`",
        f"- Sessions: `{len(payload.get('sessions', []))}`",
        f"- Models: `{len(payload.get('models', []))}`",
        f"- Tools: `{len(payload.get('tools', []))}`",
        f"- Warnings: `{len(payload.get('warnings', []))}`",
        "",
        "## Sessions",
        "",
        "| session_id | participants | phases | turns | discoveries | verified | refuted | final_status | decision_source |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for item in payload.get("sessions", []):
        participants = ", ".join(_participant_ids(item.get("participants", [])))
        lines.append(
            "| {session_id} | {participants} | {phases} | {turns} | {discoveries} | {verified} | {refuted} | {final_status} | {decision_source} |".format(
                session_id=item.get("session_id", ""),
                participants=participants or "-",
                phases=item.get("completed_phases_count", 0),
                turns=item.get("turns_count", 0),
                discoveries=item.get("discoveries_count", 0),
                verified=item.get("verified_discoveries_count", 0),
                refuted=item.get("refuted_discoveries_count", 0),
                final_status=item.get("final_status", ""),
                decision_source=item.get("final_decision_source", ""),
            )
        )

    lines.extend(
        [
            "",
            "## Models",
            "",
            "| model_id | provider | sessions | turns | proposed | verified | refuted | auth_required | error | avg_latency_sec | useful_rate | refuted_rate |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for item in payload.get("models", []):
        lines.append(
            "| {model_id} | {provider} | {sessions} | {turns} | {proposed} | {verified} | {refuted} | {auth_required} | {error} | {latency:.3f} | {useful:.3f} | {refuted_rate:.3f} |".format(
                model_id=item.get("model_id", ""),
                provider=item.get("provider", ""),
                sessions=item.get("sessions_count", 0),
                turns=item.get("turns_count", 0),
                proposed=item.get("discoveries_proposed", 0),
                verified=item.get("discoveries_verified", 0),
                refuted=item.get("discoveries_refuted", 0),
                auth_required=item.get("auth_required_count", 0),
                error=item.get("error_count", 0),
                latency=float(item.get("average_latency_sec", 0.0)),
                useful=float(item.get("useful_discovery_rate", 0.0)),
                refuted_rate=float(item.get("refuted_discovery_rate", 0.0)),
            )
        )

    lines.extend(
        [
            "",
            "## Tools",
            "",
            "| tool_name | runs | pass | fail | unknown | override |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for item in payload.get("tools", []):
        lines.append(
            "| {tool_name} | {runs} | {pass_count} | {fail_count} | {unknown_count} | {override_count} |".format(
                tool_name=item.get("tool_name", ""),
                runs=item.get("runs_count", 0),
                pass_count=item.get("pass_count", 0),
                fail_count=item.get("fail_count", 0),
                unknown_count=item.get("unknown_count", 0),
                override_count=item.get("override_count", 0),
            )
        )

    warnings = payload.get("warnings", [])
    if warnings:
        lines.extend(["", "## Warnings", ""])
        for warning in warnings:
            lines.append(f"- {warning}")

    return "\n".join(lines) + "\n"


def collect_research_table_records(root_path: str | Path) -> tuple[list[dict[str, Any]], list[str]]:
    root = Path(root_path)
    warnings: list[str] = []
    merged: dict[str, dict[str, Any]] = {}
    sources = [
        ("research_table_sessions", root / "mystic_data" / "research_table_sessions"),
        ("e2e_research_table", root / "mystic_data" / "e2e" / "research_table"),
        ("cli_smoke", root / "mystic_data" / "e2e" / "cli_smoke"),
    ]
    for source_kind, base_dir in sources:
        if not base_dir.exists():
            continue
        for entry in sorted(path for path in base_dir.iterdir() if path.is_dir()):
            record = _load_record(source_kind=source_kind, entry=entry, warnings=warnings)
            if record is None:
                continue
            session_id = str(record["session_id"])
            existing = merged.get(session_id)
            if existing is None:
                merged[session_id] = record
                continue
            merged[session_id] = _merge_records(existing, record)
    return list(merged.values()), warnings


def _load_record(*, source_kind: str, entry: Path, warnings: list[str]) -> dict[str, Any] | None:
    if source_kind == "research_table_sessions":
        session_dir = entry
        summary_path = None
    else:
        session_dir = entry / "session"
        summary_path = entry / "summary.json"

    session = _load_session_bundle(session_dir, warnings=warnings) if session_dir.exists() else None
    summary = _load_json_file(summary_path, warnings=warnings) if summary_path and summary_path.exists() else None
    if session is None and summary is None:
        warnings.append(f"Skipped {entry}: no readable session or summary payload found.")
        return None

    session_id = ""
    if isinstance(session, dict):
        session_id = str(session.get("session_id", "")).strip()
    if not session_id and isinstance(summary, dict):
        session_id = str(summary.get("session_id", "")).strip()
    if not session_id:
        session_id = entry.name

    return {
        "session_id": session_id,
        "source_kind": source_kind,
        "source_paths": [str(entry)],
        "session": session,
        "summary": summary,
    }


def _load_session_bundle(session_dir: Path, *, warnings: list[str]) -> dict[str, Any] | None:
    session_payload = _load_json_file(session_dir / "session.json", warnings=warnings)
    if not isinstance(session_payload, dict):
        return None
    session_payload = dict(session_payload)
    session_payload["turns"] = _load_optional_collection(session_dir / "turns.json", session_payload.get("turns", []), warnings=warnings)
    session_payload["discoveries"] = _load_optional_collection(
        session_dir / "discoveries.json",
        session_payload.get("discoveries", []),
        warnings=warnings,
    )
    session_payload["verification_requests"] = _load_optional_collection(
        session_dir / "verification_requests.json",
        session_payload.get("verification_requests", []),
        warnings=warnings,
    )
    session_payload["final_synthesis_package"] = _load_optional_collection(
        session_dir / "final_synthesis.json",
        session_payload.get("final_synthesis_package", {}),
        warnings=warnings,
    )
    return session_payload


def _load_json_file(path: Path | None, *, warnings: list[str]) -> Any:
    if path is None or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        warnings.append(f"Skipped malformed JSON at {path}: {exc}")
        return None


def _load_optional_collection(path: Path, default: Any, *, warnings: list[str]) -> Any:
    payload = _load_json_file(path, warnings=warnings)
    return default if payload is None else payload


def _merge_records(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = {
        "session_id": left["session_id"],
        "source_kind": left["source_kind"],
        "source_paths": [*left.get("source_paths", []), *right.get("source_paths", [])],
        "session": left.get("session") or right.get("session"),
        "summary": _richer_summary(left.get("summary"), right.get("summary")),
    }
    if merged["session"] is None:
        merged["session"] = right.get("session")
    return merged


def _richer_summary(left: Any, right: Any) -> Any:
    if not isinstance(left, dict):
        return right
    if not isinstance(right, dict):
        return left
    return right if len(right.keys()) > len(left.keys()) else left


def _session_metric(record: dict[str, Any]) -> dict[str, Any]:
    session = record.get("session") if isinstance(record.get("session"), dict) else {}
    summary = record.get("summary") if isinstance(record.get("summary"), dict) else {}
    turns = session.get("turns", []) if isinstance(session.get("turns", []), list) else []
    discoveries = session.get("discoveries", []) if isinstance(session.get("discoveries", []), list) else []
    verification_requests = (
        session.get("verification_requests", []) if isinstance(session.get("verification_requests", []), list) else []
    )

    participants = _normalize_participants(session=session, summary=summary)
    provider_statuses = _provider_statuses(session=session, summary=summary, participants=participants)
    model_turns = [turn for turn in turns if str(turn.get("speaker_type", "")) == "model"]
    tool_turns = [turn for turn in turns if str(turn.get("speaker_type", "")) == "tool"]
    parseable_turns = sum(1 for turn in model_turns if isinstance(turn.get("discoveries"), list) and turn.get("discoveries"))

    completed_phases = _completed_phases(session=session, summary=summary)
    verified_count = sum(1 for item in discoveries if str(item.get("status", "")).lower() == "verified")
    refuted_count = sum(1 for item in discoveries if str(item.get("status", "")).lower() == "refuted")
    teacher_count = _created_count(summary.get("teacher_labels_created"), tool_turns, "save_turn_as_teacher_label")
    training_count = _created_count(summary.get("training_items_created"), tool_turns, "save_discovery_as_training_item")

    created_at = str(session.get("created_at") or summary.get("created_at") or "")
    if not created_at:
        created_at = datetime.now(UTC).isoformat()

    final_status = str(session.get("final_status") or summary.get("final_status") or "UNKNOWN")
    final_decision_source = str(session.get("final_decision_source") or summary.get("final_decision_source") or "model_outputs")

    return {
        "session_id": str(record.get("session_id", "")),
        "created_at": created_at,
        "participants": participants,
        "provider_statuses": provider_statuses,
        "completed_phases_count": len(completed_phases),
        "turns_count": len(turns),
        "model_turns_count": len(model_turns),
        "tool_turns_count": len(tool_turns),
        "auth_required_turns_count": sum(1 for turn in turns if str(turn.get("status", "")) == "AUTH_REQUIRED"),
        "error_turns_count": sum(1 for turn in turns if str(turn.get("status", "")) == "ERROR"),
        "discoveries_count": len(discoveries),
        "parseable_discovery_rate": _safe_rate(parseable_turns, len(model_turns)),
        "verified_discoveries_count": verified_count,
        "refuted_discoveries_count": refuted_count,
        "verified_discovery_rate": _safe_rate(verified_count, len(discoveries)),
        "refuted_discovery_rate": _safe_rate(refuted_count, len(discoveries)),
        "verification_requests_count": len(verification_requests),
        "final_status": final_status,
        "final_decision_source": final_decision_source,
        "deterministic_override_used": final_decision_source == "deterministic_verifier",
        "accepted_discoveries_count": len(session.get("accepted_discoveries", []) if isinstance(session.get("accepted_discoveries", []), list) else []),
        "rejected_discoveries_count": len(session.get("rejected_discoveries", []) if isinstance(session.get("rejected_discoveries", []), list) else []),
        "teacher_labels_created": teacher_count,
        "training_items_created": training_count,
        "_session": session,
        "_summary": summary,
    }


def _normalize_participants(*, session: dict[str, Any], summary: dict[str, Any]) -> list[dict[str, Any]]:
    provider_statuses = summary.get("provider_auth_statuses")
    selected = summary.get("selected_participants") or summary.get("participants")
    if isinstance(selected, list) and selected:
        values: list[dict[str, Any]] = []
        for item in selected:
            if isinstance(item, dict):
                model_id = str(item.get("model_id", "")).strip()
                if not model_id:
                    continue
                values.append(
                    {
                        "model_id": model_id,
                        "provider": str(item.get("provider", "")),
                        "model_name": str(item.get("model_name", model_id)),
                    }
                )
                continue
            model_id = str(item).strip()
            if not model_id:
                continue
            status = provider_statuses.get(model_id, {}) if isinstance(provider_statuses, dict) else {}
            values.append(
                {
                    "model_id": model_id,
                    "provider": str(status.get("provider", "")),
                    "model_name": str(status.get("model_name", model_id)),
                }
            )
        if values:
            return values

    models = session.get("participant_models")
    if isinstance(models, list) and models:
        values = []
        for item in models:
            if not isinstance(item, dict):
                continue
            model_id = str(item.get("model_id", "")).strip()
            if not model_id:
                continue
            values.append(
                {
                    "model_id": model_id,
                    "provider": str(item.get("provider", "")),
                    "model_name": str(item.get("model_name", model_id)),
                }
            )
        if values:
            return values

    participants = session.get("participants", [])
    if isinstance(participants, list):
        return [{"model_id": str(item), "provider": "", "model_name": str(item)} for item in participants if str(item).strip()]
    return []


def _provider_statuses(*, session: dict[str, Any], summary: dict[str, Any], participants: list[dict[str, Any]]) -> dict[str, Any]:
    provided = summary.get("provider_auth_statuses")
    if isinstance(provided, dict) and provided:
        return {
            str(model_id): {
                "provider": str(payload.get("provider", "")),
                "model_name": str(payload.get("model_name", model_id)),
                "state": str(payload.get("state", "unknown")),
                "message": str(payload.get("message", "")),
                "available": bool(payload.get("available", False)),
                "authenticated": bool(payload.get("authenticated", False)),
            }
            for model_id, payload in provided.items()
            if isinstance(payload, dict)
        }

    turns = session.get("turns", []) if isinstance(session.get("turns", []), list) else []
    by_model = {
        str(item.get("model_id", "")): {
            "provider": str(item.get("provider", "")),
            "model_name": str(item.get("model_name", item.get("model_id", ""))),
            "state": "unknown",
            "message": "",
            "available": False,
            "authenticated": False,
        }
        for item in participants
        if str(item.get("model_id", "")).strip()
    }
    for turn in turns:
        if str(turn.get("speaker_type", "")) != "model":
            continue
        model_id = str(turn.get("speaker_id", "")).strip()
        if not model_id:
            continue
        item = by_model.setdefault(
            model_id,
            {
                "provider": str(turn.get("provider", "")),
                "model_name": str(turn.get("model_name", model_id)),
                "state": "unknown",
                "message": "",
                "available": False,
                "authenticated": False,
            },
        )
        status = str(turn.get("status", ""))
        if status == "AUTH_REQUIRED":
            item.update(
                {
                    "state": "not_authenticated",
                    "message": str(turn.get("content", "")),
                    "available": True,
                    "authenticated": False,
                }
            )
        elif status == "ERROR" and item.get("state") != "not_authenticated":
            item.update(
                {
                    "state": "error",
                    "message": str(turn.get("content", "")),
                    "available": False,
                    "authenticated": False,
                }
            )
        elif item.get("state") == "unknown":
            item.update(
                {
                    "state": "ready",
                    "available": True,
                    "authenticated": True,
                }
            )
    return by_model


def _completed_phases(*, session: dict[str, Any], summary: dict[str, Any]) -> list[str]:
    for key in ("completed_phases", "phases_completed"):
        values = summary.get(key)
        if isinstance(values, list):
            return [str(item) for item in values if str(item)]
    turns = session.get("turns", []) if isinstance(session.get("turns", []), list) else []
    return [phase for phase in PHASE_ORDER if any(str(turn.get("phase", "")) == phase for turn in turns)]


def _created_count(summary_value: Any, tool_turns: list[dict[str, Any]], speaker_id: str) -> int:
    if isinstance(summary_value, list):
        return len(summary_value)
    return sum(1 for turn in tool_turns if str(turn.get("speaker_id", "")) == speaker_id and str(turn.get("status", "")) == "SAVED")


def _safe_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _update_model_metrics(accumulators: dict[str, dict[str, Any]], record: dict[str, Any], session_metric: dict[str, Any]) -> None:
    session = session_metric["_session"]
    participants = session_metric.get("participants", [])
    provider_statuses = session_metric.get("provider_statuses", {})
    turns = session.get("turns", []) if isinstance(session.get("turns", []), list) else []
    discoveries = session.get("discoveries", []) if isinstance(session.get("discoveries", []), list) else []
    turn_by_id = {
        str(turn.get("turn_id", "")): turn
        for turn in turns
        if isinstance(turn, dict) and str(turn.get("turn_id", "")).strip()
    }

    seen_models: set[str] = set()
    for participant in participants:
        model_id = str(participant.get("model_id", "")).strip()
        if not model_id or model_id in seen_models:
            continue
        seen_models.add(model_id)
        item = accumulators.setdefault(
            model_id,
            {
                "model_id": model_id,
                "provider": str(participant.get("provider", "")),
                "model_name": str(participant.get("model_name", model_id)),
                "sessions_count": 0,
                "turns_count": 0,
                "discoveries_proposed": 0,
                "discoveries_verified": 0,
                "discoveries_refuted": 0,
                "auth_required_count": 0,
                "error_count": 0,
                "latency_total_sec": 0.0,
                "latency_count": 0,
            },
        )
        if not item["provider"]:
            status = provider_statuses.get(model_id, {})
            item["provider"] = str(status.get("provider", item["provider"]))
            item["model_name"] = str(status.get("model_name", item["model_name"]))
        item["sessions_count"] += 1

    for turn in turns:
        if str(turn.get("speaker_type", "")) != "model":
            continue
        model_id = str(turn.get("speaker_id", "")).strip()
        if not model_id:
            continue
        item = accumulators.setdefault(
            model_id,
            {
                "model_id": model_id,
                "provider": str(turn.get("provider", "")),
                "model_name": str(turn.get("model_name", model_id)),
                "sessions_count": 0,
                "turns_count": 0,
                "discoveries_proposed": 0,
                "discoveries_verified": 0,
                "discoveries_refuted": 0,
                "auth_required_count": 0,
                "error_count": 0,
                "latency_total_sec": 0.0,
                "latency_count": 0,
            },
        )
        item["turns_count"] += 1
        if str(turn.get("status", "")) == "AUTH_REQUIRED":
            item["auth_required_count"] += 1
        if str(turn.get("status", "")) == "ERROR":
            item["error_count"] += 1
        latency = turn.get("latency_sec")
        try:
            item["latency_total_sec"] += float(latency or 0.0)
            item["latency_count"] += 1
        except (TypeError, ValueError):
            pass

    for discovery in discoveries:
        source_turn = turn_by_id.get(str(discovery.get("source_turn_id", "")))
        if source_turn is None or str(source_turn.get("speaker_type", "")) != "model":
            continue
        model_id = str(source_turn.get("speaker_id", "")).strip()
        if not model_id:
            continue
        item = accumulators.setdefault(
            model_id,
            {
                "model_id": model_id,
                "provider": str(source_turn.get("provider", "")),
                "model_name": str(source_turn.get("model_name", model_id)),
                "sessions_count": 0,
                "turns_count": 0,
                "discoveries_proposed": 0,
                "discoveries_verified": 0,
                "discoveries_refuted": 0,
                "auth_required_count": 0,
                "error_count": 0,
                "latency_total_sec": 0.0,
                "latency_count": 0,
            },
        )
        item["discoveries_proposed"] += 1
        status = str(discovery.get("status", "")).lower()
        if status == "verified":
            item["discoveries_verified"] += 1
        if status == "refuted":
            item["discoveries_refuted"] += 1


def _update_tool_metrics(accumulators: dict[str, dict[str, Any]], record: dict[str, Any], session_metric: dict[str, Any]) -> None:
    session = session_metric["_session"]
    turns = session.get("turns", []) if isinstance(session.get("turns", []), list) else []
    tool_names_seen: set[str] = set()
    for turn in turns:
        if str(turn.get("speaker_type", "")) != "tool":
            continue
        tool_name = str(turn.get("speaker_id", "")).strip() or str(turn.get("model_name", "")).strip()
        if not tool_name:
            continue
        item = accumulators.setdefault(
            tool_name,
            {
                "tool_name": tool_name,
                "runs_count": 0,
                "pass_count": 0,
                "fail_count": 0,
                "unknown_count": 0,
                "override_count": 0,
            },
        )
        item["runs_count"] += 1
        verdict = _tool_outcome(turn)
        item[f"{verdict}_count"] += 1
        tool_names_seen.add(tool_name)

    if session_metric.get("deterministic_override_used"):
        for tool_name in tool_names_seen:
            if tool_name == "mystic_verify_answer":
                accumulators[tool_name]["override_count"] += 1


def _tool_outcome(turn: dict[str, Any]) -> str:
    tool_name = str(turn.get("speaker_id", ""))
    status = str(turn.get("status", ""))
    summary = str(turn.get("summary", "")).upper()
    if tool_name == "mystic_verify_answer" or str(turn.get("role", "")) == "verifier":
        if summary == "VALID":
            return "pass"
        if summary == "INVALID":
            return "fail"
        return "unknown"
    if status in {"SAVED", "PASS", "OK"}:
        return "pass"
    if status in {"FAILED", "ERROR"}:
        return "fail"
    return "unknown"


def _finalize_model_metrics(item: dict[str, Any]) -> dict[str, Any]:
    proposed = int(item.get("discoveries_proposed", 0))
    return {
        "model_id": item["model_id"],
        "provider": item.get("provider", ""),
        "model_name": item.get("model_name", item["model_id"]),
        "sessions_count": int(item.get("sessions_count", 0)),
        "turns_count": int(item.get("turns_count", 0)),
        "discoveries_proposed": proposed,
        "discoveries_verified": int(item.get("discoveries_verified", 0)),
        "discoveries_refuted": int(item.get("discoveries_refuted", 0)),
        "auth_required_count": int(item.get("auth_required_count", 0)),
        "error_count": int(item.get("error_count", 0)),
        "average_latency_sec": _safe_rate(float(item.get("latency_total_sec", 0.0)), int(item.get("latency_count", 0))),
        "useful_discovery_rate": _safe_rate(int(item.get("discoveries_verified", 0)), proposed),
        "refuted_discovery_rate": _safe_rate(int(item.get("discoveries_refuted", 0)), proposed),
    }


def _finalize_tool_metrics(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "tool_name": item["tool_name"],
        "runs_count": int(item.get("runs_count", 0)),
        "pass_count": int(item.get("pass_count", 0)),
        "fail_count": int(item.get("fail_count", 0)),
        "unknown_count": int(item.get("unknown_count", 0)),
        "override_count": int(item.get("override_count", 0)),
    }


def _public_session_metric(item: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in item.items() if not str(key).startswith("_")}


def _participant_ids(participants: list[dict[str, Any]]) -> list[str]:
    return [str(item.get("model_id", "")) for item in participants if str(item.get("model_id", "")).strip()]

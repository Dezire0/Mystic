from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from mystic.lab.session import Claim, Experiment, Failure, LabSession, LabTurn
from mystic.lab.storage import LabStorage
from mystic.raven_training import write_jsonl


FAILURE_VERDICT_MAP = {
    "arithmetic": "INVALID",
    "counterexample": "INVALID",
    "contradiction": "INVALID",
    "invalid_assumption": "INVALID",
    "missing_case": "INVALID",
    "logic_gap": "INVALID",
    "hallucination": "INVALID",
    "unsupported_generalization": "INVALID",
    "insufficient_detail": "NEEDS_MORE_DETAIL",
    "tool_error": "UNCLEAR",
    "runtime_error": "UNCLEAR",
}


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def map_lab_failure_to_raven_verdict(failure_type: str) -> str:
    normalized = str(failure_type or "").strip()
    return FAILURE_VERDICT_MAP.get(normalized, "UNCLEAR")


def build_raven_row_from_lab_failure(
    session: LabSession,
    claim: Claim | None,
    failure: Failure,
    source_turn: LabTurn | None = None,
    experiments: list[Experiment] | None = None,
) -> dict[str, Any]:
    experiments = experiments or []
    claim_text = claim.text if claim else ""
    model_output = source_turn.output if source_turn else ""
    verdict = map_lab_failure_to_raven_verdict(failure.failure_type)
    tool_evidence_parts: list[str] = []
    if claim:
        tool_evidence_parts.extend(item.strip() for item in claim.refuting_evidence if str(item).strip())
    for experiment in experiments:
        if experiment.evidence_summary.strip():
            tool_evidence_parts.append(experiment.evidence_summary.strip())
        if experiment.outputs:
            tool_evidence_parts.append(json.dumps(experiment.outputs, ensure_ascii=True, sort_keys=True))
    tool_evidence = "\n".join(dict.fromkeys(tool_evidence_parts))

    context_lines = [
        f"Domain: {session.domain}",
        f"Goal: {session.goal}",
        f"Mode: {session.mode}",
        f"Phase: {session.current_phase}",
        f"Failure type: {failure.failure_type}",
        f"Lesson: {failure.lesson}",
    ]
    if source_turn is not None:
        context_lines.extend(
            [
                f"Source agent role: {source_turn.agent_role}",
                f"Source provider: {source_turn.provider}",
                f"Source model: {source_turn.model_name}",
            ]
        )
    if claim is not None:
        context_lines.append(f"Claim status at archive time: {claim.status}")

    if verdict == "INVALID":
        recommended_next_action = "Repair the invalid step, bound the search, and rerun deterministic verification."
    elif verdict == "NEEDS_MORE_DETAIL":
        recommended_next_action = "Add the missing proof detail or case split before retrying the claim."
    else:
        recommended_next_action = "Stabilize the failing tool path and rerun the verification with explicit diagnostics."

    critique = failure.lesson.strip() or f"Reject the claim because: {failure.first_fatal_error}"

    return {
        "agent": "raven",
        "input": {
            "problem": session.problem,
            "model_output": model_output,
            "discovery_or_claim": claim_text,
            "tool_evidence": tool_evidence,
            "context": "\n".join(context_lines).strip(),
        },
        "output": {
            "verdict": verdict,
            "first_fatal_error": failure.first_fatal_error,
            "critique": critique,
            "recommended_next_action": recommended_next_action,
        },
        "source": {
            "source_type": "lab_failure",
            "session_id": session.session_id,
            "claim_id": failure.claim_id,
            "failure_id": failure.failure_id,
            "source_turn_id": failure.source_turn_id,
            "turn_id": failure.source_turn_id,
        },
    }


def export_lab_failures_for_raven(
    root_path: str | Path,
    output_path: str | Path,
    *,
    limit: int | None = None,
    include_non_reusable: bool = False,
    allow_empty: bool = False,
) -> dict[str, Any]:
    root = Path(root_path)
    storage = LabStorage(root)
    target_path = Path(output_path)
    summary_path = target_path.parent / f"{target_path.stem}_summary.json"

    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    verdict_distribution: Counter[str] = Counter()
    failure_type_distribution: Counter[str] = Counter()
    sessions_scanned = 0
    failures_scanned = 0
    reusable_failures = 0
    skipped_failures = 0

    for session_id in storage.list_session_ids():
        sessions_scanned += 1
        try:
            bundle = storage.load_bundle(session_id)
        except Exception as exc:
            warnings.append(f"Skipping malformed lab session {session_id}: {exc}")
            continue

        claims_by_id = {claim.claim_id: claim for claim in bundle.claims}
        turns_by_id = {turn.turn_id: turn for turn in bundle.turns}
        experiments_by_claim: dict[str, list[Experiment]] = {}
        for experiment in bundle.experiments:
            experiments_by_claim.setdefault(experiment.claim_id, []).append(experiment)

        for failure in bundle.failures:
            failures_scanned += 1
            if failure.reusable_as_training_data:
                reusable_failures += 1
            elif not include_non_reusable:
                skipped_failures += 1
                continue

            claim = claims_by_id.get(failure.claim_id)
            source_turn = turns_by_id.get(failure.source_turn_id)
            related_experiments = experiments_by_claim.get(failure.claim_id, [])
            row = build_raven_row_from_lab_failure(
                bundle.session,
                claim,
                failure,
                source_turn=source_turn,
                experiments=related_experiments,
            )
            rows.append(row)
            verdict_distribution[str(row["output"]["verdict"]).strip()] += 1
            failure_type_distribution[str(failure.failure_type).strip()] += 1
            if limit and len(rows) >= limit:
                break
        if limit and len(rows) >= limit:
            break

    if not rows and not allow_empty:
        raise ValueError("No reusable lab failures were found. Use --allow-empty to write an empty dataset.")

    write_jsonl(target_path, rows)
    summary = {
        "target": "raven",
        "output_path": str(target_path),
        "rows_written": len(rows),
        "sessions_scanned": sessions_scanned,
        "failures_scanned": failures_scanned,
        "reusable_failures": reusable_failures,
        "skipped_failures": skipped_failures,
        "verdict_distribution": dict(sorted(verdict_distribution.items())),
        "failure_type_distribution": dict(sorted(failure_type_distribution.items())),
        "warnings": warnings,
        "created_at": now_iso(),
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return summary

"""Comparison helpers for base Raven vs adapter Raven."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
import uuid


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def critique_quality_score(critique: dict[str, Any], target_verdict: str | None = None) -> float:
    score = 0.0
    if critique.get("parse_error") is None:
        score += 1.0
    verdict = str(critique.get("verdict", "")).strip().upper()
    if target_verdict and verdict == target_verdict.strip().upper():
        score += 2.0
    if verdict != "VALID" and str(critique.get("first_fatal_error", "")).strip():
        score += 1.0
    score += min(len(critique.get("missing_assumptions", [])), 4) * 0.1
    return score


def build_comparison_record(
    *,
    sample_id: str,
    source: str,
    problem: str,
    proof_text: str,
    target_verdict: str | None,
    base_critique: dict[str, Any],
    adapter_critique: dict[str, Any],
    base_latency: float,
    adapter_latency: float,
    base_model: str,
    adapter_path: str,
    run_id: str | None = None,
) -> dict[str, Any]:
    base_score = critique_quality_score(base_critique, target_verdict)
    adapter_score = critique_quality_score(adapter_critique, target_verdict)
    adapter_better_or_equal = adapter_score >= base_score
    if adapter_score > base_score:
        improvement_reason = "adapter score is higher"
    elif adapter_score == base_score:
        improvement_reason = "adapter score is equal"
    else:
        improvement_reason = "adapter score is lower"

    return {
        "event_id": str(uuid.uuid4()),
        "timestamp": now_iso(),
        "run_id": run_id,
        "source": source,
        "sample_id": sample_id,
        "problem": problem,
        "proof_text": proof_text,
        "target_verdict": target_verdict,
        "base_model": base_model,
        "adapter_path": adapter_path,
        "base": {
            "verdict": base_critique.get("verdict"),
            "parse_error": base_critique.get("parse_error"),
            "first_fatal_error": base_critique.get("first_fatal_error", ""),
            "missing_assumptions_count": len(base_critique.get("missing_assumptions", [])),
            "latency_seconds": base_latency,
            "score": base_score,
        },
        "adapter": {
            "verdict": adapter_critique.get("verdict"),
            "parse_error": adapter_critique.get("parse_error"),
            "first_fatal_error": adapter_critique.get("first_fatal_error", ""),
            "missing_assumptions_count": len(adapter_critique.get("missing_assumptions", [])),
            "latency_seconds": adapter_latency,
            "score": adapter_score,
        },
        "adapter_better_or_equal": adapter_better_or_equal,
        "improvement_reason": improvement_reason,
    }


def summarize_comparison_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def _metrics(prefix: str) -> dict[str, Any]:
        total = len(rows)
        if total == 0:
            return {
                "valid_json_rate": 0.0,
                "verdict_match_rate": 0.0,
                "first_fatal_error_nonempty_rate": 0.0,
                "missing_assumptions_count_average": 0.0,
                "invalid_output_count": 0,
                "average_latency": 0.0,
            }
        valid_json = 0
        verdict_matches = 0
        fatal_nonempty = 0
        missing_count_total = 0
        invalid_outputs = 0
        latency_total = 0.0
        for row in rows:
            payload = row[prefix]
            parse_error = payload.get("parse_error")
            if parse_error is None:
                valid_json += 1
            else:
                invalid_outputs += 1
            target = str(row.get("target_verdict") or "").strip().upper()
            verdict = str(payload.get("verdict") or "").strip().upper()
            if target and verdict == target:
                verdict_matches += 1
            if str(payload.get("first_fatal_error", "")).strip():
                fatal_nonempty += 1
            missing_count_total += int(payload.get("missing_assumptions_count", 0))
            latency_total += float(payload.get("latency_seconds", 0.0))
        return {
            "valid_json_rate": valid_json / total,
            "verdict_match_rate": verdict_matches / total,
            "first_fatal_error_nonempty_rate": fatal_nonempty / total,
            "missing_assumptions_count_average": missing_count_total / total,
            "invalid_output_count": invalid_outputs,
            "average_latency": latency_total / total,
        }

    adapter_better_or_equal_count = sum(1 for row in rows if row.get("adapter_better_or_equal"))
    return {
        "total": len(rows),
        "base": _metrics("base"),
        "adapter": _metrics("adapter"),
        "adapter_better_or_equal_rate": (adapter_better_or_equal_count / len(rows)) if rows else 0.0,
    }


def should_promote_adapter(summary: dict[str, Any]) -> tuple[bool, str]:
    adapter = summary.get("adapter", {})
    base = summary.get("base", {})
    checks = [
        float(adapter.get("valid_json_rate", 0.0)) >= float(base.get("valid_json_rate", 0.0)),
        float(adapter.get("verdict_match_rate", 0.0)) >= float(base.get("verdict_match_rate", 0.0)),
        float(adapter.get("first_fatal_error_nonempty_rate", 0.0)) >= float(base.get("first_fatal_error_nonempty_rate", 0.0)),
        int(adapter.get("invalid_output_count", 0)) <= int(base.get("invalid_output_count", 0)),
    ]
    if all(checks):
        return True, "adapter is better or equal on selected promotion metrics"
    return False, "adapter is worse on at least one selected promotion metric"

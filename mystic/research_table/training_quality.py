from __future__ import annotations

from collections import Counter
import hashlib
import json
from typing import Any


DEFAULT_MIN_INVALID_ROWS = 5
DEFAULT_MIN_FATAL_ERROR_COVERAGE = 0.95
DEFAULT_MIN_TOOL_EVIDENCE_COVERAGE = 0.90
DEFAULT_MAX_DUPLICATE_RATE = 0.20


def _research_payload(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata", {})
    if not isinstance(metadata, dict):
        return {}
    payload = metadata.get("research_table", {})
    return payload if isinstance(payload, dict) else {}


def _assistant_payload(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("assistant_output", "")
    if isinstance(raw, dict):
        return raw
    try:
        payload = json.loads(str(raw or ""))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def raven_training_row_fingerprint(row: dict[str, Any]) -> str:
    metadata = row.get("metadata", {})
    weight_index = metadata.get("adversarial_weight_index") if isinstance(metadata, dict) else None
    payload = {
        "problem": row.get("problem", ""),
        "proof_attempt": row.get("proof_attempt", ""),
        "target_verdict": row.get("target_verdict", ""),
        "assistant_output": row.get("assistant_output", ""),
        "adversarial_weight_index": weight_index,
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _coverage(covered: int, total: int) -> dict[str, Any]:
    return {
        "covered": covered,
        "total": total,
        "rate": 1.0 if total == 0 else covered / total,
    }


def evaluate_raven_training_quality(
    rows: list[dict[str, Any]],
    *,
    min_invalid_rows: int = DEFAULT_MIN_INVALID_ROWS,
    min_fatal_error_coverage: float = DEFAULT_MIN_FATAL_ERROR_COVERAGE,
    min_tool_evidence_coverage: float = DEFAULT_MIN_TOOL_EVIDENCE_COVERAGE,
    max_duplicate_rate: float = DEFAULT_MAX_DUPLICATE_RATE,
    duplicate_rows_removed: int = 0,
    train_rows_count: int | None = None,
    eval_rows_count: int | None = None,
    enforce_min_invalid: bool = False,
    allow_low_invalid: bool = False,
) -> dict[str, Any]:
    verdicts: Counter[str] = Counter()
    invalid_with_fatal = 0
    verifier_rows = 0
    verifier_with_evidence = 0
    fingerprints: Counter[str] = Counter()

    for row in rows:
        verdict = str(row.get("target_verdict", "") or "").strip().upper()
        verdicts[verdict] += 1
        research = _research_payload(row)
        assistant = _assistant_payload(row)
        first_fatal_error = str(
            research.get("first_fatal_error", assistant.get("first_fatal_error", "")) or ""
        ).strip()
        verifier_derived = bool(
            research.get("verifier_derived")
            or (isinstance(row.get("metadata"), dict) and row["metadata"].get("verifier_derived"))
        )
        tool_evidence = str(research.get("tool_evidence", "") or "").strip()
        if verdict == "INVALID" and first_fatal_error:
            invalid_with_fatal += 1
        if verifier_derived:
            verifier_rows += 1
            if tool_evidence:
                verifier_with_evidence += 1
        fingerprints[raven_training_row_fingerprint(row)] += 1

    computed_duplicates = sum(count - 1 for count in fingerprints.values() if count > 1)
    duplicate_rate = computed_duplicates / len(rows) if rows else 0.0
    rows_before_dedup = len(rows) + int(duplicate_rows_removed)
    source_duplicate_rate = int(duplicate_rows_removed) / rows_before_dedup if rows_before_dedup else 0.0
    invalid_count = int(verdicts.get("INVALID", 0))
    fatal_coverage = _coverage(invalid_with_fatal, invalid_count)
    tool_coverage = _coverage(verifier_with_evidence, verifier_rows)

    warnings: list[str] = []
    errors: list[str] = []
    if not rows:
        errors.append("Prepared Raven dataset has no rows.")
    if rows and min_invalid_rows > 0 and invalid_count < min_invalid_rows:
        message = f"Too few INVALID rows for conservative Raven training: {invalid_count} < {min_invalid_rows}."
        if enforce_min_invalid and not allow_low_invalid:
            errors.append(message)
        else:
            warnings.append(message)
    if fatal_coverage["rate"] < min_fatal_error_coverage:
        warnings.append(
            "INVALID first_fatal_error coverage is below the recommended threshold: "
            f"{fatal_coverage['rate']:.3f} < {min_fatal_error_coverage:.3f}."
        )
    if tool_coverage["rate"] < min_tool_evidence_coverage:
        warnings.append(
            "Verifier-derived tool_evidence coverage is below the recommended threshold: "
            f"{tool_coverage['rate']:.3f} < {min_tool_evidence_coverage:.3f}."
        )
    if duplicate_rate > max_duplicate_rate:
        warnings.append(
            f"Duplicate row rate is high: {duplicate_rate:.3f} > {max_duplicate_rate:.3f}."
        )
    if source_duplicate_rate > max_duplicate_rate:
        warnings.append(
            "Too many duplicate source rows were removed before training: "
            f"{source_duplicate_rate:.3f} > {max_duplicate_rate:.3f}."
        )
    if train_rows_count is not None and train_rows_count <= 0:
        errors.append("Raven train split is empty.")
    if eval_rows_count is not None and eval_rows_count <= 0:
        errors.append("Raven eval split is empty.")

    stats = {
        "rows_written": len(rows),
        "verdict_distribution": dict(sorted((key, value) for key, value in verdicts.items() if key)),
        "invalid_rows_count": invalid_count,
        "needs_more_detail_rows_count": int(verdicts.get("NEEDS_MORE_DETAIL", 0)),
        "valid_rows_count": int(verdicts.get("VALID", 0)),
        "invalid_row_ratio": invalid_count / len(rows) if rows else 0.0,
        "first_fatal_error_coverage": fatal_coverage,
        "tool_evidence_coverage": tool_coverage,
        "duplicate_rows_count": computed_duplicates,
        "duplicate_rows_removed": int(duplicate_rows_removed),
        "duplicate_rate": duplicate_rate,
        "source_duplicate_rate": source_duplicate_rate,
        "train_rows_count": train_rows_count,
        "eval_rows_count": eval_rows_count,
    }
    return {
        "passed": not errors,
        "warnings": warnings,
        "errors": errors,
        "stats": stats,
    }

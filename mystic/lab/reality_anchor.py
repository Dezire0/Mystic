from __future__ import annotations


def normalize_claim_status(
    *,
    model_generated: bool = False,
    verifier_verdict: str | None = None,
    method: str | None = None,
    referee_fatal_error: bool = False,
    simulation_supported: bool = False,
    incomplete_proof: bool = False,
    contradiction_detected: bool = False,
) -> str:
    verdict = (verifier_verdict or "").upper()
    execution_method = (method or "").lower()

    if contradiction_detected:
        return "REFUTED" if verdict == "INVALID" else "UNKNOWN"
    if referee_fatal_error:
        return "FAILED"
    if verdict == "INVALID":
        return "REFUTED"
    if incomplete_proof:
        return "NEEDS_MORE_DETAIL"
    if verdict == "VALID":
        if execution_method in {"symbolic", "manual_review"}:
            return "PROVED"
        return "TESTED"
    if simulation_supported:
        return "TESTED"
    if model_generated:
        return "HEURISTIC"
    return "UNKNOWN"


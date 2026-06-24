"""Typed structures for the Mystic JSONL research loop."""

from __future__ import annotations

from typing import Any, Literal, TypedDict


Verdict = Literal["VALID", "INVALID", "GAP", "NEEDS_MORE_DETAIL"]


class ProblemItem(TypedDict, total=False):
    sample_id: str
    source_dataset: str
    downloaded_at: str
    problem: str
    reference_solution: str
    raw: dict[str, Any]


class ProofAttempt(TypedDict, total=False):
    proof_id: str
    sample_id: str
    run_id: str
    backend: str
    model: str
    prompt: str
    proof_text: str
    raw_output: str
    generated_at: str
    error: str | None


class RavenCritique(TypedDict, total=False):
    critique_id: str
    sample_id: str
    run_id: str
    backend: str
    model: str
    verdict: Verdict
    first_fatal_error: str
    missing_assumptions: list[str]
    invalid_steps: list[str]
    valid_steps: list[str]
    repair_possible: bool
    confidence: float
    final_status: str
    raw_output: str
    parse_error: str | None
    parsed_at: str


class LoopResult(TypedDict, total=False):
    result_id: str
    sample_id: str
    run_id: str
    timestamp: str
    backend: str
    generator_model: str
    raven_model: str
    problem: str
    reference_solution: str
    proof_attempt: ProofAttempt
    raven_critique: RavenCritique
    verdict: Verdict
    final_status: str


class RunLogEvent(TypedDict, total=False):
    event_id: str
    id: str
    timestamp: str
    run_id: str
    backend: str
    generator_model: str
    raven_model: str
    status: str
    error: str | None

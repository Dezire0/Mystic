"""Deterministic, decision-auditable ALETHEIA specialist eligibility gate.

This module deliberately separates evidence eligibility from routing selection.
It registers no production backend and does not alter WORLD, HERMES, or OIKOS.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Callable, Mapping


class CandidateStatus(StrEnum):
    DISCOVERED = "DISCOVERED"
    BENCHMARKING = "BENCHMARKING"
    EXPERIMENTAL = "EXPERIMENTAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DEPRECATED = "DEPRECATED"


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    candidate_id: str
    benchmark_id: str
    benchmark_version: str
    quality_metrics: Mapping[str, float]
    latency_ms: float | None
    peak_vram_mb: int | None
    execution_succeeded: bool
    reliability: float | None
    resource_cost: Mapping[str, Any]
    hardware_backend: str
    model_revision: str
    timestamp: str
    raw_evidence_ref: str
    suite_completed: bool = True
    reproducible: bool = True
    environment_acceptance_passed: bool = False


@dataclass(frozen=True, slots=True)
class ApprovalRecord:
    decision: str
    candidate_id: str
    reasons: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    policy_version: str
    evaluated_at: str


@dataclass(frozen=True, slots=True)
class BenchmarkCandidate:
    candidate_id: str
    capability: str
    identity: str
    version: str
    model_revision: str
    execution_backend: str
    supported_modalities: tuple[str, ...]
    status: CandidateStatus
    benchmark_evidence_refs: tuple[str, ...]
    approval_record: ApprovalRecord | None
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class CapabilityPolicy:
    required_benchmark_ids: tuple[str, ...]
    minimum_quality: Mapping[str, float]
    minimum_reliability: float
    require_environment_acceptance: bool = True


@dataclass(frozen=True, slots=True)
class ApprovalPolicy:
    version: str
    capabilities: Mapping[str, CapabilityPolicy]


class SpecialistApprovalGate:
    """Applies versioned, capability-specific rules without ranking candidates."""

    def __init__(self, policy: ApprovalPolicy, now: Callable[[], datetime] | None = None) -> None:
        self.policy = policy
        self._now = now or (lambda: datetime.now(UTC))

    def evaluate(self, candidate: BenchmarkCandidate, results: tuple[BenchmarkResult, ...]) -> ApprovalRecord:
        reasons: list[str] = []
        policy = self.policy.capabilities.get(candidate.capability)
        relevant = tuple(result for result in results if result.candidate_id == candidate.candidate_id)
        if policy is None:
            reasons.append("UNSUPPORTED_CAPABILITY")
        else:
            found = {result.benchmark_id for result in relevant}
            for benchmark_id in policy.required_benchmark_ids:
                if benchmark_id not in found:
                    reasons.append(f"MISSING_BENCHMARK:{benchmark_id}")
            for result in relevant:
                if result.model_revision != candidate.model_revision:
                    reasons.append(f"STALE_MODEL_REVISION:{result.benchmark_id}")
                if not result.suite_completed:
                    reasons.append(f"INCOMPLETE_SUITE:{result.benchmark_id}")
                if not result.reproducible or not result.benchmark_version or not result.raw_evidence_ref:
                    reasons.append(f"NONREPRODUCIBLE_EVIDENCE:{result.benchmark_id}")
                if not result.execution_succeeded:
                    reasons.append(f"EXECUTION_FAILED:{result.benchmark_id}")
                if result.reliability is None or result.reliability < policy.minimum_reliability:
                    reasons.append(f"RELIABILITY_BELOW_THRESHOLD:{result.benchmark_id}")
                if policy.require_environment_acceptance and not result.environment_acceptance_passed:
                    reasons.append(f"ENVIRONMENT_ACCEPTANCE_FAILED:{result.benchmark_id}")
                for metric, threshold in policy.minimum_quality.items():
                    value = result.quality_metrics.get(metric)
                    if value is None or value < threshold:
                        reasons.append(f"QUALITY_BELOW_THRESHOLD:{metric}:{result.benchmark_id}")
        evidence = tuple(sorted({reference for result in relevant for reference in (result.raw_evidence_ref,)} | set(candidate.benchmark_evidence_refs)))
        return ApprovalRecord(
            decision="APPROVED" if not reasons else "REJECTED",
            candidate_id=candidate.candidate_id,
            reasons=tuple(sorted(set(reasons))),
            evidence_refs=evidence,
            policy_version=self.policy.version,
            evaluated_at=self._now().isoformat(),
        )


class BenchmarkCandidateRegistry:
    """In-memory versioned registry; persistence remains an explicit later decision."""

    def __init__(self, candidates: tuple[BenchmarkCandidate, ...] = ()) -> None:
        self._candidates = {candidate.candidate_id: candidate for candidate in candidates}
        if len(self._candidates) != len(candidates):
            raise ValueError("candidate identifiers must be unique")

    def candidates(self, capability: str | None = None) -> tuple[BenchmarkCandidate, ...]:
        values = self._candidates.values()
        return tuple(sorted((item for item in values if capability is None or item.capability == capability), key=lambda item: item.candidate_id))

    def register(self, candidate: BenchmarkCandidate) -> BenchmarkCandidate:
        """Add or update candidate metadata, invalidating approval on a revision change."""
        existing = self._candidates.get(candidate.candidate_id)
        if existing and (existing.version, existing.model_revision) != (candidate.version, candidate.model_revision):
            candidate = replace(candidate, status=CandidateStatus.EXPERIMENTAL, approval_record=None)
        self._candidates[candidate.candidate_id] = candidate
        return candidate

    def apply(self, record: ApprovalRecord) -> BenchmarkCandidate:
        candidate = self._candidates[record.candidate_id]
        if record.decision == "APPROVED":
            status = CandidateStatus.APPROVED
        elif any(reason.startswith(("QUALITY_", "RELIABILITY_", "EXECUTION_", "STALE_", "ENVIRONMENT_")) for reason in record.reasons):
            status = CandidateStatus.REJECTED
        else:
            # Incomplete or not-yet-reproducible evidence remains eligible for future benchmarking.
            status = CandidateStatus.EXPERIMENTAL
        updated = replace(candidate, status=status, approval_record=record, updated_at=record.evaluated_at)
        self._candidates[candidate.candidate_id] = updated
        return updated


@dataclass(frozen=True, slots=True)
class ScientificTask:
    task_id: str
    capability: str


@dataclass(frozen=True, slots=True)
class RouteDecisionReceipt:
    task_id: str
    capability: str
    eligible_candidate_ids: tuple[str, ...]
    ineligible_candidates: Mapping[str, tuple[str, ...]]
    selected_candidate_id: str | None
    selection_reason: str
    benchmark_evidence_refs: tuple[str, ...]
    provider_backend: str | None
    timestamp: str


class ApprovedSpecialistRouter:
    """Selects deterministically from approved candidates only; it never approves."""

    def __init__(self, registry: BenchmarkCandidateRegistry, now: Callable[[], datetime] | None = None) -> None:
        self.registry = registry
        self._now = now or (lambda: datetime.now(UTC))

    def route(self, task: ScientificTask) -> RouteDecisionReceipt:
        candidates = self.registry.candidates(task.capability)
        eligible = tuple(candidate for candidate in candidates if candidate.status is CandidateStatus.APPROVED)
        ineligible = {
            candidate.candidate_id: candidate.approval_record.reasons if candidate.approval_record else (f"STATUS:{candidate.status}",)
            for candidate in candidates if candidate.status is not CandidateStatus.APPROVED
        }
        if not eligible:
            return RouteDecisionReceipt(task.task_id, task.capability, (), ineligible, None, "NO_APPROVED_CANDIDATE", (), None, self._now().isoformat())
        selected = eligible[0]
        return RouteDecisionReceipt(
            task.task_id, task.capability, tuple(item.candidate_id for item in eligible), ineligible,
            selected.candidate_id, "LEXICOGRAPHIC_CANDIDATE_ID_AMONG_APPROVED", selected.approval_record.evidence_refs if selected.approval_record else (),
            selected.execution_backend, self._now().isoformat(),
        )


class SpecialistRouter:
    """Coordinates explicit approval evaluation and approved-only route selection.

    Calling :meth:`evaluate_candidate` is an intentional operator/workflow action;
    :meth:`route` never promotes a record as a side effect.
    """

    def __init__(self, approval_gate: SpecialistApprovalGate, registry: BenchmarkCandidateRegistry, now: Callable[[], datetime] | None = None) -> None:
        self.approval_gate = approval_gate
        self.registry = registry
        self._approved_router = ApprovedSpecialistRouter(registry, now)

    def evaluate_candidate(self, candidate: BenchmarkCandidate, results: tuple[BenchmarkResult, ...]) -> BenchmarkCandidate:
        return self.registry.apply(self.approval_gate.evaluate(candidate, results))

    def route(self, task: ScientificTask) -> RouteDecisionReceipt:
        return self._approved_router.route(task)


def verified_nvidia_candidates() -> tuple[BenchmarkCandidate, ...]:
    """Seed only observed, small/toy evidence as EXPERIMENTAL—not route activation."""
    created = "2026-08-25T00:00:00+00:00"
    dispatcher_ref = "docs/alethia_lightning_specialist_dispatcher_v0.md#final-real-acceptance"
    rows = (
        ("nvidia-nemotron-text-embed-1b-v2", "scientific.text_retrieval", "nvidia/llama-nemotron-embed-1b-v2", ("text",), "2048d; synthetic-1000-doc 354 docs/sec; toy Top-1 5/5 Recall@3 5/5"),
        ("nvidia-nemotron-vl-embed-1b-v2", "scientific.visual_retrieval", "nvidia/llama-nemotron-embed-vl-1b-v2", ("text", "image"), "text-to-image retrieval succeeded on T4"),
        ("nvidia-nemotron-vl-rerank-vl-1b-v2", "scientific.multimodal_reranking", "nvidia/llama-nemotron-rerank-vl-1b-v2", ("text", "image"), "native Transformers adapter; gravitational-lensing result ranked first on T4"),
    )
    return tuple(BenchmarkCandidate(candidate_id, capability, identity, "v2", "v2", "lightning_nvidia_retrieval_stack", modalities, CandidateStatus.EXPERIMENTAL, (detail, dispatcher_ref), None, created, created) for candidate_id, capability, identity, modalities, detail in rows)

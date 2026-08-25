from dataclasses import replace
from datetime import UTC, datetime

from mystic.alethia_approval import (
    ApprovalPolicy, ApprovedSpecialistRouter, BenchmarkCandidate, BenchmarkCandidateRegistry,
    BenchmarkResult, CandidateStatus, CapabilityPolicy, ScientificTask, SpecialistApprovalGate,
    SpecialistRouter, verified_nvidia_candidates,
)


NOW = lambda: datetime(2026, 8, 25, tzinfo=UTC)
POLICY = ApprovalPolicy("approval-v0", {"scientific.text_retrieval": CapabilityPolicy(("suite",), {"top_1": 0.8}, 0.95)})


def candidate(candidate_id: str = "candidate-a", revision: str = "r1", status: CandidateStatus = CandidateStatus.EXPERIMENTAL) -> BenchmarkCandidate:
    return BenchmarkCandidate(candidate_id, "scientific.text_retrieval", "local/model", "v1", revision, "local", ("text",), status, (), None, "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00")


def result(candidate_id: str = "candidate-a", revision: str = "r1", **changes: object) -> BenchmarkResult:
    values = dict(candidate_id=candidate_id, benchmark_id="suite", benchmark_version="v1", quality_metrics={"top_1": 0.9}, latency_ms=10.0, peak_vram_mb=None, execution_succeeded=True, reliability=0.99, resource_cost={"cost": "unknown"}, hardware_backend="local", model_revision=revision, timestamp="2026-01-01T00:00:00+00:00", raw_evidence_ref="fixtures/suite-v1.json", environment_acceptance_passed=True)
    values.update(changes)
    return BenchmarkResult(**values)


def approve(registry: BenchmarkCandidateRegistry, item: BenchmarkCandidate, *results: BenchmarkResult) -> BenchmarkCandidate:
    return registry.apply(SpecialistApprovalGate(POLICY, NOW).evaluate(item, tuple(results)))


def test_unapproved_and_experimental_candidates_cannot_route_or_promote_silently() -> None:
    registry = BenchmarkCandidateRegistry((candidate(),))
    receipt = ApprovedSpecialistRouter(registry, NOW).route(ScientificTask("task", "scientific.text_retrieval"))
    assert receipt.selected_candidate_id is None and receipt.selection_reason == "NO_APPROVED_CANDIDATE"
    incomplete = approve(registry, candidate())
    assert incomplete.status is CandidateStatus.EXPERIMENTAL
    updated = approve(registry, incomplete, result())
    assert updated.status is CandidateStatus.APPROVED


def test_threshold_failure_missing_evidence_and_stale_revision_are_machine_readable() -> None:
    gate = SpecialistApprovalGate(POLICY, NOW)
    low = gate.evaluate(candidate(), (result(quality_metrics={"top_1": 0.2}),))
    missing = gate.evaluate(candidate(), ())
    stale = gate.evaluate(candidate(revision="r2"), (result(revision="r1"),))
    assert "QUALITY_BELOW_THRESHOLD:top_1:suite" in low.reasons
    assert "MISSING_BENCHMARK:suite" in missing.reasons
    assert "STALE_MODEL_REVISION:suite" in stale.reasons


def test_revision_change_invalidates_an_existing_approval_before_routing() -> None:
    registry = BenchmarkCandidateRegistry((candidate(),))
    approved = approve(registry, candidate(), result())
    changed = registry.register(replace(approved, model_revision="r2", updated_at="2026-08-25T00:00:00+00:00"))
    assert changed.status is CandidateStatus.EXPERIMENTAL
    assert changed.approval_record is None
    assert ApprovedSpecialistRouter(registry, NOW).route(ScientificTask("task", "scientific.text_retrieval")).selected_candidate_id is None


def test_approval_and_routing_are_deterministic_with_multiple_approved_candidates() -> None:
    items = (candidate("candidate-b"), candidate("candidate-a"))
    registry = BenchmarkCandidateRegistry(items)
    for item in items:
        approve(registry, item, result(item.candidate_id))
    receipt = ApprovedSpecialistRouter(registry, NOW).route(ScientificTask("task-1", "scientific.text_retrieval"))
    assert receipt.eligible_candidate_ids == ("candidate-a", "candidate-b")
    assert receipt.selected_candidate_id == "candidate-a"
    assert receipt.selection_reason == "LEXICOGRAPHIC_CANDIDATE_ID_AMONG_APPROVED"
    assert receipt.benchmark_evidence_refs == ("fixtures/suite-v1.json",)


def test_specialist_router_never_promotes_during_route_but_can_apply_explicit_evaluation() -> None:
    item = candidate()
    registry = BenchmarkCandidateRegistry((item,))
    router = SpecialistRouter(SpecialistApprovalGate(POLICY, NOW), registry, NOW)
    assert router.route(ScientificTask("task", item.capability)).selected_candidate_id is None
    assert router.evaluate_candidate(item, (result(),)).status is CandidateStatus.APPROVED
    assert router.route(ScientificTask("task", item.capability)).selected_candidate_id == item.candidate_id


def test_route_receipt_records_ineligible_candidates_and_no_eligible_case() -> None:
    registry = BenchmarkCandidateRegistry((candidate("approved"), candidate("rejected")))
    approve(registry, candidate("approved"), result("approved"))
    registry.apply(SpecialistApprovalGate(POLICY, NOW).evaluate(candidate("rejected"), ()))
    receipt = ApprovedSpecialistRouter(registry, NOW).route(ScientificTask("task-2", "scientific.text_retrieval"))
    assert receipt.selected_candidate_id == "approved"
    assert receipt.ineligible_candidates["rejected"] == ("MISSING_BENCHMARK:suite",)


def test_seeded_nvidia_evidence_is_honestly_experimental_and_not_routable() -> None:
    candidates = verified_nvidia_candidates()
    assert {item.capability for item in candidates} == {"scientific.text_retrieval", "scientific.visual_retrieval", "scientific.multimodal_reranking"}
    assert all(item.status is CandidateStatus.EXPERIMENTAL for item in candidates)
    assert all("toy" in " ".join(item.benchmark_evidence_refs).lower() or item.capability != "scientific.text_retrieval" for item in candidates)

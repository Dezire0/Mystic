from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

import pytest

from mystic.alethia_approval import (
    ApprovalPolicy, CandidateStatus, CapabilityPolicy, SpecialistApprovalGate,
    verified_nvidia_candidates,
)
from mystic.alethia_scientific_suite import (
    BenchmarkObservation, BenchmarkRun, CaseRunResult, FrozenBenchmarkError,
    FrozenScientificBenchmarkSuite, build_approval_review,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "benchmarks/alethia/approval-v0/fixtures.json"
NOW = lambda: datetime(2026, 8, 25, tzinfo=UTC)


def suite() -> FrozenScientificBenchmarkSuite:
    return FrozenScientificBenchmarkSuite.load(str(FIXTURE))


def perfect_runner(_spec, case, run_number):
    return BenchmarkObservation(tuple(case["relevant_ids"]), 500.0 if run_number == 1 else 0.0, 10.0 + run_number, 1024, f"raw://run-{run_number}/{case['case_id']}")


def test_frozen_benchmark_versions_and_hashes_cover_all_capabilities() -> None:
    frozen = suite()
    specs = [frozen.spec(item["benchmark_id"], model_revision="v2") for item in frozen.manifest["suites"]]
    assert {spec.capability for spec in specs} == {
        "scientific.text_retrieval", "scientific.visual_retrieval", "scientific.multimodal_reranking",
    }
    assert all(spec.dataset_sha256 == item["dataset_sha256"] for spec, item in zip(specs, frozen.manifest["suites"], strict=True))
    rerank = frozen.evaluation_cases("alethia-scientific-multimodal-reranking")
    assert {case["candidate_set_mode"] for case in rerank} == {"text_only", "image_containing", "mixed_multimodal"}


def test_dataset_hash_mismatch_is_rejected() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["suites"][0]["dataset"]["frozen_evaluation"][0]["query"] = "altered question"
    with pytest.raises(FrozenBenchmarkError, match="hash mismatch"):
        FrozenScientificBenchmarkSuite(payload).spec("alethia-scientific-text-retrieval", model_revision="v2")


def test_controlled_figure_assets_are_hash_validated() -> None:
    frozen = suite()
    frozen.manifest["suites"][1]["dataset"]["asset_sha256s"]["physics.png"] = "not-the-real-hash"
    with pytest.raises(FrozenBenchmarkError, match="asset hash mismatch"):
        frozen._validate_asset_hashes(frozen.manifest["suites"][1]["dataset"])


def test_repeated_runs_aggregate_deterministically_and_separate_cold_warm_timing() -> None:
    frozen = suite()
    spec = frozen.spec("alethia-scientific-text-retrieval", model_revision="v2", software_versions={"transformers": "test"})
    evidence = frozen.run(candidate_id="nvidia-nemotron-text-embed-1b-v2", spec=spec, runner=perfect_runner, raw_result_artifact_ref="artifacts/text.json", now=NOW)
    assert len(evidence.runs) == 3
    assert evidence.aggregate_metrics["top_1"] == 1.0
    assert evidence.aggregate_metrics["cold_load_ms_mean"] == 500.0 / 3
    assert evidence.aggregate_metrics["warm_inference_ms_mean"] == 12.0
    assert evidence.aggregate_metrics["warm_inference_ms_variance"] > 0
    assert evidence.aggregate_metrics["correct_item_rank_mean"] == 1.0
    assert evidence.reproducible and evidence.suite_completed and evidence.reliability == 1.0
    assert evidence.to_approval_result(environment_acceptance_passed=True).benchmark_id == spec.benchmark_id


def test_failed_runs_are_preserved_and_incomplete_suite_cannot_pass() -> None:
    frozen = suite()
    spec = frozen.spec("alethia-scientific-visual-retrieval", model_revision="v2")

    def failing_runner(_spec, case, _run):
        if case["case_id"] == "visual-biology":
            raise RuntimeError("controlled runner failure")
        return perfect_runner(_spec, case, 1)

    evidence = frozen.run(candidate_id="nvidia-nemotron-vl-embed-1b-v2", spec=spec, runner=failing_runner, raw_result_artifact_ref="artifacts/visual.json", now=NOW)
    assert evidence.reliability < 1.0
    assert any(case.error == "RuntimeError: controlled runner failure" for run in evidence.runs for case in run.cases)
    incomplete = frozen.aggregate_runs(candidate_id=evidence.candidate_id, spec=spec, runs=evidence.runs[:2], raw_result_artifact_ref="artifacts/incomplete.json", generated_at=NOW().isoformat())
    assert not incomplete.suite_completed


def test_review_is_non_mutating_and_preserves_experimental_status() -> None:
    frozen = suite()
    spec = frozen.spec("alethia-scientific-multimodal-reranking", model_revision="v2")
    evidence = frozen.run(candidate_id="nvidia-nemotron-vl-rerank-vl-1b-v2", spec=spec, runner=perfect_runner, raw_result_artifact_ref="artifacts/rerank.json", now=NOW)
    review = build_approval_review(evidence)
    candidate = next(item for item in verified_nvidia_candidates() if item.candidate_id == review.candidate_id)
    assert review.recommended_decision == "KEEP_EXPERIMENTAL"
    assert not review.mutates_candidate_status
    assert candidate.status is CandidateStatus.EXPERIMENTAL


def test_stale_revision_is_visible_to_existing_approval_schema_and_scoring_is_deterministic() -> None:
    frozen = suite()
    spec = frozen.spec("alethia-scientific-text-retrieval", model_revision="v1")
    first = frozen.run(candidate_id="nvidia-nemotron-text-embed-1b-v2", spec=spec, runner=perfect_runner, raw_result_artifact_ref="artifacts/first.json", now=NOW)
    second = frozen.run(candidate_id="nvidia-nemotron-text-embed-1b-v2", spec=spec, runner=perfect_runner, raw_result_artifact_ref="artifacts/second.json", now=NOW)
    assert first.aggregate_metrics == second.aggregate_metrics
    stale = first.to_approval_result(environment_acceptance_passed=True)
    candidate = next(item for item in verified_nvidia_candidates() if item.candidate_id == stale.candidate_id)
    policy = ApprovalPolicy("review-only", {candidate.capability: CapabilityPolicy((stale.benchmark_id,), {"mrr": 0.0}, 0.0)})
    record = SpecialistApprovalGate(policy, NOW).evaluate(candidate, (stale,))
    assert "STALE_MODEL_REVISION:alethia-scientific-text-retrieval" in record.reasons
    assert stale.quality_metrics["mrr"] == 1.0

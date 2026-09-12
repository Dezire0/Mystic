"""Frozen, repeatable specialist benchmarks for ALETHEIA approval review.

This is an evidence producer only.  It never updates a candidate registry or
selects a specialist for a scientific task.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
import json
from math import log2
from pathlib import Path
from statistics import fmean, pvariance
from typing import Any, Callable, Mapping, Protocol

from mystic.alethia_approval import BenchmarkResult


FROZEN_SCHEMA = "aletheia-specialist-scientific-suite/v0"
FROZEN_DATASET_HASHES: Mapping[tuple[str, str], str] = {
    # Updated only when a material fixture change deliberately increments its version.
    ("alethia-scientific-text-retrieval", "v0.1.0"): "fbb29aac873c18a0d6e1b37a2cf0269f8c8a5d48ac2fe5b4b8de4e9762d57cec",
    ("alethia-scientific-visual-retrieval", "v0.1.0"): "cb7cb58b8355cec2af49b953094f2d5cc6c92d5ef7e59cabba196310a2bc56f2",
    ("alethia-scientific-multimodal-reranking", "v0.1.0"): "e8ab74447cdf50be48e0ec1ed5e07c725a9437197e27a087e0eb88b775c2ea1d",
}


class FrozenBenchmarkError(ValueError):
    """Raised when an evaluation manifest is altered without a version update."""


@dataclass(frozen=True, slots=True)
class BenchmarkSpec:
    benchmark_id: str
    benchmark_version: str
    capability: str
    dataset_id: str
    dataset_version: str
    dataset_sha256: str
    random_seed: int
    hardware_backend: str
    model_revision: str
    software_versions: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class BenchmarkObservation:
    """One runner response. Exceptions are preserved outside this value."""

    ranked_ids: tuple[str, ...]
    cold_load_ms: float | None
    warm_inference_ms: float | None
    peak_vram_mb: int | None
    raw_output_ref: str


class BenchmarkRunner(Protocol):
    def __call__(self, spec: BenchmarkSpec, case: Mapping[str, Any], run_number: int) -> BenchmarkObservation: ...


@dataclass(frozen=True, slots=True)
class CaseRunResult:
    case_id: str
    ranked_ids: tuple[str, ...]
    top_1: float
    recall_at_3: float
    recall_at_5: float
    reciprocal_rank: float
    ndcg: float
    correct_item_rank: int | None
    cold_load_ms: float | None
    warm_inference_ms: float | None
    peak_vram_mb: int | None
    raw_output_ref: str
    error: str | None = None


@dataclass(frozen=True, slots=True)
class BenchmarkRun:
    run_number: int
    timestamp: str
    cases: tuple[CaseRunResult, ...]


@dataclass(frozen=True, slots=True)
class BenchmarkEvidence:
    spec: BenchmarkSpec
    candidate_id: str
    runs: tuple[BenchmarkRun, ...]
    aggregate_metrics: Mapping[str, float]
    reliability: float
    reproducible: bool
    suite_completed: bool
    raw_result_artifact_ref: str
    generated_at: str

    def to_approval_result(self, *, environment_acceptance_passed: bool) -> BenchmarkResult:
        """Return the existing gate schema without inventing an approval decision."""
        return BenchmarkResult(
            candidate_id=self.candidate_id,
            benchmark_id=self.spec.benchmark_id,
            benchmark_version=self.spec.benchmark_version,
            quality_metrics={
                key: self.aggregate_metrics[key]
                for key in ("top_1", "recall_at_3", "recall_at_5", "mrr", "ndcg")
            },
            latency_ms=self.aggregate_metrics.get("warm_inference_ms_mean"),
            peak_vram_mb=round(self.aggregate_metrics["peak_vram_mb_max"])
            if self.aggregate_metrics.get("peak_vram_mb_max") is not None else None,
            execution_succeeded=self.reliability == 1.0,
            reliability=self.reliability,
            resource_cost={
                "throughput_cases_per_second": self.aggregate_metrics.get("throughput_cases_per_second"),
                "cold_load_ms_mean": self.aggregate_metrics.get("cold_load_ms_mean"),
                "software_versions": dict(self.spec.software_versions),
                "dataset_sha256": self.spec.dataset_sha256,
                "random_seed": self.spec.random_seed,
            },
            hardware_backend=self.spec.hardware_backend,
            model_revision=self.spec.model_revision,
            timestamp=self.generated_at,
            raw_evidence_ref=self.raw_result_artifact_ref,
            suite_completed=self.suite_completed,
            reproducible=self.reproducible,
            environment_acceptance_passed=environment_acceptance_passed,
        )


@dataclass(frozen=True, slots=True)
class ApprovalReviewReport:
    candidate_id: str
    capability: str
    benchmark_id: str
    benchmark_version: str
    benchmark_complete: bool
    measured_quality: Mapping[str, float]
    reliability: float
    latency: Mapping[str, float]
    peak_vram_mb: float | None
    known_failure_modes: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    recommended_decision: str
    recommendation_reason: str
    mutates_candidate_status: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _dataset_hash(dataset: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(dataset)).hexdigest()


def _rank_metrics(ranked_ids: tuple[str, ...], relevant_ids: tuple[str, ...]) -> tuple[float, float, float, float, float, int | None]:
    if not relevant_ids:
        correct_abstention = float(not ranked_ids)
        return correct_abstention, correct_abstention, correct_abstention, correct_abstention, correct_abstention, None
    relevant = set(relevant_ids)
    top_1 = float(bool(ranked_ids) and ranked_ids[0] in relevant)
    recalls = tuple(len(relevant.intersection(ranked_ids[:limit])) / len(relevant) for limit in (3, 5))
    first_rank = next((index + 1 for index, identifier in enumerate(ranked_ids) if identifier in relevant), None)
    reciprocal_rank = 1.0 / first_rank if first_rank else 0.0
    dcg = sum(1.0 / log2(index + 2) for index, identifier in enumerate(ranked_ids) if identifier in relevant)
    ideal = sum(1.0 / log2(index + 2) for index in range(min(len(relevant), len(ranked_ids))))
    return top_1, recalls[0], recalls[1], reciprocal_rank, dcg / ideal if ideal else 0.0, first_rank


class FrozenScientificBenchmarkSuite:
    """Loads a locked evaluation corpus and repeats it without mutating fixtures."""

    def __init__(self, manifest: Mapping[str, Any], fixture_root: Path | None = None) -> None:
        if manifest.get("schema_version") != FROZEN_SCHEMA:
            raise FrozenBenchmarkError("unsupported scientific suite manifest")
        self.manifest = manifest
        self.fixture_root = fixture_root

    @classmethod
    def load(cls, path: str) -> "FrozenScientificBenchmarkSuite":
        fixture_path = Path(path)
        with fixture_path.open(encoding="utf-8") as fixture_file:
            return cls(json.load(fixture_file), fixture_path.parent)

    def spec(self, benchmark_id: str, *, model_revision: str, hardware_backend: str = "Tesla T4", software_versions: Mapping[str, str] | None = None) -> BenchmarkSpec:
        suite = next((item for item in self.manifest["suites"] if item["benchmark_id"] == benchmark_id), None)
        if suite is None:
            raise FrozenBenchmarkError(f"unknown benchmark id: {benchmark_id}")
        version = str(suite["benchmark_version"])
        expected_hash = FROZEN_DATASET_HASHES.get((benchmark_id, version))
        actual_hash = _dataset_hash(suite["dataset"])
        if expected_hash is None or suite["dataset_sha256"] != actual_hash or actual_hash != expected_hash:
            raise FrozenBenchmarkError("frozen dataset hash mismatch; increment benchmark_version for material fixture changes")
        self._validate_asset_hashes(suite["dataset"])
        return BenchmarkSpec(
            benchmark_id=benchmark_id,
            benchmark_version=version,
            capability=str(suite["capability"]),
            dataset_id=str(suite["dataset"]["dataset_id"]),
            dataset_version=str(suite["dataset"]["dataset_version"]),
            dataset_sha256=actual_hash,
            random_seed=int(suite["random_seed"]),
            hardware_backend=hardware_backend,
            model_revision=model_revision,
            software_versions=dict(software_versions or {}),
        )

    def evaluation_cases(self, benchmark_id: str) -> tuple[Mapping[str, Any], ...]:
        suite = next(item for item in self.manifest["suites"] if item["benchmark_id"] == benchmark_id)
        return tuple(suite["dataset"]["frozen_evaluation"])

    def _validate_asset_hashes(self, dataset: Mapping[str, Any]) -> None:
        if not dataset.get("asset_sha256s") or self.fixture_root is None:
            return
        asset_root = self.fixture_root.parent / "scientific-v1" / "assets"
        for filename, expected_hash in dataset["asset_sha256s"].items():
            asset_path = asset_root / filename
            actual_hash = hashlib.sha256(asset_path.read_bytes()).hexdigest() if asset_path.is_file() else "MISSING"
            if actual_hash != expected_hash:
                raise FrozenBenchmarkError(f"frozen asset hash mismatch: {filename}")

    def run(
        self,
        *,
        candidate_id: str,
        spec: BenchmarkSpec,
        runner: BenchmarkRunner,
        raw_result_artifact_ref: str,
        repetitions: int = 3,
        now: Callable[[], datetime] | None = None,
    ) -> BenchmarkEvidence:
        if repetitions < 3:
            raise ValueError("approval-grade evidence requires at least three repeated executions")
        timestamp = now or (lambda: datetime.now(UTC))
        runs: list[BenchmarkRun] = []
        expected_cases = self.evaluation_cases(spec.benchmark_id)
        for run_number in range(1, repetitions + 1):
            cases: list[CaseRunResult] = []
            for case in expected_cases:
                try:
                    observation = runner(spec, case, run_number)
                    metrics = _rank_metrics(observation.ranked_ids, tuple(case["relevant_ids"]))
                    cases.append(CaseRunResult(str(case["case_id"]), observation.ranked_ids, *metrics, observation.cold_load_ms, observation.warm_inference_ms, observation.peak_vram_mb, observation.raw_output_ref))
                except Exception as error:  # Benchmark failures are evidence, not dropped samples.
                    cases.append(CaseRunResult(str(case["case_id"]), (), 0.0, 0.0, 0.0, 0.0, 0.0, None, None, None, None, "", f"{type(error).__name__}: {error}"))
            runs.append(BenchmarkRun(run_number, timestamp().isoformat(), tuple(cases)))
        return aggregate_observed_runs(
            candidate_id=candidate_id,
            spec=spec,
            runs=tuple(runs),
            raw_result_artifact_ref=raw_result_artifact_ref,
            generated_at=timestamp().isoformat(),
            required_case_count=len(expected_cases),
        )

    def aggregate_runs(
        self,
        *,
        candidate_id: str,
        spec: BenchmarkSpec,
        runs: tuple[BenchmarkRun, ...],
        raw_result_artifact_ref: str,
        generated_at: str,
    ) -> BenchmarkEvidence:
        """Aggregate externally executed runs while retaining completeness checks."""
        return aggregate_observed_runs(
            candidate_id=candidate_id,
            spec=spec,
            runs=runs,
            raw_result_artifact_ref=raw_result_artifact_ref,
            generated_at=generated_at,
            required_case_count=len(self.evaluation_cases(spec.benchmark_id)),
        )


def aggregate_observed_runs(
    *,
    candidate_id: str,
    spec: BenchmarkSpec,
    runs: tuple[BenchmarkRun, ...],
    raw_result_artifact_ref: str,
    generated_at: str,
    required_case_count: int,
) -> BenchmarkEvidence:
    """Normalize externally executed runs into the gate-compatible evidence format."""
    rows = tuple(case for run in runs for case in run.cases)
    successful = tuple(row for row in rows if row.error is None)
    aggregate = {
        "top_1": fmean(row.top_1 for row in rows),
        "recall_at_3": fmean(row.recall_at_3 for row in rows),
        "recall_at_5": fmean(row.recall_at_5 for row in rows),
        "mrr": fmean(row.reciprocal_rank for row in rows),
        "ndcg": fmean(row.ndcg for row in rows),
        "reproducibility_variance": pvariance([row.reciprocal_rank for row in rows]) if len(rows) > 1 else 0.0,
    }
    ranks = tuple(row.correct_item_rank for row in successful if row.correct_item_rank is not None)
    warm = tuple(row.warm_inference_ms for row in successful if row.warm_inference_ms is not None)
    cold = tuple(row.cold_load_ms for row in successful if row.cold_load_ms is not None)
    vram = tuple(row.peak_vram_mb for row in successful if row.peak_vram_mb is not None)
    aggregate.update({
        "warm_inference_ms_mean": fmean(warm) if warm else 0.0,
        "warm_inference_ms_variance": pvariance(warm) if len(warm) > 1 else 0.0,
        "cold_load_ms_mean": fmean(cold) if cold else 0.0,
        "peak_vram_mb_max": float(max(vram)) if vram else None,
        "throughput_cases_per_second": len(successful) / (sum(warm) / 1000) if warm and sum(warm) else 0.0,
        "correct_item_rank_mean": fmean(ranks) if ranks else 0.0,
    })
    signatures = tuple(tuple((case.case_id, case.ranked_ids, case.error) for case in run.cases) for run in runs)
    return BenchmarkEvidence(
        spec, candidate_id, runs, aggregate,
        reliability=len(successful) / len(rows) if rows else 0.0,
        reproducible=len(set(signatures)) == 1,
        suite_completed=len(runs) >= 3 and all(len(run.cases) == required_case_count for run in runs),
        raw_result_artifact_ref=raw_result_artifact_ref,
        generated_at=generated_at,
    )


def build_approval_review(evidence: BenchmarkEvidence) -> ApprovalReviewReport:
    """Summarise measured evidence without inventing thresholds or changing status."""
    failures = tuple(sorted({case.error for run in evidence.runs for case in run.cases if case.error}))
    return ApprovalReviewReport(
        candidate_id=evidence.candidate_id,
        capability=evidence.spec.capability,
        benchmark_id=evidence.spec.benchmark_id,
        benchmark_version=evidence.spec.benchmark_version,
        benchmark_complete=evidence.suite_completed,
        measured_quality={key: evidence.aggregate_metrics[key] for key in ("top_1", "recall_at_3", "recall_at_5", "mrr", "ndcg")},
        reliability=evidence.reliability,
        latency={key: evidence.aggregate_metrics[key] for key in ("cold_load_ms_mean", "warm_inference_ms_mean", "warm_inference_ms_variance", "throughput_cases_per_second")},
        peak_vram_mb=evidence.aggregate_metrics["peak_vram_mb_max"],
        known_failure_modes=failures,
        evidence_refs=(evidence.raw_result_artifact_ref,),
        recommended_decision="KEEP_EXPERIMENTAL",
        recommendation_reason="No approval thresholds are defined in v0; human review must decide whether measured evidence is sufficient.",
    )

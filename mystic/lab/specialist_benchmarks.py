"""Reproducible specialist benchmark metrics and safe result records."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from mystic.lab.schema import utc_now_iso
from mystic.lab.specialists import (
    BenchmarkStatus,
    SpecialistClassification,
    SpecialistModelRegistry,
)


@dataclass(slots=True)
class BenchmarkCase:
    case_id: str
    query: str
    relevance: dict[str, int]
    expected_text: str = ""
    expected_layout: dict[str, Any] = field(default_factory=dict)
    expected_reading_order: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SpecialistBenchmarkResult:
    benchmark_id: str
    specialist_id: str
    category: str
    execution_mode: str
    metrics: dict[str, float]
    latency_ms: float
    throughput_per_second: float
    failure_rate: float
    estimated_cost: float | None
    baseline_id: str = ""
    notes: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        if self.execution_mode not in {"fixture", "live"}:
            raise ValueError("execution_mode must be fixture or live")
        if self.category not in {"embedding", "reranking", "ocr", "parsing", "visual"}:
            raise ValueError("Unsupported specialist benchmark category")
        if not 0.0 <= self.failure_rate <= 1.0:
            raise ValueError("failure_rate must be between zero and one")

    def safe_dict(self) -> dict[str, Any]:
        return asdict(self)


class SpecialistBenchmarkHarness:
    """Measures a declared corpus; fixture metrics never approve a named candidate."""

    def __init__(self, *, root_path: str | Path, registry: SpecialistModelRegistry | None = None) -> None:
        self.root_path = Path(root_path)
        self.registry = registry
        self.result_root = self.root_path / "mystic_data" / "specialist_benchmarks"

    def evaluate_ranking(
        self,
        *,
        specialist_id: str,
        category: str,
        cases: Iterable[BenchmarkCase],
        ranker: Callable[[BenchmarkCase], list[str]],
        execution_mode: str = "fixture",
        latency_ms: float = 0.0,
        failure_count: int = 0,
        estimated_cost: float | None = None,
        baseline_id: str = "",
        notes: list[str] | None = None,
    ) -> SpecialistBenchmarkResult:
        materialized = list(cases)
        if not materialized:
            raise ValueError("Benchmark requires at least one case")
        rankings: list[list[str]] = []
        actual_failures = failure_count
        for case in materialized:
            try:
                rankings.append(ranker(case))
            except Exception:
                rankings.append([])
                actual_failures += 1
        metrics = _ranking_metrics(materialized, rankings)
        return self._persist(
            SpecialistBenchmarkResult(
                benchmark_id=_new_benchmark_id(specialist_id, category),
                specialist_id=specialist_id,
                category=category,
                execution_mode=execution_mode,
                metrics=metrics,
                latency_ms=max(0.0, latency_ms),
                throughput_per_second=len(materialized) / (latency_ms / 1000) if latency_ms > 0 else 0.0,
                failure_rate=min(1.0, actual_failures / len(materialized)),
                estimated_cost=estimated_cost,
                baseline_id=baseline_id,
                notes=list(notes or []),
            )
        )

    def evaluate_ocr(
        self,
        *,
        specialist_id: str,
        cases: Iterable[BenchmarkCase],
        extractor: Callable[[BenchmarkCase], tuple[str, dict[str, Any]]],
        execution_mode: str = "fixture",
        latency_ms: float = 0.0,
        failure_count: int = 0,
        estimated_cost: float | None = None,
    ) -> SpecialistBenchmarkResult:
        materialized = list(cases)
        if not materialized:
            raise ValueError("Benchmark requires at least one case")
        character_scores: list[float] = []
        word_scores: list[float] = []
        layout_scores: list[float] = []
        actual_failures = failure_count
        for case in materialized:
            try:
                text, layout = extractor(case)
            except Exception:
                text, layout = "", {}
                actual_failures += 1
            character_scores.append(_text_accuracy(case.expected_text, text))
            word_scores.append(_text_accuracy(" ".join(case.expected_text.split()), " ".join(text.split())))
            layout_scores.append(_mapping_overlap(case.expected_layout, layout))
        return self._persist(
            SpecialistBenchmarkResult(
                benchmark_id=_new_benchmark_id(specialist_id, "ocr"),
                specialist_id=specialist_id,
                category="ocr",
                execution_mode=execution_mode,
                metrics={
                    "character_accuracy": _average(character_scores),
                    "word_accuracy": _average(word_scores),
                    "layout_preservation": _average(layout_scores),
                },
                latency_ms=max(0.0, latency_ms),
                throughput_per_second=len(materialized) / (latency_ms / 1000) if latency_ms > 0 else 0.0,
                failure_rate=min(1.0, actual_failures / len(materialized)),
                estimated_cost=estimated_cost,
            )
        )

    def evaluate_parsing(
        self,
        *,
        specialist_id: str,
        cases: Iterable[BenchmarkCase],
        parser: Callable[[BenchmarkCase], dict[str, Any]],
        execution_mode: str = "fixture",
        latency_ms: float = 0.0,
        failure_count: int = 0,
        estimated_cost: float | None = None,
    ) -> SpecialistBenchmarkResult:
        materialized = list(cases)
        if not materialized:
            raise ValueError("Benchmark requires at least one case")
        structural_scores: list[float] = []
        table_scores: list[float] = []
        order_scores: list[float] = []
        provenance_scores: list[float] = []
        actual_failures = failure_count
        for case in materialized:
            try:
                result = parser(case)
            except Exception:
                result = {}
                actual_failures += 1
            structural_scores.append(_mapping_overlap(case.expected_layout, result.get("structure", {})))
            table_scores.append(_mapping_overlap(case.expected_layout.get("tables", {}), result.get("tables", {})))
            order_scores.append(_sequence_overlap(case.expected_reading_order, result.get("reading_order", [])))
            provenance_scores.append(1.0 if result.get("source_id") and result.get("page") is not None else 0.0)
        return self._persist(
            SpecialistBenchmarkResult(
                benchmark_id=_new_benchmark_id(specialist_id, "parsing"),
                specialist_id=specialist_id,
                category="parsing",
                execution_mode=execution_mode,
                metrics={
                    "structural_accuracy": _average(structural_scores),
                    "table_extraction_quality": _average(table_scores),
                    "reading_order_correctness": _average(order_scores),
                    "provenance_preservation": _average(provenance_scores),
                },
                latency_ms=max(0.0, latency_ms),
                throughput_per_second=len(materialized) / (latency_ms / 1000) if latency_ms > 0 else 0.0,
                failure_rate=min(1.0, actual_failures / len(materialized)),
                estimated_cost=estimated_cost,
            )
        )

    def compare_to_baseline(
        self,
        *,
        candidate: SpecialistBenchmarkResult,
        baseline: SpecialistBenchmarkResult,
    ) -> dict[str, Any]:
        if candidate.category != baseline.category:
            raise ValueError("Candidate and baseline categories must match")
        shared = sorted(set(candidate.metrics) & set(baseline.metrics))
        return {
            "candidate_id": candidate.specialist_id,
            "baseline_id": baseline.specialist_id,
            "category": candidate.category,
            "metric_delta": {name: candidate.metrics[name] - baseline.metrics[name] for name in shared},
            "latency_delta_ms": candidate.latency_ms - baseline.latency_ms,
            "failure_rate_delta": candidate.failure_rate - baseline.failure_rate,
            "estimated_cost_delta": _cost_delta(candidate.estimated_cost, baseline.estimated_cost),
            "comparison_is_live": candidate.execution_mode == baseline.execution_mode == "live",
        }

    def approve_live_candidate(
        self,
        *,
        result: SpecialistBenchmarkResult,
        baseline: SpecialistBenchmarkResult,
        classification: str,
        quality_metric: str,
        reliability: float,
    ) -> dict[str, Any]:
        if self.registry is None:
            raise ValueError("A registry is required to approve a candidate")
        comparison = self.compare_to_baseline(candidate=result, baseline=baseline)
        if not comparison["comparison_is_live"]:
            raise ValueError("Only a live candidate-versus-baseline comparison can approve a specialist")
        if quality_metric not in result.metrics:
            raise ValueError("quality_metric is not present in candidate results")
        model = self.registry.update_benchmark(
            result.specialist_id,
            benchmark_status=BenchmarkStatus.APPROVED.value,
            classification=SpecialistClassification(classification).value,
            benchmark_quality=result.metrics[quality_metric],
            reliability=reliability,
        )
        return {"specialist": model.safe_dict(), "comparison": comparison}

    def fixture_smoke(self) -> SpecialistBenchmarkResult:
        cases = [
            BenchmarkCase(
                case_id="physics-gravity",
                query="What changes projectile range?",
                relevance={"gravity": 3, "history": 0},
            ),
            BenchmarkCase(
                case_id="biology-cell",
                query="What does a cell membrane regulate?",
                relevance={"membrane": 3, "astronomy": 0},
            ),
        ]

        def rank(case: BenchmarkCase) -> list[str]:
            return [identifier for identifier, _ in sorted(case.relevance.items(), key=lambda item: item[1], reverse=True)]

        return self.evaluate_ranking(
            specialist_id="fixture.deterministic-ranking-baseline",
            category="embedding",
            cases=cases,
            ranker=rank,
            execution_mode="fixture",
            notes=["Fixture wiring check only; this is not a named-provider model evaluation."],
        )

    def _persist(self, result: SpecialistBenchmarkResult) -> SpecialistBenchmarkResult:
        self.result_root.mkdir(parents=True, exist_ok=True)
        target = self.result_root / f"{result.benchmark_id}.json"
        target.write_text(json.dumps(result.safe_dict(), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        if self.registry is not None and result.specialist_id in {item.specialist_id for item in self.registry.list()}:
            if result.execution_mode == "fixture":
                model = self.registry.get(result.specialist_id)
                if model.benchmark_status == BenchmarkStatus.NOT_RUN.value:
                    model.benchmark_status = BenchmarkStatus.FIXTURE_ONLY.value
        return result


def _ranking_metrics(cases: list[BenchmarkCase], rankings: list[list[str]]) -> dict[str, float]:
    recall5: list[float] = []
    mrr: list[float] = []
    ndcg10: list[float] = []
    top_n: list[float] = []
    for case, ranking in zip(cases, rankings):
        relevant = {identifier for identifier, grade in case.relevance.items() if grade > 0}
        top5 = ranking[:5]
        top10 = ranking[:10]
        recall5.append(len(set(top5) & relevant) / len(relevant) if relevant else 1.0)
        first = next((index + 1 for index, identifier in enumerate(ranking) if identifier in relevant), None)
        mrr.append(1.0 / first if first else 0.0)
        top_n.append(1.0 if any(identifier in relevant for identifier in top5) else 0.0)
        dcg = sum((2 ** case.relevance.get(identifier, 0) - 1) / _log2(index + 2) for index, identifier in enumerate(top10))
        ideal = sorted(case.relevance.values(), reverse=True)[:10]
        ideal_dcg = sum((2 ** grade - 1) / _log2(index + 2) for index, grade in enumerate(ideal))
        ndcg10.append(dcg / ideal_dcg if ideal_dcg else 1.0)
    return {"recall_at_5": _average(recall5), "mrr": _average(mrr), "ndcg_at_10": _average(ndcg10), "top_5_relevance": _average(top_n)}


def _text_accuracy(expected: str, observed: str) -> float:
    if not expected:
        return 1.0 if not observed else 0.0
    distance = _levenshtein(expected, observed)
    return max(0.0, 1.0 - distance / max(len(expected), len(observed), 1))


def _levenshtein(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for index, left_char in enumerate(left, start=1):
        current = [index]
        for right_index, right_char in enumerate(right, start=1):
            current.append(min(current[-1] + 1, previous[right_index] + 1, previous[right_index - 1] + (left_char != right_char)))
        previous = current
    return previous[-1]


def _mapping_overlap(expected: Mapping[str, Any], observed: Mapping[str, Any]) -> float:
    if not expected:
        return 1.0 if not observed else 0.0
    expected_items = set(json.dumps({key: value}, sort_keys=True) for key, value in expected.items())
    observed_items = set(json.dumps({key: value}, sort_keys=True) for key, value in observed.items())
    return len(expected_items & observed_items) / len(expected_items)


def _sequence_overlap(expected: list[str], observed: list[str]) -> float:
    if not expected:
        return 1.0 if not observed else 0.0
    return sum(left == right for left, right in zip(expected, observed)) / len(expected)


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _log2(value: int) -> float:
    from math import log2

    return log2(value)


def _new_benchmark_id(specialist_id: str, category: str) -> str:
    safe = "".join(char if char.isalnum() else "_" for char in specialist_id)
    return f"benchmark_{safe}_{category}_{utc_now_iso().replace(':', '').replace('+', '').replace('-', '')}"


def _cost_delta(candidate: float | None, baseline: float | None) -> float | None:
    if candidate is None or baseline is None:
        return None
    return candidate - baseline

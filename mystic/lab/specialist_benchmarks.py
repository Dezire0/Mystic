"""Reproducible specialist benchmark metrics and safe result records."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from pathlib import Path
import re
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
    language: str = "en"
    source_id: str = ""
    location: str = ""


@dataclass(slots=True)
class SpecialistBenchmarkCorpus:
    """Versioned, validated evaluation inputs with source references intact."""

    corpus_id: str
    version: str
    schema_version: str
    corpus_hash: str
    source_path: str
    documents: dict[str, dict[str, Any]]
    retrieval_cases: list[BenchmarkCase]
    ocr_cases: list[BenchmarkCase]
    ocr_inputs: dict[str, dict[str, Any]]
    parsing_cases: list[BenchmarkCase]
    visual_cases: list[BenchmarkCase]
    provenance_cases: list[dict[str, Any]]
    asset_gaps: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: str | Path) -> "SpecialistBenchmarkCorpus":
        source = Path(path)
        raw = source.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Benchmark corpus must be a JSON object")
        required = ("schema_version", "corpus_id", "version", "documents", "retrieval_cases", "ocr_cases", "parsing_cases", "visual_cases", "provenance_cases")
        if any(not payload.get(key) for key in required):
            raise ValueError("Benchmark corpus is missing a required section")
        documents: dict[str, dict[str, Any]] = {}
        for document in payload["documents"]:
            if not isinstance(document, dict):
                raise ValueError("Benchmark document entries must be objects")
            document_id = str(document.get("document_id", ""))
            text = document.get("text")
            source_url = str(document.get("source_url", ""))
            if not _safe_id(document_id) or not isinstance(text, str) or not text.strip() or not source_url.startswith("https://"):
                raise ValueError("Benchmark documents require a safe identifier, text, and HTTPS source URL")
            if document_id in documents:
                raise ValueError(f"Duplicate benchmark document: {document_id}")
            documents[document_id] = dict(document)
        retrieval_cases = [_ranking_case(item, documents=documents) for item in payload["retrieval_cases"]]
        ocr_cases = [_observation_case(item, category="ocr") for item in payload["ocr_cases"]]
        parsing_cases = [_observation_case(item, category="parsing") for item in payload["parsing_cases"]]
        visual_cases = [_visual_case(item) for item in payload["visual_cases"]]
        provenance_cases = [dict(item) for item in payload["provenance_cases"] if isinstance(item, dict)]
        if not retrieval_cases or not ocr_cases or not parsing_cases or not visual_cases or not provenance_cases:
            raise ValueError("Benchmark corpus must cover retrieval, OCR, parsing, visual, and provenance cases")
        gaps = [str(item.get("case_id", "unknown")) for section in (payload["ocr_cases"], payload["parsing_cases"], payload["visual_cases"]) for item in section if isinstance(item, dict) and item.get("asset_status")]
        return cls(
            corpus_id=str(payload["corpus_id"]),
            version=str(payload["version"]),
            schema_version=str(payload["schema_version"]),
            corpus_hash=hashlib.sha256(raw).hexdigest(),
            source_path=str(source),
            documents=documents,
            retrieval_cases=retrieval_cases,
            ocr_cases=ocr_cases,
            ocr_inputs={str(item.get("case_id", "")): dict(item) for item in payload["ocr_cases"] if isinstance(item, dict)},
            parsing_cases=parsing_cases,
            visual_cases=visual_cases,
            provenance_cases=provenance_cases,
            asset_gaps=gaps,
        )


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
    corpus_id: str = ""
    corpus_version: str = ""
    corpus_hash: str = ""
    configuration: dict[str, Any] = field(default_factory=dict)
    request_count: int = 0
    latency_samples_ms: list[float] = field(default_factory=list)
    provenance_preserved: bool = False
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        if self.execution_mode not in {"fixture", "live", "baseline"}:
            raise ValueError("execution_mode must be fixture, baseline, or live")
        if self.category not in {"embedding", "reranking", "ocr", "parsing", "visual"}:
            raise ValueError("Unsupported specialist benchmark category")
        if not 0.0 <= self.failure_rate <= 1.0:
            raise ValueError("failure_rate must be between zero and one")
        if self.request_count < 0 or any(value < 0 for value in self.latency_samples_ms):
            raise ValueError("Benchmark request count and latency samples must be non-negative")

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
        corpus: SpecialistBenchmarkCorpus | None = None,
        configuration: Mapping[str, Any] | None = None,
        request_count: int = 0,
        latency_samples_ms: list[float] | None = None,
        provenance_preserved: bool = False,
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
                corpus_id=corpus.corpus_id if corpus else "",
                corpus_version=corpus.version if corpus else "",
                corpus_hash=corpus.corpus_hash if corpus else "",
                configuration=_safe_configuration(configuration),
                request_count=request_count,
                latency_samples_ms=[float(value) for value in latency_samples_ms or []],
                provenance_preserved=provenance_preserved,
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
        corpus: SpecialistBenchmarkCorpus | None = None,
        configuration: Mapping[str, Any] | None = None,
        request_count: int = 0,
        latency_samples_ms: list[float] | None = None,
        provenance_preserved: bool = False,
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
                corpus_id=corpus.corpus_id if corpus else "",
                corpus_version=corpus.version if corpus else "",
                corpus_hash=corpus.corpus_hash if corpus else "",
                configuration=_safe_configuration(configuration),
                request_count=request_count,
                latency_samples_ms=[float(value) for value in latency_samples_ms or []],
                provenance_preserved=provenance_preserved,
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
        corpus: SpecialistBenchmarkCorpus | None = None,
        configuration: Mapping[str, Any] | None = None,
        request_count: int = 0,
        latency_samples_ms: list[float] | None = None,
        provenance_preserved: bool = False,
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
                corpus_id=corpus.corpus_id if corpus else "",
                corpus_version=corpus.version if corpus else "",
                corpus_hash=corpus.corpus_hash if corpus else "",
                configuration=_safe_configuration(configuration),
                request_count=request_count,
                latency_samples_ms=[float(value) for value in latency_samples_ms or []],
                provenance_preserved=provenance_preserved,
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
            "comparison_is_live": candidate.execution_mode == "live" and baseline.execution_mode in {"live", "baseline"},
            "candidate_latency_percentiles_ms": _latency_percentiles(candidate.latency_samples_ms),
            "baseline_latency_percentiles_ms": _latency_percentiles(baseline.latency_samples_ms),
            "corpus_match": bool(candidate.corpus_hash) and candidate.corpus_hash == baseline.corpus_hash,
        }

    def classify_live_candidate(
        self,
        *,
        candidate: SpecialistBenchmarkResult,
        baseline: SpecialistBenchmarkResult,
        quality_metric: str,
        essential_capability: bool = False,
    ) -> dict[str, Any]:
        """Apply transparent, conservative activation criteria to a live result."""
        comparison = self.compare_to_baseline(candidate=candidate, baseline=baseline)
        reasons: list[str] = []
        if not comparison["comparison_is_live"]:
            reasons.append("candidate and baseline comparison is not a valid live evaluation")
        if not comparison["corpus_match"]:
            reasons.append("candidate and baseline do not use the same versioned corpus")
        if quality_metric not in candidate.metrics or quality_metric not in baseline.metrics:
            reasons.append("requested quality metric is missing")
        candidate_quality = candidate.metrics.get(quality_metric, 0.0)
        baseline_quality = baseline.metrics.get(quality_metric, 0.0)
        quality_delta = candidate_quality - baseline_quality
        if candidate.failure_rate > 0.05:
            return {"classification": SpecialistClassification.REJECTED.value, "approve": False, "reasons": reasons + ["failure rate exceeds 5%"], "comparison": comparison, "quality_metric": quality_metric}
        if not candidate.provenance_preserved:
            return {"classification": SpecialistClassification.REJECTED.value, "approve": False, "reasons": reasons + ["benchmark output did not preserve required provenance"], "comparison": comparison, "quality_metric": quality_metric}
        if reasons:
            return {"classification": SpecialistClassification.UNCLASSIFIED.value, "approve": False, "reasons": reasons, "comparison": comparison, "quality_metric": quality_metric}
        if essential_capability and candidate_quality >= 0.90:
            classification = SpecialistClassification.ESSENTIAL.value
            approve = True
            reasons.append("candidate provides a measured capability absent from the baseline")
        elif quality_delta >= 0.03 and candidate_quality >= 0.70:
            classification = SpecialistClassification.SUPERIOR.value
            approve = True
            reasons.append(f"{quality_metric} improves by at least 0.03 over the baseline")
        elif quality_delta >= -0.01 and _accelerates(candidate=candidate, baseline=baseline):
            classification = SpecialistClassification.ACCELERATOR.value
            approve = True
            reasons.append("quality is within one point of baseline and measured cost or latency is materially lower")
        else:
            classification = SpecialistClassification.REDUNDANT.value
            approve = False
            reasons.append("no material capability, quality, latency, or cost advantage was measured")
        return {
            "classification": classification,
            "approve": approve,
            "reasons": reasons,
            "comparison": comparison,
            "quality_metric": quality_metric,
            "quality": candidate_quality,
            "reliability": 1.0 - candidate.failure_rate,
        }

    def approve_live_candidate(
        self,
        *,
        result: SpecialistBenchmarkResult,
        baseline: SpecialistBenchmarkResult,
        quality_metric: str,
        essential_capability: bool = False,
        classification: str | None = None,
        reliability: float | None = None,
    ) -> dict[str, Any]:
        if self.registry is None:
            raise ValueError("A registry is required to approve a candidate")
        # Kept only to provide a clear compatibility failure for old callers; a
        # caller cannot self-declare an approval classification or reliability.
        if classification is not None or reliability is not None:
            raise ValueError("Classification and reliability are derived from the live benchmark, not caller input")
        decision = self.classify_live_candidate(
            candidate=result,
            baseline=baseline,
            quality_metric=quality_metric,
            essential_capability=essential_capability,
        )
        if not decision["approve"]:
            raise ValueError("Live benchmark did not meet the evidence-backed activation gate")
        model = self.registry.update_benchmark(
            result.specialist_id,
            benchmark_status=BenchmarkStatus.APPROVED.value,
            classification=SpecialistClassification(decision["classification"]).value,
            benchmark_quality=result.metrics[quality_metric],
            reliability=float(decision["reliability"]),
        )
        return {"specialist": model.safe_dict(), "decision": decision}

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

    def list_results(self, *, specialist_id: str = "", limit: int = 20) -> list[dict[str, Any]]:
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        if not self.result_root.exists():
            return []
        results: list[dict[str, Any]] = []
        for path in sorted(self.result_root.glob("*.json"), reverse=True):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict):
                continue
            if specialist_id and payload.get("specialist_id") != specialist_id:
                continue
            results.append(_safe_result_summary(payload))
            if len(results) >= limit:
                break
        return results

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


def _ranking_case(value: object, *, documents: Mapping[str, Mapping[str, Any]]) -> BenchmarkCase:
    if not isinstance(value, Mapping):
        raise ValueError("Retrieval case must be an object")
    case_id = str(value.get("case_id", ""))
    query = str(value.get("query", ""))
    relevance = value.get("relevance")
    candidate_ids = value.get("candidate_ids")
    if not _safe_id(case_id) or not query or not isinstance(relevance, Mapping) or not isinstance(candidate_ids, list):
        raise ValueError("Retrieval case is missing an identifier, query, candidate IDs, or relevance labels")
    normalized = {str(identifier): int(grade) for identifier, grade in relevance.items()}
    if not normalized or any(identifier not in documents for identifier in normalized) or any(identifier not in documents for identifier in candidate_ids):
        raise ValueError("Retrieval case refers to an unknown document")
    if set(str(identifier) for identifier in candidate_ids) != set(normalized):
        raise ValueError("Retrieval relevance labels must exactly cover candidate IDs")
    return BenchmarkCase(case_id=case_id, query=query, relevance=normalized, language=str(value.get("language", "en")))


def _observation_case(value: object, *, category: str) -> BenchmarkCase:
    if not isinstance(value, Mapping):
        raise ValueError(f"{category} case must be an object")
    case_id = str(value.get("case_id", ""))
    expected_layout = value.get("expected_layout", {})
    if not _safe_id(case_id) or not isinstance(expected_layout, Mapping):
        raise ValueError(f"{category} case is missing an identifier or layout labels")
    return BenchmarkCase(
        case_id=case_id,
        query=str(value.get("query", "")),
        relevance={str(key): int(item) for key, item in dict(value.get("relevance", {})).items()},
        expected_text=str(value.get("expected_text", "")),
        expected_layout=dict(expected_layout),
        expected_reading_order=[str(item) for item in value.get("expected_reading_order", [])],
        language=str(value.get("language", "en")),
        source_id=str(value.get("source_id", "")),
        location=f"page:{value.get('page', 1)}",
    )


def _visual_case(value: object) -> BenchmarkCase:
    if not isinstance(value, Mapping):
        raise ValueError("Visual case must be an object")
    case_id = str(value.get("case_id", ""))
    relevance = value.get("relevance")
    if not _safe_id(case_id) or not isinstance(relevance, Mapping) or not relevance:
        raise ValueError("Visual case is missing an identifier or relevance labels")
    return BenchmarkCase(
        case_id=case_id,
        query=str(value.get("query", "")),
        relevance={str(key): int(item) for key, item in relevance.items()},
    )


def _safe_id(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_.-]{1,160}", value))


def _safe_configuration(value: Mapping[str, Any] | None) -> dict[str, Any]:
    """Keep reproducibility metadata but reject credentials and raw endpoint paths."""
    if not value:
        return {}
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    decoded = json.loads(encoded)
    if _contains_secret_key(decoded):
        raise ValueError("Benchmark configuration must not contain credentials or authorization material")
    return decoded


def _contains_secret_key(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized != "api_key_configured" and any(term in normalized for term in ("api_key", "authorization", "token", "secret", "password")):
                return True
            if _contains_secret_key(item):
                return True
    elif isinstance(value, list):
        return any(_contains_secret_key(item) for item in value)
    return False


def _safe_result_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "benchmark_id": str(payload.get("benchmark_id", "")),
        "specialist_id": str(payload.get("specialist_id", "")),
        "category": str(payload.get("category", "")),
        "execution_mode": str(payload.get("execution_mode", "")),
        "metrics": dict(payload.get("metrics", {})),
        "latency_ms": float(payload.get("latency_ms", 0.0)),
        "failure_rate": float(payload.get("failure_rate", 0.0)),
        "estimated_cost": payload.get("estimated_cost"),
        "corpus_id": str(payload.get("corpus_id", "")),
        "corpus_version": str(payload.get("corpus_version", "")),
        "created_at": str(payload.get("created_at", "")),
    }


def _latency_percentiles(samples: list[float]) -> dict[str, float]:
    if not samples:
        return {"p50": 0.0, "p95": 0.0}
    ordered = sorted(samples)
    return {
        "p50": ordered[min(len(ordered) - 1, round((len(ordered) - 1) * 0.50))],
        "p95": ordered[min(len(ordered) - 1, round((len(ordered) - 1) * 0.95))],
    }


def _accelerates(*, candidate: SpecialistBenchmarkResult, baseline: SpecialistBenchmarkResult) -> bool:
    lower_latency = baseline.latency_ms > 0 and candidate.latency_ms <= baseline.latency_ms * 0.75
    lower_cost = (
        candidate.estimated_cost is not None
        and baseline.estimated_cost is not None
        and candidate.estimated_cost <= baseline.estimated_cost * 0.75
    )
    return lower_latency or lower_cost


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

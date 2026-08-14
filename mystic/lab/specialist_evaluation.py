"""Reproducible, bounded Wave 1 specialist evaluation.

This module is intentionally a local operator surface, not an MCP tool.  It runs
only the fixed Phase 2D.2 candidate set and records activation decisions that the
normal router can later honour.  It does not provide arbitrary model execution.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from math import sqrt
from pathlib import Path
import re
from time import perf_counter
from typing import Any, Mapping

from mystic.lab.specialist_benchmarks import (
    BenchmarkCase,
    SpecialistBenchmarkCorpus,
    SpecialistBenchmarkHarness,
    SpecialistBenchmarkResult,
)
from mystic.lab.specialists import (
    SpecialistExecutionResult,
    SpecialistFailureType,
    SpecialistModel,
    SpecialistRuntime,
)


WAVE_1 = {
    "embedding": "nvidia.nemotron-3-embed-1b",
    "reranking": "nvidia.llama-nemotron-rerank-1b-v2",
    "ocr": "nvidia.nemotron-ocr-v2",
}
DEFAULT_CORPUS = Path("benchmarks/phase2d/v1/corpus.json")


@dataclass(slots=True)
class Wave1EvaluationReport:
    status: str
    corpus_id: str
    corpus_version: str
    corpus_hash: str
    results: list[dict[str, Any]]
    decisions: list[dict[str, Any]]
    blockers: list[str]

    def safe_dict(self) -> dict[str, Any]:
        return asdict(self)


class Wave1SpecialistEvaluator:
    """Compares fixed Wave 1 candidates with Mystic's non-specialist baseline."""

    def __init__(
        self,
        *,
        root_path: str | Path,
        runtime: SpecialistRuntime | None = None,
        harness: SpecialistBenchmarkHarness | None = None,
        corpus_path: str | Path | None = None,
    ) -> None:
        self.root_path = Path(root_path)
        self.runtime = runtime or SpecialistRuntime(root_path=self.root_path)
        self.harness = harness or SpecialistBenchmarkHarness(root_path=self.root_path, registry=self.runtime.registry)
        self.corpus = SpecialistBenchmarkCorpus.load(self.root_path / (corpus_path or DEFAULT_CORPUS))

    def readiness(self) -> dict[str, Any]:
        provider = self.runtime.providers.get("nvidia_nim")
        safe_config = provider.safe_configuration() if provider is not None and hasattr(provider, "safe_configuration") else {}
        model_health = {specialist_id: self.runtime.registry.get(specialist_id).health for specialist_id in WAVE_1.values()}
        blockers: list[str] = []
        if self.corpus.asset_gaps:
            blockers.append("CORPUS_REAL_DOCUMENT_ASSETS_REQUIRED:" + ",".join(self.corpus.asset_gaps))
        if any(health != "healthy" for health in model_health.values()):
            blockers.append("NVIDIA_NIM_WAVE_1_NOT_SAFELY_CONFIGURED")
        return {"corpus": _corpus_summary(self.corpus), "provider_configuration": safe_config, "model_health": model_health, "blockers": blockers}

    def run_baselines(self) -> Wave1EvaluationReport:
        """Persist a versioned Mystic lexical/no-OCR baseline without network calls."""
        embedding = self.harness.evaluate_ranking(
            specialist_id="mystic.lexical-retrieval-baseline",
            category="embedding",
            cases=self.corpus.retrieval_cases,
            ranker=lambda case: _lexical_rank(case, self.corpus.documents),
            execution_mode="baseline",
            baseline_id="mystic.lexical-retrieval-baseline",
            notes=["Existing non-specialist lexical candidate retrieval baseline; not a GPT quality claim."],
            corpus=self.corpus,
            configuration={"baseline": "lexical_token_overlap_v1", "network_calls": 0},
            provenance_preserved=True,
        )
        reranking = self.harness.evaluate_ranking(
            specialist_id="mystic.lexical-rerank-baseline",
            category="reranking",
            cases=self.corpus.retrieval_cases,
            ranker=lambda case: _lexical_rank(case, self.corpus.documents),
            execution_mode="baseline",
            baseline_id="mystic.lexical-rerank-baseline",
            notes=["Existing non-specialist lexical reranking baseline; not a GPT quality claim."],
            corpus=self.corpus,
            configuration={"baseline": "lexical_token_overlap_v1", "network_calls": 0},
            provenance_preserved=True,
        )
        results = [embedding.safe_dict(), reranking.safe_dict()]
        blockers: list[str] = []
        if self._ocr_asset_gaps():
            blockers.append("REAL_DOCUMENT_OCR_BASELINE_PENDING")
        else:
            ocr = self.harness.evaluate_ocr(
                specialist_id="mystic.no-ocr-baseline",
                cases=self.corpus.ocr_cases,
                extractor=lambda case: ("", {}),
                execution_mode="baseline",
                baseline_id="mystic.no-ocr-baseline",
                notes=["Existing pipeline has no OCR specialist; this baseline deliberately emits no extracted observations."],
                corpus=self.corpus,
                configuration={"baseline": "no_ocr_capability_v1", "network_calls": 0},
                provenance_preserved=True,
            )
            results.append(ocr.safe_dict())
        return Wave1EvaluationReport(
            status="baseline_recorded",
            corpus_id=self.corpus.corpus_id,
            corpus_version=self.corpus.version,
            corpus_hash=self.corpus.corpus_hash,
            results=results,
            decisions=[],
            blockers=[item for item in blockers if item],
        )

    def run_live(self) -> Wave1EvaluationReport:
        """Run only configured Wave 1 operations and activate only passed decisions."""
        readiness = self.readiness()
        baseline_report = self.run_baselines()
        baselines = {result["category"]: _result_from_dict(result) for result in baseline_report.results}
        results: list[SpecialistBenchmarkResult] = []
        decisions: list[dict[str, Any]] = []
        blockers = list(readiness["blockers"])
        if self.runtime.registry.get(WAVE_1["embedding"]).health == "healthy":
            results.append(self._evaluate_embedding())
        else:
            blockers.append("EMBEDDING_NOT_RUN:provider_not_ready")
        if self.runtime.registry.get(WAVE_1["reranking"]).health == "healthy":
            results.append(self._evaluate_reranking())
        else:
            blockers.append("RERANKING_NOT_RUN:provider_not_ready")
        if self._ocr_asset_gaps():
            blockers.append("OCR_NOT_RUN:real_document_assets_required")
        elif self.runtime.registry.get(WAVE_1["ocr"]).health == "healthy":
            results.append(self._evaluate_ocr())
        else:
            blockers.append("OCR_NOT_RUN:provider_not_ready")
        for result in results:
            baseline = baselines.get(result.category)
            if baseline is None:
                continue
            decision = self.harness.classify_live_candidate(
                candidate=result,
                baseline=baseline,
                quality_metric=_quality_metric_for(result.category),
                essential_capability=result.category == "ocr",
            )
            decision["specialist_id"] = result.specialist_id
            decision["benchmark_id"] = result.benchmark_id
            if decision["approve"]:
                self._activate(result=result, baseline=baseline, decision=decision)
            decisions.append(decision)
        status = "completed" if not blockers else "partial"
        return Wave1EvaluationReport(
            status=status,
            corpus_id=self.corpus.corpus_id,
            corpus_version=self.corpus.version,
            corpus_hash=self.corpus.corpus_hash,
            results=[*baseline_report.results, *(result.safe_dict() for result in results)],
            decisions=decisions,
            blockers=_unique(blockers),
        )

    def _evaluate_embedding(self) -> SpecialistBenchmarkResult:
        model = self.runtime.registry.get(WAVE_1["embedding"])
        document_ids = list(self.corpus.documents)
        document_texts = [str(self.corpus.documents[identifier]["text"]) for identifier in document_ids]
        latency_samples: list[float] = []
        failures = 0
        document_result = self._execute(model, "embed", {"texts": document_texts, "input_type": "passage"})
        latency_samples.append(document_result.latency_ms)
        document_embeddings = _embeddings(document_result, expected=len(document_ids))
        if document_embeddings is None:
            failures += 1
            document_embeddings = []
        query_result = self._execute(model, "embed", {"texts": [case.query for case in self.corpus.retrieval_cases], "input_type": "query"})
        latency_samples.append(query_result.latency_ms)
        query_embeddings = _embeddings(query_result, expected=len(self.corpus.retrieval_cases))
        if query_embeddings is None:
            failures += 1
            query_embeddings = []

        def rank(case: BenchmarkCase) -> list[str]:
            if len(document_embeddings) != len(document_ids) or len(query_embeddings) != len(self.corpus.retrieval_cases):
                raise ValueError("embedding call failed")
            query_index = next(index for index, item in enumerate(self.corpus.retrieval_cases) if item.case_id == case.case_id)
            embedding_by_id = dict(zip(document_ids, document_embeddings))
            return sorted(case.relevance, key=lambda identifier: _cosine(query_embeddings[query_index], embedding_by_id[identifier]), reverse=True)

        return self.harness.evaluate_ranking(
            specialist_id=model.specialist_id,
            category="embedding",
            cases=self.corpus.retrieval_cases,
            ranker=rank,
            execution_mode="live",
            latency_ms=_average(latency_samples),
            failure_count=failures,
            baseline_id="mystic.lexical-retrieval-baseline",
            notes=["NVIDIA NIM Wave 1 embedding evaluation."],
            corpus=self.corpus,
            configuration=self._safe_provider_configuration(),
            request_count=2,
            latency_samples_ms=latency_samples,
            provenance_preserved=True,
        )

    def _evaluate_reranking(self) -> SpecialistBenchmarkResult:
        model = self.runtime.registry.get(WAVE_1["reranking"])
        latency_samples: list[float] = []
        failures = 0
        outputs: dict[str, list[float]] = {}
        for case in self.corpus.retrieval_cases:
            passages = [str(self.corpus.documents[identifier]["text"]) for identifier in case.relevance]
            result = self._execute(model, "rerank", {"query": case.query, "passages": passages})
            latency_samples.append(result.latency_ms)
            scores = result.output.get("scores") if result.succeeded else None
            if not isinstance(scores, list) or len(scores) != len(passages) or any(not isinstance(value, (int, float)) for value in scores):
                failures += 1
                continue
            outputs[case.case_id] = [float(value) for value in scores]

        def rank(case: BenchmarkCase) -> list[str]:
            scores = outputs.get(case.case_id)
            if scores is None:
                raise ValueError("reranking call failed")
            return [identifier for identifier, _ in sorted(zip(case.relevance, scores), key=lambda item: item[1], reverse=True)]

        return self.harness.evaluate_ranking(
            specialist_id=model.specialist_id,
            category="reranking",
            cases=self.corpus.retrieval_cases,
            ranker=rank,
            execution_mode="live",
            latency_ms=_average(latency_samples),
            failure_count=failures,
            baseline_id="mystic.lexical-rerank-baseline",
            notes=["NVIDIA NIM Wave 1 reranking evaluation."],
            corpus=self.corpus,
            configuration=self._safe_provider_configuration(),
            request_count=len(self.corpus.retrieval_cases),
            latency_samples_ms=latency_samples,
            provenance_preserved=True,
        )

    def _evaluate_ocr(self) -> SpecialistBenchmarkResult:
        model = self.runtime.registry.get(WAVE_1["ocr"])
        latency_samples: list[float] = []
        failures = 0

        def extract(case: BenchmarkCase) -> tuple[str, dict[str, Any]]:
            nonlocal failures
            item = self.corpus.ocr_inputs[case.case_id]
            image = item.get("image_data_url")
            if not isinstance(image, str) or not image:
                failures += 1
                raise ValueError("OCR image asset is unavailable")
            result = self._execute(model, "ocr", {"image": image, "merge_level": "paragraph"})
            latency_samples.append(result.latency_ms)
            if not result.succeeded:
                failures += 1
                raise ValueError("OCR call failed")
            pages = result.output.get("pages")
            page = pages[0] if isinstance(pages, list) and pages and isinstance(pages[0], Mapping) else {}
            return str(page.get("text", "")), {"detection_count": len(page.get("detections", []))}

        return self.harness.evaluate_ocr(
            specialist_id=model.specialist_id,
            cases=self.corpus.ocr_cases,
            extractor=extract,
            execution_mode="live",
            latency_ms=_average(latency_samples),
            failure_count=failures,
            corpus=self.corpus,
            configuration=self._safe_provider_configuration(),
            request_count=len(self.corpus.ocr_cases),
            latency_samples_ms=latency_samples,
            provenance_preserved=True,
        )

    def _execute(self, model: SpecialistModel, operation: str, payload: Mapping[str, Any]) -> SpecialistExecutionResult:
        provider = self.runtime.providers.get(model.provider)
        if provider is None:
            return SpecialistExecutionResult(
                specialist_id=model.specialist_id,
                provider=model.provider,
                operation=operation,
                status="failed",
                failure_type=SpecialistFailureType.PROVIDER_OFFLINE.value,
                safe_error="No configured provider is available for this benchmark candidate.",
            )
        started = perf_counter()
        result = provider.execute(model=model, operation=operation, payload=payload)
        result.latency_ms = result.latency_ms or (perf_counter() - started) * 1000
        return result

    def _activate(
        self,
        *,
        result: SpecialistBenchmarkResult,
        baseline: SpecialistBenchmarkResult,
        decision: Mapping[str, Any],
    ) -> None:
        approved = self.harness.approve_live_candidate(
            result=result,
            baseline=baseline,
            quality_metric=str(decision["quality_metric"]),
            essential_capability=result.category == "ocr",
        )
        model = self.runtime.registry.enable(result.specialist_id)
        if self.runtime.approvals is None:
            raise ValueError("A root-backed specialist runtime is required to persist activation")
        self.runtime.approvals.record(
            model=model,
            benchmark_id=result.benchmark_id,
            benchmark_result_hash=hashlib.sha256(
                (self.harness.result_root / f"{result.benchmark_id}.json").read_bytes()
            ).hexdigest(),
            quality_metric=str(decision["quality_metric"]),
        )
        decision["activation"] = approved["specialist"]

    def _safe_provider_configuration(self) -> dict[str, Any]:
        provider = self.runtime.providers.get("nvidia_nim")
        return provider.safe_configuration() if provider is not None and hasattr(provider, "safe_configuration") else {"provider": "unknown"}

    def _ocr_asset_gaps(self) -> list[str]:
        return [
            case.case_id
            for case in self.corpus.ocr_cases
            if not isinstance(self.corpus.ocr_inputs.get(case.case_id, {}).get("image_data_url"), str)
            or not self.corpus.ocr_inputs[case.case_id].get("image_data_url")
        ]


def _corpus_summary(corpus: SpecialistBenchmarkCorpus) -> dict[str, Any]:
    return {
        "corpus_id": corpus.corpus_id,
        "version": corpus.version,
        "corpus_hash": corpus.corpus_hash,
        "cases": {
            "retrieval": len(corpus.retrieval_cases),
            "ocr": len(corpus.ocr_cases),
            "parsing": len(corpus.parsing_cases),
            "visual": len(corpus.visual_cases),
            "provenance": len(corpus.provenance_cases),
        },
        "asset_gaps": list(corpus.asset_gaps),
    }


def _lexical_rank(case: BenchmarkCase, documents: Mapping[str, Mapping[str, Any]]) -> list[str]:
    query_terms = set(_tokens(case.query))
    return sorted(
        case.relevance,
        key=lambda identifier: len(query_terms & set(_tokens(str(documents[identifier]["text"])))),
        reverse=True,
    )


def _embeddings(result: SpecialistExecutionResult, *, expected: int) -> list[list[float]] | None:
    if not result.succeeded:
        return None
    values = result.output.get("embeddings")
    if not isinstance(values, list) or len(values) != expected:
        return None
    try:
        converted = [[float(value) for value in embedding] for embedding in values]
    except (TypeError, ValueError):
        return None
    return converted if all(embedding for embedding in converted) else None


def _quality_metric_for(category: str) -> str:
    return {"embedding": "ndcg_at_10", "reranking": "ndcg_at_10", "ocr": "character_accuracy"}[category]


def _tokens(value: str) -> list[str]:
    return re.findall(r"[a-z0-9가-힣]+", value.lower())


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        return -1.0
    denominator = sqrt(sum(value * value for value in left)) * sqrt(sum(value * value for value in right))
    return sum(a * b for a, b in zip(left, right)) / denominator if denominator else 0.0


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _result_from_dict(value: Mapping[str, Any]) -> SpecialistBenchmarkResult:
    return SpecialistBenchmarkResult(**dict(value))

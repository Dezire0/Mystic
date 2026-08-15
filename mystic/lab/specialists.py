"""Vendor-neutral, benchmark-gated specialist instrument contracts.

Specialists are deliberately narrow: they retrieve, rank, parse, or extract.  This
module contains no research-policy or general-reasoning interface.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping, Protocol

from mystic.lab.schema import utc_now_iso


class SpecialistRole(StrEnum):
    TEXT_EMBEDDING = "text_embedding"
    VISUAL_EMBEDDING = "visual_embedding"
    TEXT_RERANKING = "text_reranking"
    VISUAL_RERANKING = "visual_reranking"
    OCR = "ocr"
    DOCUMENT_PARSING = "document_parsing"
    PAGE_STRUCTURE = "page_structure"
    TABLE_STRUCTURE = "table_structure"
    CODE_EMBEDDING = "code_embedding"


class SpecialistHealth(StrEnum):
    HEALTHY = "healthy"
    UNVERIFIED = "unverified"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"


class BenchmarkStatus(StrEnum):
    NOT_RUN = "not_run"
    FIXTURE_ONLY = "fixture_only"
    APPROVED = "approved"
    REJECTED = "rejected"


class SpecialistClassification(StrEnum):
    UNCLASSIFIED = "unclassified"
    ESSENTIAL = "essential"
    SUPERIOR = "superior"
    ACCELERATOR = "accelerator"
    REDUNDANT = "redundant"
    REJECTED = "rejected"


class SpecialistFailureType(StrEnum):
    UNAVAILABLE = "unavailable"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    INVALID_OUTPUT = "invalid_output"
    UNSUPPORTED_INPUT = "unsupported_input"
    MODEL_DISABLED = "model_disabled"
    PROVIDER_OFFLINE = "provider_offline"


@dataclass(slots=True)
class SpecialistModel:
    specialist_id: str
    provider: str
    model_id: str
    version: str
    role: str
    modalities: list[str]
    domains: list[str]
    capabilities: list[str]
    languages: list[str]
    max_input: int
    expected_latency_class: str
    expected_cost_class: str
    local_or_remote: str
    free_endpoint_available: bool
    deterministic_or_nondeterministic: str
    trust_level: str
    enabled: bool
    health: str
    benchmark_status: str
    fallback_ids: list[str]
    limitations: list[str]
    license_metadata: dict[str, str]
    last_verified_at: str = ""
    classification: str = SpecialistClassification.UNCLASSIFIED.value
    benchmark_quality: float = 0.0
    reliability: float = 0.0

    def __post_init__(self) -> None:
        if not self.specialist_id or not self.provider or not self.model_id or not self.version:
            raise ValueError("Specialist registry entries require identifier, provider, model ID, and version")
        self.role = SpecialistRole(self.role).value
        self.health = SpecialistHealth(self.health).value
        self.benchmark_status = BenchmarkStatus(self.benchmark_status).value
        self.classification = SpecialistClassification(self.classification).value
        if self.max_input < 0:
            raise ValueError("max_input must be non-negative")
        if not 0.0 <= self.benchmark_quality <= 1.0 or not 0.0 <= self.reliability <= 1.0:
            raise ValueError("Specialist quality and reliability must be between zero and one")

    @property
    def benchmark_approved(self) -> bool:
        return self.benchmark_status == BenchmarkStatus.APPROVED.value and self.classification not in {
            SpecialistClassification.UNCLASSIFIED.value,
            SpecialistClassification.REJECTED.value,
        }

    def safe_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SpecialistTaskRequest:
    task: str
    modality: str = "text"
    language: str = "en"
    domain: str = "general"
    quality_priority: float = 0.8
    latency_priority: float = 0.5
    cost_priority: float = 1.0
    input_units: int = 0

    def __post_init__(self) -> None:
        if self.task not in TASK_ROLE:
            raise ValueError(f"Unsupported specialist task: {self.task}")
        if self.modality not in {"text", "image", "document", "code"}:
            raise ValueError("modality must be text, image, document, or code")
        for name in ("quality_priority", "latency_priority", "cost_priority"):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"{name} must be between zero and one")
        if not isinstance(self.input_units, int) or self.input_units < 0:
            raise ValueError("input_units must be a non-negative integer")


@dataclass(slots=True)
class SpecialistMatch:
    request: SpecialistTaskRequest
    specialist: SpecialistModel | None
    status: str
    reason: str = ""
    considered_ids: list[str] = field(default_factory=list)

    def safe_dict(self) -> dict[str, Any]:
        return {
            "task": self.request.task,
            "modality": self.request.modality,
            "language": self.request.language,
            "domain": self.request.domain,
            "input_units": self.request.input_units,
            "status": self.status,
            "reason": self.reason,
            "specialist": self.specialist.safe_dict() if self.specialist else None,
            "considered_ids": self.considered_ids,
        }


@dataclass(slots=True)
class SpecialistExecutionResult:
    specialist_id: str
    provider: str
    operation: str
    status: str
    output: dict[str, Any] = field(default_factory=dict)
    failure_type: str = ""
    safe_error: str = ""
    latency_ms: float = 0.0
    estimated_cost: float | None = None
    used_fallback: bool = False
    executed_at: str = field(default_factory=utc_now_iso)

    @property
    def succeeded(self) -> bool:
        return self.status == "ok"

    def safe_dict(self) -> dict[str, Any]:
        return asdict(self)


class SpecialistProvider(Protocol):
    """Provider implementations receive a selected model, never an arbitrary model ID."""

    provider_id: str

    def health(self) -> str: ...

    def execute(
        self,
        *,
        model: SpecialistModel,
        operation: str,
        payload: Mapping[str, Any],
    ) -> SpecialistExecutionResult: ...


class NvidiaNIMSpecialistProvider:
    """Configuration-gated NVIDIA NIM adapter.

    Phase 2D.1 intentionally stops before provider-specific inference serializers.
    A configured deployment must still add a reviewed serializer and live benchmark
    before remote execution can be enabled.
    """

    provider_id = "nvidia_nim"

    def __init__(self, *, environment: Mapping[str, str] | None = None) -> None:
        self.environment = environment if environment is not None else os.environ

    def health(self) -> str:
        key = str(self.environment.get("MYSTIC_NVIDIA_NIM_API_KEY", "")).strip()
        base_url = str(self.environment.get("MYSTIC_NVIDIA_NIM_BASE_URL", "")).strip()
        return SpecialistHealth.HEALTHY.value if key and base_url else SpecialistHealth.UNVERIFIED.value

    def execute(
        self,
        *,
        model: SpecialistModel,
        operation: str,
        payload: Mapping[str, Any],
    ) -> SpecialistExecutionResult:
        del payload
        if self.health() != SpecialistHealth.HEALTHY.value:
            return SpecialistExecutionResult(
                specialist_id=model.specialist_id,
                provider=self.provider_id,
                operation=operation,
                status="failed",
                failure_type=SpecialistFailureType.PROVIDER_OFFLINE.value,
                safe_error="NVIDIA NIM is not configured for specialist execution.",
            )
        return SpecialistExecutionResult(
            specialist_id=model.specialist_id,
            provider=self.provider_id,
            operation=operation,
            status="failed",
            failure_type=SpecialistFailureType.MODEL_DISABLED.value,
            safe_error="Remote specialist execution is disabled pending a reviewed serializer and live benchmark.",
        )


class SpecialistModelRegistry:
    def __init__(self, models: list[SpecialistModel] | None = None) -> None:
        self._models: dict[str, SpecialistModel] = {}
        for model in models or default_specialist_models():
            self.register(model)

    def register(self, model: SpecialistModel) -> None:
        if model.specialist_id in self._models:
            raise ValueError(f"Specialist already registered: {model.specialist_id}")
        self._models[model.specialist_id] = model

    def get(self, specialist_id: str) -> SpecialistModel:
        try:
            return self._models[specialist_id]
        except KeyError as exc:
            raise KeyError(f"Unknown specialist: {specialist_id}") from exc

    def list(self, *, role: str = "", enabled: bool | None = None) -> list[SpecialistModel]:
        items = list(self._models.values())
        if role:
            items = [item for item in items if item.role == SpecialistRole(role).value]
        if enabled is not None:
            items = [item for item in items if item.enabled is enabled]
        return sorted(items, key=lambda item: item.specialist_id)

    def update_benchmark(
        self,
        specialist_id: str,
        *,
        benchmark_status: str,
        classification: str,
        benchmark_quality: float,
        reliability: float,
        verified_at: str = "",
    ) -> SpecialistModel:
        model = self.get(specialist_id)
        status = BenchmarkStatus(benchmark_status).value
        kind = SpecialistClassification(classification).value
        if status == BenchmarkStatus.APPROVED.value and kind == SpecialistClassification.UNCLASSIFIED.value:
            raise ValueError("Approved specialists require an evidence-backed classification")
        if status != BenchmarkStatus.APPROVED.value and model.enabled:
            raise ValueError("Only benchmark-approved specialists may be enabled")
        model.benchmark_status = status
        model.classification = kind
        model.benchmark_quality = _bounded_fraction("benchmark_quality", benchmark_quality)
        model.reliability = _bounded_fraction("reliability", reliability)
        model.last_verified_at = verified_at or utc_now_iso()
        return model

    def enable(self, specialist_id: str) -> SpecialistModel:
        model = self.get(specialist_id)
        if not model.benchmark_approved:
            raise ValueError("A specialist cannot be enabled before an approved benchmark classification")
        if model.health != SpecialistHealth.HEALTHY.value:
            raise ValueError("A specialist cannot be enabled while provider health is not healthy")
        model.enabled = True
        return model

    def safe_summary(self) -> dict[str, Any]:
        models = self.list()
        return {
            "specialists": [model.safe_dict() for model in models],
            "count": len(models),
            "enabled_count": sum(item.enabled for item in models),
            "approved_count": sum(item.benchmark_approved for item in models),
        }


TASK_ROLE: dict[str, SpecialistRole] = {
    "retrieve_scientific_evidence": SpecialistRole.TEXT_EMBEDDING,
    "retrieve_research_memory": SpecialistRole.TEXT_EMBEDDING,
    "retrieve_code": SpecialistRole.CODE_EMBEDDING,
    "rerank_evidence": SpecialistRole.TEXT_RERANKING,
    "extract_document_text": SpecialistRole.OCR,
    "parse_document": SpecialistRole.DOCUMENT_PARSING,
    "embed_visual_document": SpecialistRole.VISUAL_EMBEDDING,
    "rerank_visual_evidence": SpecialistRole.VISUAL_RERANKING,
    "detect_page_structure": SpecialistRole.PAGE_STRUCTURE,
    "detect_table_structure": SpecialistRole.TABLE_STRUCTURE,
}


class SpecialistRouter:
    """Matches capability requirements; it deliberately has no parameter-count input."""

    def __init__(self, registry: SpecialistModelRegistry) -> None:
        self.registry = registry

    def match(self, request: SpecialistTaskRequest, *, include_disabled: bool = False) -> SpecialistMatch:
        role = TASK_ROLE[request.task].value
        considered = self.registry.list(role=role)
        eligible = [model for model in considered if self._eligible(model, request, include_disabled=include_disabled)]
        if not eligible:
            return SpecialistMatch(
                request=request,
                specialist=None,
                status="unavailable",
                reason="No benchmark-approved, healthy specialist satisfies the task requirements.",
                considered_ids=[model.specialist_id for model in considered],
            )
        selected = max(eligible, key=lambda model: self._score(model, request))
        return SpecialistMatch(
            request=request,
            specialist=selected,
            status="matched",
            considered_ids=[model.specialist_id for model in eligible],
        )

    @staticmethod
    def _eligible(model: SpecialistModel, request: SpecialistTaskRequest, *, include_disabled: bool) -> bool:
        if request.modality not in model.modalities:
            return False
        if request.language not in model.languages and "*" not in model.languages:
            return False
        if request.domain not in model.domains and "general" not in model.domains and "*" not in model.domains:
            return False
        if model.max_input and request.input_units > model.max_input:
            return False
        if not include_disabled and not model.enabled:
            return False
        return model.health == SpecialistHealth.HEALTHY.value and model.benchmark_approved

    @staticmethod
    def _score(model: SpecialistModel, request: SpecialistTaskRequest) -> float:
        latency = {"low": 1.0, "medium": 0.65, "high": 0.3}.get(model.expected_latency_class, 0.2)
        cost = {"free": 1.0, "low": 0.8, "trial": 0.6, "unknown": 0.3, "high": 0.1}.get(
            model.expected_cost_class,
            0.2,
        )
        return (
            request.quality_priority * model.benchmark_quality
            + request.latency_priority * latency
            + request.cost_priority * cost
            + 0.15 * model.reliability
        )


@dataclass(slots=True)
class SpecialistUsageRecord:
    specialist_id: str
    provider: str
    operation: str
    status: str
    failure_type: str
    latency_ms: float
    estimated_cost: float | None
    input_hash: str
    input_units: int
    used_fallback: bool
    created_at: str = field(default_factory=utc_now_iso)


class SpecialistUsageLedger:
    def __init__(self, root_path: str | Path) -> None:
        self.path = Path(root_path) / "mystic_data" / "specialist_usage" / "usage.jsonl"

    def record(self, record: SpecialistUsageRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(record), ensure_ascii=False, sort_keys=True) + "\n")

    def summary(self, *, specialist_id: str = "") -> dict[str, Any]:
        records = self._read_records()
        if specialist_id:
            records = [item for item in records if item.get("specialist_id") == specialist_id]
        calls = len(records)
        fallback_calls = sum(bool(item.get("used_fallback")) for item in records)
        failures = sum(item.get("status") != "ok" for item in records)
        latencies = [float(item["latency_ms"]) for item in records if isinstance(item.get("latency_ms"), (float, int))]
        return {
            "calls": calls,
            "failures": failures,
            "failure_rate": failures / calls if calls else 0.0,
            "fallback_calls": fallback_calls,
            "fallback_rate": fallback_calls / calls if calls else 0.0,
            "average_latency_ms": sum(latencies) / len(latencies) if latencies else 0.0,
            "recent": records[-10:],
        }

    def _read_records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
        return rows


class SpecialistRuntime:
    def __init__(
        self,
        *,
        registry: SpecialistModelRegistry | None = None,
        providers: Mapping[str, SpecialistProvider] | None = None,
        root_path: str | Path | None = None,
    ) -> None:
        self.registry = registry or SpecialistModelRegistry()
        self.router = SpecialistRouter(self.registry)
        self.providers = dict(providers or {"nvidia_nim": NvidiaNIMSpecialistProvider()})
        self.usage = SpecialistUsageLedger(root_path) if root_path is not None else None
        self.refresh_health()

    def refresh_health(self) -> None:
        for model in self.registry.list():
            provider = self.providers.get(model.provider)
            if provider is not None and not model.enabled:
                model.health = provider.health()

    def execute(
        self,
        request: SpecialistTaskRequest,
        *,
        operation: str,
        payload: Mapping[str, Any],
    ) -> SpecialistExecutionResult:
        match = self.router.match(request)
        if match.specialist is None:
            return SpecialistExecutionResult(
                specialist_id="",
                provider="",
                operation=operation,
                status="failed",
                failure_type=SpecialistFailureType.UNAVAILABLE.value,
                safe_error=match.reason,
            )
        result = self._execute_model(match.specialist, operation=operation, payload=payload)
        if result.succeeded:
            self._record(match.specialist, result, payload=payload)
            return result
        fallback = self._approved_fallback(match.specialist, request)
        if fallback is not None and result.failure_type in {
            SpecialistFailureType.UNAVAILABLE.value,
            SpecialistFailureType.TIMEOUT.value,
            SpecialistFailureType.RATE_LIMITED.value,
            SpecialistFailureType.PROVIDER_OFFLINE.value,
        }:
            fallback_result = self._execute_model(fallback, operation=operation, payload=payload)
            fallback_result.used_fallback = True
            self._record(fallback, fallback_result, payload=payload)
            return fallback_result
        self._record(match.specialist, result, payload=payload)
        return result

    def _execute_model(
        self,
        model: SpecialistModel,
        *,
        operation: str,
        payload: Mapping[str, Any],
    ) -> SpecialistExecutionResult:
        provider = self.providers.get(model.provider)
        if provider is None:
            return SpecialistExecutionResult(
                specialist_id=model.specialist_id,
                provider=model.provider,
                operation=operation,
                status="failed",
                failure_type=SpecialistFailureType.PROVIDER_OFFLINE.value,
                safe_error="No registered provider is available for the selected specialist.",
            )
        started = perf_counter()
        result = provider.execute(model=model, operation=operation, payload=payload)
        result.latency_ms = result.latency_ms or (perf_counter() - started) * 1000
        if result.specialist_id != model.specialist_id or result.provider != model.provider:
            return SpecialistExecutionResult(
                specialist_id=model.specialist_id,
                provider=model.provider,
                operation=operation,
                status="failed",
                failure_type=SpecialistFailureType.INVALID_OUTPUT.value,
                safe_error="Provider returned an execution record for a different specialist.",
                latency_ms=result.latency_ms,
            )
        return result

    def _approved_fallback(
        self,
        model: SpecialistModel,
        request: SpecialistTaskRequest,
    ) -> SpecialistModel | None:
        for fallback_id in model.fallback_ids:
            try:
                fallback = self.registry.get(fallback_id)
            except KeyError:
                continue
            if SpecialistRouter._eligible(fallback, request, include_disabled=False):
                return fallback
        return None

    def _record(
        self,
        model: SpecialistModel,
        result: SpecialistExecutionResult,
        *,
        payload: Mapping[str, Any],
    ) -> None:
        if self.usage is None:
            return
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        self.usage.record(
            SpecialistUsageRecord(
                specialist_id=model.specialist_id,
                provider=model.provider,
                operation=result.operation,
                status=result.status,
                failure_type=result.failure_type,
                latency_ms=result.latency_ms,
                estimated_cost=result.estimated_cost,
                input_hash=hashlib.sha256(encoded).hexdigest(),
                input_units=len(encoded),
                used_fallback=result.used_fallback,
            )
        )


def default_specialist_models() -> list[SpecialistModel]:
    """Candidate metadata only; none is a claim of live availability or quality."""

    common = {
        "provider": "nvidia_nim",
        "version": "catalog-2026-08",
        "domains": ["*"],
        "expected_latency_class": "medium",
        "expected_cost_class": "trial",
        "local_or_remote": "remote",
        "deterministic_or_nondeterministic": "nondeterministic_service",
        "trust_level": "candidate_unverified",
        "enabled": False,
        "health": SpecialistHealth.UNVERIFIED.value,
        "benchmark_status": BenchmarkStatus.NOT_RUN.value,
        "license_metadata": {"source": "NVIDIA Build model catalogue", "verification_required": "true"},
    }
    return [
        SpecialistModel(
            specialist_id="nvidia.nemotron-3-embed-1b",
            model_id="nvidia/nemotron-3-embed-1b",
            role=SpecialistRole.TEXT_EMBEDDING.value,
            modalities=["text"],
            capabilities=["semantic_retrieval", "scientific_retrieval", "research_memory", "code_document_retrieval"],
            languages=["*"],
            max_input=0,
            free_endpoint_available=True,
            fallback_ids=["nvidia.llama-nemotron-embed-1b-v2"],
            limitations=["Input limit and retrieval quality require deployment-specific verification."],
            **common,
        ),
        SpecialistModel(
            specialist_id="nvidia.llama-nemotron-embed-1b-v2",
            model_id="nvidia/llama-nemotron-embed-1b-v2",
            role=SpecialistRole.TEXT_EMBEDDING.value,
            modalities=["text"],
            capabilities=["multilingual_retrieval", "cross_lingual_retrieval", "long_document_qa"],
            languages=["*"],
            max_input=0,
            free_endpoint_available=False,
            fallback_ids=["nvidia.nv-embedqa-e5-v5"],
            limitations=["Candidate only; benchmark against the primary embedding model."],
            **common,
        ),
        SpecialistModel(
            specialist_id="nvidia.nv-embedqa-e5-v5",
            model_id="nvidia/nv-embedqa-e5-v5",
            role=SpecialistRole.TEXT_EMBEDDING.value,
            modalities=["text"],
            capabilities=["english_qa_retrieval"],
            languages=["en"],
            max_input=0,
            free_endpoint_available=False,
            fallback_ids=[],
            limitations=["Secondary English QA comparison candidate; disabled by default."],
            **common,
        ),
        SpecialistModel(
            specialist_id="nvidia.llama-nemotron-rerank-1b-v2",
            model_id="nvidia/llama-nemotron-rerank-1b-v2",
            role=SpecialistRole.TEXT_RERANKING.value,
            modalities=["text"],
            capabilities=["evidence_reranking", "multilingual_qa_reranking"],
            languages=["*"],
            max_input=8192,
            free_endpoint_available=True,
            fallback_ids=[],
            limitations=["Cross-encoder inputs must be chunked within the deployed context limit."],
            **common,
        ),
        SpecialistModel(
            specialist_id="nvidia.nemotron-ocr-v2",
            model_id="nvidia/nemotron-ocr-v2",
            role=SpecialistRole.OCR.value,
            modalities=["image", "document"],
            capabilities=["multilingual_ocr", "complex_layout_extraction", "figure_text"],
            languages=["*"],
            max_input=0,
            free_endpoint_available=True,
            fallback_ids=[],
            limitations=["OCR output is an observation and requires source/page provenance before use."],
            **common,
        ),
        SpecialistModel(
            specialist_id="nvidia.nemotron-parse",
            model_id="nvidia/nemotron-parse",
            role=SpecialistRole.DOCUMENT_PARSING.value,
            modalities=["image", "document"],
            capabilities=["document_text", "headings", "tables", "regions", "reading_order"],
            languages=["en"],
            max_input=0,
            free_endpoint_available=False,
            fallback_ids=[],
            limitations=["Language and structured output quality require document-family benchmarks."],
            **common,
        ),
        SpecialistModel(
            specialist_id="nvidia.llama-nemotron-embed-vl-1b-v2",
            model_id="nvidia/llama-nemotron-embed-vl-1b-v2",
            role=SpecialistRole.VISUAL_EMBEDDING.value,
            modalities=["image", "document"],
            capabilities=["multimodal_document_retrieval", "page_image_retrieval"],
            languages=["*"],
            max_input=0,
            free_endpoint_available=False,
            fallback_ids=[],
            limitations=["Use only when clean text extraction loses relevant layout."],
            **common,
        ),
        SpecialistModel(
            specialist_id="nvidia.llama-nemotron-rerank-vl-1b-v2",
            model_id="nvidia/llama-nemotron-rerank-vl-1b-v2",
            role=SpecialistRole.VISUAL_RERANKING.value,
            modalities=["image", "document"],
            capabilities=["visual_page_reranking", "table_chart_reranking"],
            languages=["*"],
            max_input=0,
            free_endpoint_available=False,
            fallback_ids=[],
            limitations=["Use after visual candidate retrieval, not for ordinary text."],
            **common,
        ),
        SpecialistModel(
            specialist_id="nvidia.nemotron-page-elements-v3",
            model_id="nvidia/nemotron-page-elements-v3",
            role=SpecialistRole.PAGE_STRUCTURE.value,
            modalities=["image", "document"],
            capabilities=["page_regions", "titles", "charts", "tables"],
            languages=["*"],
            max_input=0,
            free_endpoint_available=False,
            fallback_ids=[],
            limitations=["Secondary candidate; invoke only when structure improves parsing."],
            **common,
        ),
        SpecialistModel(
            specialist_id="nvidia.nemotron-table-structure-v1",
            model_id="nvidia/nemotron-table-structure-v1",
            role=SpecialistRole.TABLE_STRUCTURE.value,
            modalities=["image", "document"],
            capabilities=["table_structure", "cell_relationships"],
            languages=["*"],
            max_input=0,
            free_endpoint_available=False,
            fallback_ids=[],
            limitations=["Secondary candidate; benchmark table fidelity before enabling."],
            **common,
        ),
        SpecialistModel(
            specialist_id="nvidia.nv-embedcode-7b-v1",
            model_id="nvidia/nv-embedcode-7b-v1",
            role=SpecialistRole.CODE_EMBEDDING.value,
            modalities=["code"],
            capabilities=["code_retrieval", "scientific_software_lookup"],
            languages=["*"],
            max_input=0,
            free_endpoint_available=False,
            fallback_ids=[],
            limitations=["Optional code candidate; remains disabled unless it materially improves retrieval."],
            **common,
        ),
    ]


def _bounded_fraction(name: str, value: float) -> float:
    if not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
        raise ValueError(f"{name} must be between zero and one")
    return float(value)

"""Vendor-neutral, benchmark-gated specialist instrument contracts.

Specialists are deliberately narrow: they retrieve, rank, parse, or extract.  This
module contains no research-policy or general-reasoning interface.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
import base64
import hashlib
import json
import os
from pathlib import Path
import re
from time import perf_counter
from typing import Any, Callable, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

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
    """Narrow, opt-in HTTP adapter for approved NVIDIA NIM capabilities.

    The adapter intentionally accepts only registry-selected model/operation pairs.
    It never exposes a generic URL, request body, or model invocation surface to
    MCP.  A deployment has to opt in with ``MYSTIC_NVIDIA_NIM_EXECUTION_ENABLED``;
    credentials remain in the server process and are redacted from result records.
    """

    provider_id = "nvidia_nim"
    serializer_version = "phase2d2-nim-v1"
    _ROLE_ENDPOINT_VARIABLE = {
        SpecialistRole.TEXT_EMBEDDING.value: "MYSTIC_NVIDIA_NIM_EMBED_BASE_URL",
        SpecialistRole.VISUAL_EMBEDDING.value: "MYSTIC_NVIDIA_NIM_EMBED_BASE_URL",
        SpecialistRole.TEXT_RERANKING.value: "MYSTIC_NVIDIA_NIM_RERANK_BASE_URL",
        SpecialistRole.VISUAL_RERANKING.value: "MYSTIC_NVIDIA_NIM_RERANK_BASE_URL",
        SpecialistRole.OCR.value: "MYSTIC_NVIDIA_NIM_OCR_BASE_URL",
    }
    _WAVE_1_MODEL_OPERATIONS = {
        "nvidia.nemotron-3-embed-1b": ("nvidia/nemotron-3-embed-1b", "embed"),
        "nvidia.llama-nemotron-rerank-1b-v2": ("nvidia/llama-nemotron-rerank-1b-v2", "rerank"),
        "nvidia.nemotron-ocr-v2": ("nvidia/nemotron-ocr-v2", "ocr"),
    }
    _DEFAULT_ALLOWED_HOSTS = {
        "integrate.api.nvidia.com",
        "ai.api.nvidia.com",
        "localhost",
        "127.0.0.1",
        "::1",
    }
    _MAX_TEXT_CHARS = 120_000
    _MAX_BATCH_ITEMS = 50
    _MAX_IMAGE_BYTES = 8 * 1024 * 1024

    def __init__(
        self,
        *,
        environment: Mapping[str, str] | None = None,
        post_json: Callable[[str, dict[str, str], bytes, float], tuple[int, Mapping[str, Any]]] | None = None,
    ) -> None:
        self.environment = environment if environment is not None else os.environ
        self._post_json = post_json or self._urllib_post_json

    def health(self) -> str:
        """Return configuration readiness without making a probe request."""
        if not _truthy(self.environment.get("MYSTIC_NVIDIA_NIM_EXECUTION_ENABLED", "")):
            return SpecialistHealth.UNVERIFIED.value
        return SpecialistHealth.HEALTHY.value if any(self._configured_role(role) for role in self._ROLE_ENDPOINT_VARIABLE) else SpecialistHealth.UNVERIFIED.value

    def health_for(self, model: SpecialistModel) -> str:
        if not _truthy(self.environment.get("MYSTIC_NVIDIA_NIM_EXECUTION_ENABLED", "")):
            return SpecialistHealth.UNVERIFIED.value
        if model.specialist_id not in self._WAVE_1_MODEL_OPERATIONS:
            return SpecialistHealth.UNVERIFIED.value
        return SpecialistHealth.HEALTHY.value if self._configured_role(model.role) else SpecialistHealth.UNVERIFIED.value

    def safe_configuration(self) -> dict[str, Any]:
        endpoints: dict[str, str] = {}
        for role in sorted(self._ROLE_ENDPOINT_VARIABLE):
            base_url = self._base_url_for_role(role)
            if base_url:
                endpoints[role] = str(urlparse(base_url).hostname or "")
        credential_present = bool(str(self.environment.get("MYSTIC_NVIDIA_NIM_API_KEY", "")).strip())
        endpoint_configured = bool(endpoints)
        wave_1_roles = (
            SpecialistRole.TEXT_EMBEDDING.value,
            SpecialistRole.TEXT_RERANKING.value,
            SpecialistRole.OCR.value,
        )
        return {
            "provider": self.provider_id,
            "serializer_version": self.serializer_version,
            "execution_enabled": _truthy(self.environment.get("MYSTIC_NVIDIA_NIM_EXECUTION_ENABLED", "")),
            "nim_configured": all(self._configured_role(role) for role in wave_1_roles),
            "credential_present": credential_present,
            "endpoint_configured": endpoint_configured,
            "api_key_configured": credential_present,
            "endpoint_hosts": endpoints,
            "selected_models": {
                "embedding": self._WAVE_1_MODEL_OPERATIONS["nvidia.nemotron-3-embed-1b"][0],
                "reranking": self._WAVE_1_MODEL_OPERATIONS["nvidia.llama-nemotron-rerank-1b-v2"][0],
                "ocr": self._WAVE_1_MODEL_OPERATIONS["nvidia.nemotron-ocr-v2"][0],
            },
            "timeout_seconds": self._timeout_seconds(),
            "retry_policy": "none",
            "allowed_host_policy": "NVIDIA API, loopback, or explicitly configured MYSTIC_NVIDIA_NIM_ALLOWED_HOSTS",
        }

    def execute(
        self,
        *,
        model: SpecialistModel,
        operation: str,
        payload: Mapping[str, Any],
    ) -> SpecialistExecutionResult:
        expected = self._WAVE_1_MODEL_OPERATIONS.get(model.specialist_id)
        if expected != (model.model_id, operation):
            return self._failure(
                model,
                operation,
                SpecialistFailureType.UNSUPPORTED_INPUT,
                "NVIDIA NIM provider accepts only fixed Phase 2D.2 Wave 1 specialist operations.",
            )
        if not _truthy(self.environment.get("MYSTIC_NVIDIA_NIM_EXECUTION_ENABLED", "")):
            return self._failure(
                model,
                operation,
                SpecialistFailureType.MODEL_DISABLED,
                "NVIDIA NIM execution is disabled by server configuration.",
            )
        try:
            endpoint, body = self._request_for(model=model, operation=operation, payload=payload)
        except ValueError as exc:
            return self._failure(model, operation, SpecialistFailureType.UNSUPPORTED_INPUT, str(exc))
        if endpoint is None:
            return self._failure(
                model,
                operation,
                SpecialistFailureType.PROVIDER_OFFLINE,
                "No approved NVIDIA NIM endpoint is configured for this specialist role.",
            )
        endpoint_host = (urlparse(endpoint).hostname or "").lower()
        if endpoint_host not in {"localhost", "127.0.0.1", "::1"} and not str(
            self.environment.get("MYSTIC_NVIDIA_NIM_API_KEY", "")
        ).strip():
            return self._failure(
                model,
                operation,
                SpecialistFailureType.PROVIDER_OFFLINE,
                "NVIDIA NIM remote endpoint requires a server-side API key.",
            )
        headers = {"accept": "application/json", "content-type": "application/json"}
        api_key = str(self.environment.get("MYSTIC_NVIDIA_NIM_API_KEY", "")).strip()
        if api_key:
            headers["authorization"] = f"Bearer {api_key}"
        try:
            status, response = self._post_json(
                endpoint,
                headers,
                json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
                self._timeout_seconds(),
            )
        except TimeoutError:
            return self._failure(model, operation, SpecialistFailureType.TIMEOUT, "NVIDIA NIM request timed out.")
        except HTTPError as exc:
            return self._http_failure(model, operation, exc.code)
        except URLError:
            return self._failure(model, operation, SpecialistFailureType.PROVIDER_OFFLINE, "NVIDIA NIM endpoint is unavailable.")
        except OSError:
            return self._failure(model, operation, SpecialistFailureType.PROVIDER_OFFLINE, "NVIDIA NIM transport failed.")
        except (TypeError, ValueError, json.JSONDecodeError):
            return self._failure(model, operation, SpecialistFailureType.INVALID_OUTPUT, "NVIDIA NIM returned an invalid response.")
        if status < 200 or status >= 300:
            return self._http_failure(model, operation, status)
        try:
            output = self._normalize_response(model=model, operation=operation, response=response)
        except (KeyError, TypeError, ValueError):
            return self._failure(model, operation, SpecialistFailureType.INVALID_OUTPUT, "NVIDIA NIM response did not match the expected specialist contract.")
        return SpecialistExecutionResult(
            specialist_id=model.specialist_id,
            provider=self.provider_id,
            operation=operation,
            status="ok",
            output=output,
            estimated_cost=None,
        )

    def _request_for(
        self,
        *,
        model: SpecialistModel,
        operation: str,
        payload: Mapping[str, Any],
    ) -> tuple[str | None, dict[str, Any]]:
        base_url = self._base_url_for_role(model.role)
        if not base_url:
            return None, {}
        if model.role == SpecialistRole.TEXT_EMBEDDING.value and operation == "embed":
            texts = _text_batch(payload)
            input_type = str(payload.get("input_type", "passage"))
            if input_type not in {"query", "passage"}:
                raise ValueError("Embedding input_type must be query or passage.")
            return _nim_endpoint(base_url, "v1/embeddings"), {
                "model": model.model_id,
                "input": texts if len(texts) > 1 else texts[0],
                "input_type": input_type,
                "encoding_format": "float",
                "truncate": "NONE",
            }
        if model.role == SpecialistRole.TEXT_RERANKING.value and operation == "rerank":
            query = _bounded_text(payload.get("query"), field="query")
            passages_value = payload.get("passages")
            if not isinstance(passages_value, list) or not passages_value or len(passages_value) > self._MAX_BATCH_ITEMS:
                raise ValueError("Reranking requires 1-50 text passages.")
            passages = [_bounded_text(value, field="passage") for value in passages_value]
            if len(query) + sum(len(value) for value in passages) > self._MAX_TEXT_CHARS:
                raise ValueError("Reranking request exceeds the approved text budget.")
            return _nim_endpoint(base_url, "v1/ranking"), {
                "model": model.model_id,
                "query": {"text": query},
                "passages": [{"text": passage} for passage in passages],
                "truncate": "END",
            }
        if model.role == SpecialistRole.OCR.value and operation == "ocr":
            image_urls = _image_batch(payload, max_bytes=self._MAX_IMAGE_BYTES, max_items=self._MAX_BATCH_ITEMS)
            merge_level = str(payload.get("merge_level", "paragraph"))
            if merge_level not in {"word", "sentence", "paragraph"}:
                raise ValueError("OCR merge_level must be word, sentence, or paragraph.")
            return _nim_endpoint(base_url, "v1/ocr"), {
                "input": [{"type": "image_url", "url": item} for item in image_urls],
                "merge_levels": [merge_level] * len(image_urls),
            }
        raise ValueError("The selected NVIDIA specialist does not support this operation.")

    def _normalize_response(
        self,
        *,
        model: SpecialistModel,
        operation: str,
        response: Mapping[str, Any],
    ) -> dict[str, Any]:
        if model.role == SpecialistRole.TEXT_EMBEDDING.value and operation == "embed":
            rows = response.get("data")
            if not isinstance(rows, list) or not rows:
                raise ValueError("Missing embedding data")
            ordered = sorted(rows, key=lambda row: int(row.get("index", 0)))
            embeddings = [
                [float(value) for value in row["embedding"]]
                for row in ordered
                if isinstance(row, Mapping) and isinstance(row.get("embedding"), list) and row["embedding"]
            ]
            if len(embeddings) != len(rows):
                raise ValueError("Invalid embedding vector")
            return {"embedding": embeddings[0], "embeddings": embeddings, "usage": _safe_usage(response.get("usage"))}
        if model.role == SpecialistRole.TEXT_RERANKING.value and operation == "rerank":
            rows = response.get("data", response.get("rankings"))
            if not isinstance(rows, list):
                raise ValueError("Missing ranking data")
            scores_by_index: dict[int, float] = {}
            for row in rows:
                if not isinstance(row, Mapping):
                    raise ValueError("Invalid ranking row")
                index = int(row["index"])
                score = row.get("logit", row.get("score"))
                if not isinstance(score, (int, float)):
                    raise ValueError("Invalid ranking score")
                scores_by_index[index] = float(score)
            if sorted(scores_by_index) != list(range(len(scores_by_index))):
                raise ValueError("Ranking response omitted or duplicated candidate indices")
            return {"scores": [scores_by_index[index] for index in range(len(scores_by_index))], "usage": _safe_usage(response.get("usage"))}
        if model.role == SpecialistRole.OCR.value and operation == "ocr":
            rows = response.get("data")
            if not isinstance(rows, list):
                raise ValueError("Missing OCR data")
            pages: list[dict[str, Any]] = []
            for item in rows:
                if not isinstance(item, Mapping):
                    raise ValueError("Invalid OCR page")
                detections: list[dict[str, Any]] = []
                for detection in item.get("text_detections", []):
                    if not isinstance(detection, Mapping):
                        continue
                    prediction = detection.get("text_prediction", {})
                    if not isinstance(prediction, Mapping) or not isinstance(prediction.get("text"), str):
                        continue
                    confidence = prediction.get("confidence")
                    box = detection.get("bounding_box", {})
                    detections.append(
                        {
                            "text": prediction["text"],
                            "confidence": float(confidence) if isinstance(confidence, (int, float)) else None,
                            "bounding_box": box if isinstance(box, Mapping) else {},
                        }
                    )
                pages.append({"index": int(item.get("index", len(pages))), "text": "\n".join(row["text"] for row in detections), "detections": detections})
            if not pages:
                raise ValueError("OCR response contained no page records")
            return {"text": pages[0]["text"], "pages": pages, "usage": _safe_usage(response.get("usage"))}
        raise ValueError("Unsupported response contract")

    def _base_url_for_role(self, role: str) -> str:
        variable = self._ROLE_ENDPOINT_VARIABLE.get(role)
        raw = str(self.environment.get(variable or "", "") or self.environment.get("MYSTIC_NVIDIA_NIM_BASE_URL", "")).strip()
        if not raw:
            return ""
        parsed = urlparse(raw)
        allowed_hosts = self._allowed_hosts()
        host = (parsed.hostname or "").lower()
        if parsed.scheme not in {"https", "http"} or not host or parsed.username or parsed.password:
            return ""
        if parsed.scheme == "http" and host not in {"localhost", "127.0.0.1", "::1"}:
            return ""
        if host not in allowed_hosts:
            return ""
        return raw.rstrip("/")

    def _allowed_hosts(self) -> set[str]:
        configured = {
            item.strip().lower()
            for item in str(self.environment.get("MYSTIC_NVIDIA_NIM_ALLOWED_HOSTS", "")).split(",")
            if item.strip()
        }
        return self._DEFAULT_ALLOWED_HOSTS | configured

    def _configured_role(self, role: str) -> bool:
        base_url = self._base_url_for_role(role)
        if not base_url:
            return False
        host = (urlparse(base_url).hostname or "").lower()
        if host in {"localhost", "127.0.0.1", "::1"}:
            return True
        return bool(str(self.environment.get("MYSTIC_NVIDIA_NIM_API_KEY", "")).strip())

    def _timeout_seconds(self) -> float:
        raw = str(self.environment.get("MYSTIC_NVIDIA_NIM_TIMEOUT_SECONDS", "30")).strip()
        try:
            value = float(raw)
        except ValueError:
            return 30.0
        return min(max(value, 1.0), 60.0)

    def _failure(
        self,
        model: SpecialistModel,
        operation: str,
        failure_type: SpecialistFailureType,
        safe_error: str,
    ) -> SpecialistExecutionResult:
        return SpecialistExecutionResult(
            specialist_id=model.specialist_id,
            provider=self.provider_id,
            operation=operation,
            status="failed",
            failure_type=failure_type.value,
            safe_error=safe_error,
        )

    def _http_failure(self, model: SpecialistModel, operation: str, status: int) -> SpecialistExecutionResult:
        if status == 429:
            kind = SpecialistFailureType.RATE_LIMITED
            message = "NVIDIA NIM request was rate limited."
        elif status in {408, 504}:
            kind = SpecialistFailureType.TIMEOUT
            message = "NVIDIA NIM request timed out."
        elif status in {401, 403, 404, 502, 503} or status >= 500:
            kind = SpecialistFailureType.PROVIDER_OFFLINE
            message = "NVIDIA NIM endpoint rejected or could not serve the request."
        else:
            kind = SpecialistFailureType.INVALID_OUTPUT
            message = "NVIDIA NIM rejected the bounded specialist request."
        return self._failure(model, operation, kind, message)

    @staticmethod
    def _urllib_post_json(url: str, headers: dict[str, str], body: bytes, timeout: float) -> tuple[int, Mapping[str, Any]]:
        request = Request(url, data=body, headers=headers, method="POST")
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - endpoint is allowlisted from server configuration.
            payload = response.read(16 * 1024 * 1024 + 1)
            if len(payload) > 16 * 1024 * 1024:
                raise ValueError("NVIDIA NIM response exceeded the approved size limit")
            decoded = json.loads(payload.decode("utf-8"))
            if not isinstance(decoded, Mapping):
                raise ValueError("NVIDIA NIM response must be a JSON object")
            return int(response.status), decoded


class LocalOpenAICompatibleEmbeddingProvider:
    """Opt-in adapter for an explicitly registered loopback embedding server.

    This is intentionally narrower than a general OpenAI-compatible client: it
    accepts only an embedding operation for a model ID supplied at application
    wiring time, and only connects to a loopback origin.  It is useful for a
    locally hosted model (for example, a development inference server) without
    turning the Specialist API into arbitrary model execution.
    """

    provider_id = "local_openai_compatible"
    serializer_version = "phase2d2-local-openai-embedding-v1"
    _LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}

    def __init__(
        self,
        *,
        allowed_model_ids: set[str] | frozenset[str] | None = None,
        environment: Mapping[str, str] | None = None,
        post_json: Callable[[str, dict[str, str], bytes, float], tuple[int, Mapping[str, Any]]] | None = None,
    ) -> None:
        self.allowed_model_ids = frozenset(str(value) for value in (allowed_model_ids or set()) if str(value).strip())
        self.environment = environment if environment is not None else os.environ
        self._post_json = post_json or NvidiaNIMSpecialistProvider._urllib_post_json

    def health(self) -> str:
        if not _truthy(self.environment.get("MYSTIC_LOCAL_OPENAI_COMPATIBLE_EXECUTION_ENABLED", "")):
            return SpecialistHealth.UNVERIFIED.value
        return SpecialistHealth.HEALTHY.value if self.allowed_model_ids and self._base_url() else SpecialistHealth.UNVERIFIED.value

    def health_for(self, model: SpecialistModel) -> str:
        if model.provider != self.provider_id or model.role != SpecialistRole.TEXT_EMBEDDING.value:
            return SpecialistHealth.UNVERIFIED.value
        if model.model_id not in self.allowed_model_ids:
            return SpecialistHealth.UNVERIFIED.value
        return self.health()

    def safe_configuration(self) -> dict[str, Any]:
        base_url = self._base_url()
        return {
            "provider": self.provider_id,
            "serializer_version": self.serializer_version,
            "execution_enabled": _truthy(self.environment.get("MYSTIC_LOCAL_OPENAI_COMPATIBLE_EXECUTION_ENABLED", "")),
            "api_key_configured": bool(str(self.environment.get("MYSTIC_LOCAL_OPENAI_COMPATIBLE_API_KEY", "")).strip()),
            "endpoint_host": str(urlparse(base_url).hostname or "") if base_url else "",
            "allowed_model_count": len(self.allowed_model_ids),
            "timeout_seconds": self._timeout_seconds(),
            "endpoint_policy": "loopback-only fixed /v1/embeddings endpoint",
        }

    def execute(
        self,
        *,
        model: SpecialistModel,
        operation: str,
        payload: Mapping[str, Any],
    ) -> SpecialistExecutionResult:
        if (
            model.provider != self.provider_id
            or model.role != SpecialistRole.TEXT_EMBEDDING.value
            or operation != "embed"
            or model.model_id not in self.allowed_model_ids
        ):
            return self._failure(model, operation, SpecialistFailureType.UNSUPPORTED_INPUT, "Local provider accepts only explicitly registered text embedding models.")
        if not _truthy(self.environment.get("MYSTIC_LOCAL_OPENAI_COMPATIBLE_EXECUTION_ENABLED", "")):
            return self._failure(model, operation, SpecialistFailureType.MODEL_DISABLED, "Local embedding execution is disabled by server configuration.")
        base_url = self._base_url()
        if not base_url:
            return self._failure(model, operation, SpecialistFailureType.PROVIDER_OFFLINE, "No approved loopback local embedding endpoint is configured.")
        try:
            texts = _text_batch(payload)
        except ValueError as exc:
            return self._failure(model, operation, SpecialistFailureType.UNSUPPORTED_INPUT, str(exc))
        headers = {"accept": "application/json", "content-type": "application/json"}
        api_key = str(self.environment.get("MYSTIC_LOCAL_OPENAI_COMPATIBLE_API_KEY", "")).strip()
        if api_key:
            headers["authorization"] = f"Bearer {api_key}"
        body = {
            "model": model.model_id,
            "input": texts if len(texts) > 1 else texts[0],
            "encoding_format": "float",
        }
        try:
            status, response = self._post_json(
                _nim_endpoint(base_url, "v1/embeddings"),
                headers,
                json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
                self._timeout_seconds(),
            )
        except TimeoutError:
            return self._failure(model, operation, SpecialistFailureType.TIMEOUT, "Local embedding request timed out.")
        except HTTPError as exc:
            return self._http_failure(model, operation, exc.code)
        except URLError:
            return self._failure(model, operation, SpecialistFailureType.PROVIDER_OFFLINE, "Local embedding endpoint is unavailable.")
        except OSError:
            return self._failure(model, operation, SpecialistFailureType.PROVIDER_OFFLINE, "Local embedding transport failed.")
        except (TypeError, ValueError, json.JSONDecodeError):
            return self._failure(model, operation, SpecialistFailureType.INVALID_OUTPUT, "Local embedding endpoint returned an invalid response.")
        if status < 200 or status >= 300:
            return self._http_failure(model, operation, status)
        try:
            rows = response.get("data")
            if not isinstance(rows, list) or not rows:
                raise ValueError("Missing embedding data")
            ordered = sorted(rows, key=lambda row: int(row.get("index", 0)))
            embeddings = [
                [float(value) for value in row["embedding"]]
                for row in ordered
                if isinstance(row, Mapping) and isinstance(row.get("embedding"), list) and row["embedding"]
            ]
            if len(embeddings) != len(rows):
                raise ValueError("Invalid embedding vector")
        except (KeyError, TypeError, ValueError):
            return self._failure(model, operation, SpecialistFailureType.INVALID_OUTPUT, "Local embedding response did not match the expected contract.")
        return SpecialistExecutionResult(
            specialist_id=model.specialist_id,
            provider=self.provider_id,
            operation=operation,
            status="ok",
            output={"embedding": embeddings[0], "embeddings": embeddings, "usage": _safe_usage(response.get("usage"))},
            estimated_cost=None,
        )

    def _base_url(self) -> str:
        raw = str(self.environment.get("MYSTIC_LOCAL_OPENAI_COMPATIBLE_EMBED_BASE_URL", "")).strip()
        parsed = urlparse(raw)
        host = (parsed.hostname or "").lower()
        if parsed.scheme not in {"https", "http"} or host not in self._LOOPBACK_HOSTS or parsed.username or parsed.password:
            return ""
        return raw.rstrip("/")

    def _timeout_seconds(self) -> float:
        raw = str(self.environment.get("MYSTIC_LOCAL_OPENAI_COMPATIBLE_TIMEOUT_SECONDS", "30")).strip()
        try:
            value = float(raw)
        except ValueError:
            return 30.0
        return min(max(value, 1.0), 60.0)

    def _failure(
        self,
        model: SpecialistModel,
        operation: str,
        failure_type: SpecialistFailureType,
        safe_error: str,
    ) -> SpecialistExecutionResult:
        return SpecialistExecutionResult(
            specialist_id=model.specialist_id,
            provider=self.provider_id,
            operation=operation,
            status="failed",
            failure_type=failure_type.value,
            safe_error=safe_error,
        )

    def _http_failure(self, model: SpecialistModel, operation: str, status: int) -> SpecialistExecutionResult:
        if status == 429:
            kind = SpecialistFailureType.RATE_LIMITED
            message = "Local embedding request was rate limited."
        elif status in {408, 504}:
            kind = SpecialistFailureType.TIMEOUT
            message = "Local embedding request timed out."
        elif status in {401, 403, 404, 502, 503} or status >= 500:
            kind = SpecialistFailureType.PROVIDER_OFFLINE
            message = "Local embedding endpoint rejected or could not serve the request."
        else:
            kind = SpecialistFailureType.INVALID_OUTPUT
            message = "Local embedding endpoint rejected the bounded request."
        return self._failure(model, operation, kind, message)


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


class SpecialistApprovalStore:
    """Persists only evidence-backed activation metadata, never provider secrets."""

    def __init__(self, root_path: str | Path) -> None:
        self.path = Path(root_path) / "mystic_data" / "specialist_benchmarks" / "approvals.json"

    def record(
        self,
        *,
        model: SpecialistModel,
        benchmark_id: str,
        benchmark_result_hash: str,
        quality_metric: str,
    ) -> dict[str, Any]:
        if not model.benchmark_approved or not model.enabled:
            raise ValueError("Only enabled, benchmark-approved specialists can be persisted as active")
        record = {
            "specialist_id": model.specialist_id,
            "benchmark_id": _safe_registry_identifier(benchmark_id),
            "benchmark_result_hash": _safe_registry_hash(benchmark_result_hash),
            "benchmark_status": model.benchmark_status,
            "classification": model.classification,
            "benchmark_quality": model.benchmark_quality,
            "reliability": model.reliability,
            "quality_metric": _safe_registry_identifier(quality_metric),
            "verified_at": model.last_verified_at,
            "recorded_at": utc_now_iso(),
        }
        records = [item for item in self._read() if item.get("specialist_id") != model.specialist_id]
        records.append(record)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(records, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(self.path)
        return record

    def apply(self, registry: SpecialistModelRegistry) -> list[str]:
        applied: list[str] = []
        for record in self._read():
            try:
                specialist_id = _safe_registry_identifier(str(record["specialist_id"]))
                benchmark_id = _safe_registry_identifier(str(record["benchmark_id"]))
                expected_hash = _safe_registry_hash(str(record["benchmark_result_hash"]))
                result_path = self.path.parent / f"{benchmark_id}.json"
                if not result_path.exists() or hashlib.sha256(result_path.read_bytes()).hexdigest() != expected_hash:
                    continue
                result = json.loads(result_path.read_text(encoding="utf-8"))
                if (
                    not isinstance(result, Mapping)
                    or result.get("specialist_id") != specialist_id
                    or result.get("execution_mode") != "live"
                    or not result.get("corpus_hash")
                    or not result.get("baseline_id")
                    or result.get("provenance_preserved") is not True
                ):
                    continue
                model = registry.update_benchmark(
                    specialist_id,
                    benchmark_status=BenchmarkStatus.APPROVED.value,
                    classification=str(record["classification"]),
                    benchmark_quality=float(record["benchmark_quality"]),
                    reliability=float(record["reliability"]),
                    verified_at=str(record["verified_at"]),
                )
                if model.health == SpecialistHealth.HEALTHY.value:
                    registry.enable(specialist_id)
                    applied.append(specialist_id)
            except (KeyError, TypeError, ValueError):
                continue
        return applied

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return [dict(item) for item in payload if isinstance(item, Mapping)] if isinstance(payload, list) else []


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
        self.approvals = SpecialistApprovalStore(root_path) if root_path is not None else None
        if self.approvals is not None:
            self.approvals.apply(self.registry)

    def refresh_health(self) -> None:
        for model in self.registry.list():
            provider = self.providers.get(model.provider)
            if provider is not None and not model.enabled:
                health_for = getattr(provider, "health_for", None)
                model.health = health_for(model) if callable(health_for) else provider.health()

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


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _nim_endpoint(base_url: str, path: str) -> str:
    """Join a configured NIM origin to a fixed capability endpoint.

    Operators configure an origin (for example ``https://integrate.api.nvidia.com``
    or ``http://127.0.0.1:8000``), not a model-controlled arbitrary path.
    """
    parsed = urlparse(base_url)
    prefix = parsed.path.rstrip("/")
    if prefix.endswith("/v1"):
        prefix = prefix[:-3]
    return f"{parsed.scheme}://{parsed.netloc}{prefix}/{path.lstrip('/')}"


def _bounded_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty text string.")
    if len(value) > NvidiaNIMSpecialistProvider._MAX_TEXT_CHARS:
        raise ValueError(f"{field} exceeds the approved text budget.")
    return value


def _text_batch(payload: Mapping[str, Any]) -> list[str]:
    if "texts" in payload:
        values = payload.get("texts")
        if not isinstance(values, list) or not values or len(values) > NvidiaNIMSpecialistProvider._MAX_BATCH_ITEMS:
            raise ValueError("Embedding texts must contain 1-50 text strings.")
        texts = [_bounded_text(value, field="text") for value in values]
    else:
        texts = [_bounded_text(payload.get("text"), field="text")]
    if sum(len(value) for value in texts) > NvidiaNIMSpecialistProvider._MAX_TEXT_CHARS:
        raise ValueError("Embedding request exceeds the approved text budget.")
    return texts


def _image_batch(payload: Mapping[str, Any], *, max_bytes: int, max_items: int) -> list[str]:
    values = payload.get("images", [payload.get("image")])
    if not isinstance(values, list) or not values or len(values) > max_items:
        raise ValueError("OCR requires 1-50 PNG or JPEG image data URLs.")
    result: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value.startswith(("data:image/png;base64,", "data:image/jpeg;base64,")):
            raise ValueError("OCR accepts only PNG or JPEG image data URLs.")
        encoded = value.split(",", 1)[1]
        try:
            raw = base64.b64decode(encoded, validate=True)
        except ValueError as exc:
            raise ValueError("OCR image data URL is not valid base64.") from exc
        if not raw or len(raw) > max_bytes:
            raise ValueError("OCR image exceeds the approved byte limit.")
        result.append(value)
    return result


def _safe_usage(value: object) -> dict[str, float]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): float(item) for key, item in value.items() if isinstance(item, (int, float))}


def _safe_registry_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", value):
        raise ValueError("Registry approval identifier contains unsupported characters")
    return value


def _safe_registry_hash(value: str) -> str:
    if not re.fullmatch(r"[a-f0-9]{64}", value):
        raise ValueError("Registry approval result hash must be a SHA-256 digest")
    return value

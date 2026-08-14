"""Traceable evidence ingestion and retrieval pipelines for specialist instruments."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from math import sqrt
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

from mystic.lab.schema import utc_now_iso
from mystic.lab.specialists import (
    SpecialistExecutionResult,
    SpecialistFailureType,
    SpecialistModel,
    SpecialistProvider,
    SpecialistRuntime,
    SpecialistTaskRequest,
)


MAX_DOCUMENT_CHARS = 120_000
MAX_PAGES = 100
MAX_CHUNKS = 500
CHUNK_CHARS = 1_200
CHUNK_OVERLAP = 180


@dataclass(slots=True)
class EvidenceProvenanceStep:
    stage: str
    source_id: str
    document_id: str
    location: str
    input_hash: str
    output_hash: str
    specialist_id: str = ""
    provider: str = ""
    model_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=utc_now_iso)


@dataclass(slots=True)
class NormalizedEvidence:
    evidence_id: str
    source_id: str
    source_type: str
    title: str
    location: str
    text: str
    retrieval_score: float | None
    rerank_score: float | None
    extraction_method: str
    specialist_models_used: list[str]
    content_hash: str
    provenance: list[EvidenceProvenanceStep]
    timestamp: str
    warnings: list[str]
    document_id: str

    def safe_dict(self, *, include_text: bool = True) -> dict[str, Any]:
        payload = asdict(self)
        if not include_text:
            payload.pop("text", None)
        return payload


@dataclass(slots=True)
class DocumentIngestRequest:
    source_id: str
    source_type: str
    title: str
    mime_type: str
    content: str
    pages: list[dict[str, Any]] = field(default_factory=list)
    scanned: bool = False
    visually_complex: bool = False
    language: str = "en"
    domain: str = "general"

    def __post_init__(self) -> None:
        for name, value, maximum in (
            ("source_id", self.source_id, 160),
            ("source_type", self.source_type, 80),
            ("title", self.title, 500),
            ("mime_type", self.mime_type, 120),
            ("language", self.language, 24),
            ("domain", self.domain, 80),
        ):
            if not isinstance(value, str) or not value.strip() or len(value) > maximum:
                raise ValueError(f"{name} must be a non-empty string of at most {maximum} characters")
        if not isinstance(self.content, str) or not self.content.strip() or len(self.content) > MAX_DOCUMENT_CHARS:
            raise ValueError(f"content must be a non-empty string of at most {MAX_DOCUMENT_CHARS} characters")
        if len(self.pages) > MAX_PAGES or any(not isinstance(page, dict) for page in self.pages):
            raise ValueError(f"pages must contain at most {MAX_PAGES} objects")


@dataclass(slots=True)
class DocumentRoutingPlan:
    document_id: str
    stages: list[str]
    requires_specialist: bool
    required_tasks: list[str]
    reason: str

    def safe_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DocumentIngestResult:
    status: str
    document_id: str
    routing_plan: DocumentRoutingPlan
    evidence: list[NormalizedEvidence]
    warnings: list[str] = field(default_factory=list)
    failure: SpecialistExecutionResult | None = None

    def safe_dict(self, *, include_text: bool = False) -> dict[str, Any]:
        return {
            "status": self.status,
            "document_id": self.document_id,
            "routing_plan": self.routing_plan.safe_dict(),
            "evidence": [item.safe_dict(include_text=include_text) for item in self.evidence],
            "count": len(self.evidence),
            "warnings": self.warnings,
            "failure": self.failure.safe_dict() if self.failure else None,
        }


class EvidenceStore:
    """Local, bounded evidence index. The original caller-supplied source ID is retained."""

    def __init__(self, root_path: str | Path) -> None:
        self.root = Path(root_path) / "mystic_data" / "specialist_evidence"
        self.document_root = self.root / "documents"
        self.index_root = self.root / "index"
        self.job_link_root = self.root / "job_links"

    def save_document(self, request: DocumentIngestRequest, *, document_id: str, plan: DocumentRoutingPlan) -> None:
        self.document_root.mkdir(parents=True, exist_ok=True)
        # Content is retained locally only because local ingestion must preserve the source.
        payload = {
            "document_id": document_id,
            "source_id": request.source_id,
            "source_type": request.source_type,
            "title": request.title,
            "mime_type": request.mime_type,
            "language": request.language,
            "domain": request.domain,
            "content": request.content,
            "pages": request.pages,
            "content_hash": _sha256(request.content),
            "routing_plan": plan.safe_dict(),
            "stored_at": utc_now_iso(),
        }
        self._write_json(self.document_root / f"{document_id}.json", payload)

    def save_indexed(self, evidence: NormalizedEvidence, embedding: list[float]) -> None:
        self.index_root.mkdir(parents=True, exist_ok=True)
        if not embedding or any(not isinstance(value, (int, float)) for value in embedding):
            raise ValueError("Evidence embedding must be a non-empty numeric vector")
        self._write_json(
            self.index_root / f"{evidence.evidence_id}.json",
            {"evidence": evidence.safe_dict(include_text=True), "embedding": [float(value) for value in embedding]},
        )

    def list_indexed(self, *, limit: int = MAX_CHUNKS) -> list[tuple[NormalizedEvidence, list[float]]]:
        if not self.index_root.exists():
            return []
        rows: list[tuple[NormalizedEvidence, list[float]]] = []
        for path in sorted(self.index_root.glob("*.json"), reverse=True)[:limit]:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                evidence = _evidence_from_dict(payload["evidence"])
                embedding = [float(value) for value in payload["embedding"]]
            except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
                continue
            rows.append((evidence, embedding))
        return rows

    def get_evidence(self, evidence_id: str) -> NormalizedEvidence:
        path = self.index_root / f"{_safe_identifier(evidence_id)}.json"
        if not path.exists():
            raise KeyError(f"Evidence not found: {evidence_id}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        return _evidence_from_dict(payload["evidence"])

    def get_document_summary(self, document_id: str) -> dict[str, Any]:
        path = self.document_root / f"{_safe_identifier(document_id)}.json"
        if not path.exists():
            raise KeyError(f"Document not found: {document_id}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        return {
            "document_id": payload["document_id"],
            "source_id": payload["source_id"],
            "source_type": payload["source_type"],
            "title": payload["title"],
            "mime_type": payload["mime_type"],
            "language": payload["language"],
            "domain": payload["domain"],
            "content_hash": payload["content_hash"],
            "page_count": len(payload.get("pages", [])) or 1,
            "routing_plan": payload["routing_plan"],
            "stored_at": payload["stored_at"],
        }

    def list_evidence(self, *, limit: int = 100) -> list[NormalizedEvidence]:
        if limit < 1 or limit > MAX_CHUNKS:
            raise ValueError(f"limit must be between 1 and {MAX_CHUNKS}")
        return [evidence for evidence, _ in self.list_indexed(limit=limit)]

    def link_job(
        self,
        *,
        campaign_id: str,
        job_id: str,
        evidence: Iterable[NormalizedEvidence],
    ) -> dict[str, Any]:
        items = list(evidence)
        if not items:
            raise ValueError("At least one evidence record is required for a job link")
        self.job_link_root.mkdir(parents=True, exist_ok=True)
        payload = {
            "campaign_id": campaign_id,
            "job_id": job_id,
            "evidence": [
                {
                    "evidence_id": item.evidence_id,
                    "source_id": item.source_id,
                    "document_id": item.document_id,
                    "content_hash": item.content_hash,
                    "provenance_hash": _sha256(_canonical([asdict(step) for step in item.provenance])),
                }
                for item in items
            ],
            "mode": "reference_only",
            "created_at": utc_now_iso(),
        }
        self._write_json(self.job_link_root / f"{_safe_identifier(job_id)}.json", payload)
        return payload

    @staticmethod
    def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(path)


class SpecialistEvidenceService:
    def __init__(self, *, root_path: str | Path, runtime: SpecialistRuntime) -> None:
        self.root_path = Path(root_path)
        self.runtime = runtime
        self.store = EvidenceStore(self.root_path)

    def plan_document(self, request: DocumentIngestRequest) -> DocumentRoutingPlan:
        document_id = _document_id(request)
        mime_type = request.mime_type.lower()
        if request.scanned or mime_type.startswith("image/"):
            return DocumentRoutingPlan(
                document_id=document_id,
                stages=["mime_detection", "ocr", "normalize", "chunk", "embed", "index"],
                requires_specialist=True,
                required_tasks=["extract_document_text"],
                reason="Image-based or scanned input requires OCR before it can become evidence.",
            )
        if request.visually_complex or mime_type == "application/pdf":
            return DocumentRoutingPlan(
                document_id=document_id,
                stages=["mime_detection", "parse", "page_structure", "normalize", "chunk", "embed", "index"],
                requires_specialist=True,
                required_tasks=["parse_document", "detect_page_structure"],
                reason="A visually structured document requires parser/layout validation before text evidence is derived.",
            )
        return DocumentRoutingPlan(
            document_id=document_id,
            stages=["mime_detection", "normalize", "chunk", "embed", "index"],
            requires_specialist=False,
            required_tasks=["retrieve_scientific_evidence"],
            reason="Clean text can be normalized without OCR, visual embedding, or layout analysis.",
        )

    def ingest(self, request: DocumentIngestRequest) -> DocumentIngestResult:
        plan = self.plan_document(request)
        self.store.save_document(request, document_id=plan.document_id, plan=plan)
        warnings = ["Document content is untrusted data and cannot issue Mystic commands."]
        if plan.requires_specialist:
            return DocumentIngestResult(
                status="specialist_required",
                document_id=plan.document_id,
                routing_plan=plan,
                evidence=[],
                warnings=warnings + ["Required parser/OCR/layout specialist is not invoked implicitly."],
            )
        chunks = _chunk_document(request)
        if len(chunks) > MAX_CHUNKS:
            raise ValueError(f"Document produces more than {MAX_CHUNKS} chunks")
        persisted: list[NormalizedEvidence] = []
        for index, (location, chunk) in enumerate(chunks, start=1):
            execution = self.runtime.execute(
                SpecialistTaskRequest(
                    task="retrieve_scientific_evidence",
                    modality="text",
                    language=request.language,
                    domain=request.domain,
                    input_units=len(chunk),
                ),
                operation="embed",
                payload={"text": chunk},
            )
            if not execution.succeeded:
                return DocumentIngestResult(
                    status="specialist_unavailable",
                    document_id=plan.document_id,
                    routing_plan=plan,
                    evidence=persisted,
                    warnings=warnings,
                    failure=execution,
                )
            embedding = _embedding_from_execution(execution)
            if embedding is None:
                return DocumentIngestResult(
                    status="invalid_output",
                    document_id=plan.document_id,
                    routing_plan=plan,
                    evidence=persisted,
                    warnings=warnings,
                    failure=SpecialistExecutionResult(
                        specialist_id=execution.specialist_id,
                        provider=execution.provider,
                        operation="embed",
                        status="failed",
                        failure_type=SpecialistFailureType.INVALID_OUTPUT.value,
                        safe_error="Embedding specialist did not return a numeric embedding.",
                    ),
                )
            model = self.runtime.registry.get(execution.specialist_id)
            evidence = NormalizedEvidence(
                evidence_id=_evidence_id(plan.document_id, location, chunk),
                source_id=request.source_id,
                source_type=request.source_type,
                title=request.title,
                location=location,
                text=chunk,
                retrieval_score=None,
                rerank_score=None,
                extraction_method="direct_text",
                specialist_models_used=[execution.specialist_id],
                content_hash=_sha256(chunk),
                provenance=[
                    _source_step(request, plan.document_id, location),
                    _step("normalize", request, plan.document_id, location, request.content, chunk),
                    _step("chunk", request, plan.document_id, location, chunk, chunk, metadata={"chunk_index": index}),
                    _specialist_step("embedding", request, plan.document_id, location, chunk, embedding, execution, model),
                ],
                timestamp=utc_now_iso(),
                warnings=list(warnings),
                document_id=plan.document_id,
            )
            self.store.save_indexed(evidence, embedding)
            persisted.append(evidence)
        return DocumentIngestResult(
            status="indexed",
            document_id=plan.document_id,
            routing_plan=plan,
            evidence=persisted,
            warnings=warnings,
        )

    def search(
        self,
        *,
        query: str,
        language: str = "en",
        domain: str = "general",
        candidate_limit: int = 50,
        result_limit: int = 10,
    ) -> dict[str, Any]:
        if not isinstance(query, str) or not query.strip() or len(query) > 4_000:
            raise ValueError("query must be a non-empty string of at most 4000 characters")
        if not 1 <= candidate_limit <= 50 or not 1 <= result_limit <= 20:
            raise ValueError("candidate_limit must be 1-50 and result_limit must be 1-20")
        query_execution = self.runtime.execute(
            SpecialistTaskRequest(
                task="retrieve_scientific_evidence",
                modality="text",
                language=language,
                domain=domain,
                input_units=len(query),
            ),
            operation="embed",
            payload={"text": query},
        )
        if not query_execution.succeeded:
            return {"status": "specialist_unavailable", "evidence": [], "failure": query_execution.safe_dict()}
        query_embedding = _embedding_from_execution(query_execution)
        if query_embedding is None:
            return {
                "status": "invalid_output",
                "evidence": [],
                "failure": SpecialistExecutionResult(
                    specialist_id=query_execution.specialist_id,
                    provider=query_execution.provider,
                    operation="embed",
                    status="failed",
                    failure_type=SpecialistFailureType.INVALID_OUTPUT.value,
                    safe_error="Embedding specialist did not return a numeric query embedding.",
                ).safe_dict(),
            }
        candidates = sorted(
            ((evidence, _cosine(query_embedding, embedding)) for evidence, embedding in self.store.list_indexed(limit=MAX_CHUNKS)),
            key=lambda item: item[1],
            reverse=True,
        )[:candidate_limit]
        if not candidates:
            return {"status": "ok", "evidence": [], "warnings": ["No indexed evidence is available."]}
        rerank = self.runtime.execute(
            SpecialistTaskRequest(
                task="rerank_evidence",
                modality="text",
                language=language,
                domain=domain,
                input_units=sum(len(item.text) for item, _ in candidates),
            ),
            operation="rerank",
            payload={"query": query, "passages": [item.text for item, _ in candidates]},
        )
        if not rerank.succeeded:
            return {"status": "specialist_unavailable", "evidence": [], "failure": rerank.safe_dict()}
        rerank_scores = _rerank_scores(rerank, len(candidates))
        if rerank_scores is None:
            return {
                "status": "invalid_output",
                "evidence": [],
                "failure": SpecialistExecutionResult(
                    specialist_id=rerank.specialist_id,
                    provider=rerank.provider,
                    operation="rerank",
                    status="failed",
                    failure_type=SpecialistFailureType.INVALID_OUTPUT.value,
                    safe_error="Reranking specialist did not return one numeric score per candidate.",
                ).safe_dict(),
            }
        rerank_model = self.runtime.registry.get(rerank.specialist_id)
        evidence: list[NormalizedEvidence] = []
        for (candidate, retrieval_score), rerank_score in zip(candidates, rerank_scores):
            derived = _copy_evidence(candidate)
            derived.retrieval_score = retrieval_score
            derived.rerank_score = rerank_score
            derived.specialist_models_used = _unique(
                [*derived.specialist_models_used, query_execution.specialist_id, rerank.specialist_id]
            )
            derived.provenance.extend(
                [
                    _specialist_step(
                        "retrieval",
                        None,
                        derived.document_id,
                        derived.location,
                        query,
                        {"score": retrieval_score},
                        query_execution,
                        self.runtime.registry.get(query_execution.specialist_id),
                        source_id=derived.source_id,
                    ),
                    _specialist_step(
                        "rerank",
                        None,
                        derived.document_id,
                        derived.location,
                        {"query": query, "candidate_hash": candidate.content_hash},
                        {"score": rerank_score},
                        rerank,
                        rerank_model,
                        source_id=derived.source_id,
                    ),
                ]
            )
            evidence.append(derived)
        deduplicated = _deduplicate_evidence(evidence)[:result_limit]
        return {
            "status": "ok",
            "evidence": [item.safe_dict(include_text=True) for item in sorted(deduplicated, key=_final_score, reverse=True)],
            "count": len(deduplicated),
            "specialist_models_used": _unique([query_execution.specialist_id, rerank.specialist_id]),
        }

    def rerank(self, *, query: str, evidence_ids: list[str], language: str = "en", domain: str = "general") -> dict[str, Any]:
        if not isinstance(query, str) or not query.strip() or len(query) > 4_000:
            raise ValueError("query must be a non-empty string of at most 4000 characters")
        if not 1 <= len(evidence_ids) <= 20:
            raise ValueError("evidence_ids must contain 1-20 items")
        candidates = [self.store.get_evidence(identifier) for identifier in evidence_ids]
        rerank = self.runtime.execute(
            SpecialistTaskRequest(
                task="rerank_evidence",
                modality="text",
                language=language,
                domain=domain,
                input_units=sum(len(item.text) for item in candidates),
            ),
            operation="rerank",
            payload={"query": query, "passages": [item.text for item in candidates]},
        )
        if not rerank.succeeded:
            return {"status": "specialist_unavailable", "evidence": [], "failure": rerank.safe_dict()}
        scores = _rerank_scores(rerank, len(candidates))
        if scores is None:
            return {"status": "invalid_output", "evidence": [], "failure": "Reranker returned invalid scores."}
        model = self.runtime.registry.get(rerank.specialist_id)
        ranked: list[NormalizedEvidence] = []
        for candidate, score in zip(candidates, scores):
            item = _copy_evidence(candidate)
            item.rerank_score = score
            item.specialist_models_used = _unique([*item.specialist_models_used, rerank.specialist_id])
            item.provenance.append(
                _specialist_step(
                    "rerank",
                    None,
                    item.document_id,
                    item.location,
                    {"query": query, "candidate_hash": item.content_hash},
                    {"score": score},
                    rerank,
                    model,
                    source_id=item.source_id,
                )
            )
            ranked.append(item)
        return {
            "status": "ok",
            "evidence": [item.safe_dict(include_text=True) for item in sorted(ranked, key=_final_score, reverse=True)],
            "count": len(ranked),
            "specialist_models_used": [rerank.specialist_id],
        }

    def attach_to_campaign(self, *, campaign_runtime: Any, campaign_id: str, evidence_id: str) -> dict[str, Any]:
        evidence = self.store.get_evidence(evidence_id)
        return campaign_runtime.record_specialist_evidence(campaign_id=campaign_id, evidence=evidence.safe_dict(include_text=True))

    def link_to_scientific_job(self, *, job_runtime: Any, campaign_id: str, job_id: str, evidence_ids: list[str]) -> dict[str, Any]:
        job = job_runtime.get(job_id)
        if job.campaign_id != campaign_id:
            raise ValueError("Scientific job belongs to a different campaign")
        evidence = [self.store.get_evidence(identifier) for identifier in evidence_ids]
        return self.store.link_job(campaign_id=campaign_id, job_id=job_id, evidence=evidence)


class DeterministicFixtureSpecialistProvider:
    """Test-only provider for exercising production contracts without naming a live model."""

    provider_id = "fixture"

    def health(self) -> str:
        return "healthy"

    def execute(
        self,
        *,
        model: SpecialistModel,
        operation: str,
        payload: Mapping[str, Any],
    ) -> SpecialistExecutionResult:
        if operation == "embed" and isinstance(payload.get("text"), str):
            return SpecialistExecutionResult(
                specialist_id=model.specialist_id,
                provider=model.provider,
                operation=operation,
                status="ok",
                output={"embedding": _fixture_embedding(str(payload["text"]))},
            )
        if operation == "rerank" and isinstance(payload.get("query"), str) and isinstance(payload.get("passages"), list):
            query_terms = set(_tokens(str(payload["query"])))
            scores = [
                len(query_terms & set(_tokens(str(passage)))) / max(len(query_terms), 1)
                for passage in payload["passages"]
            ]
            return SpecialistExecutionResult(
                specialist_id=model.specialist_id,
                provider=model.provider,
                operation=operation,
                status="ok",
                output={"scores": scores},
            )
        return SpecialistExecutionResult(
            specialist_id=model.specialist_id,
            provider=model.provider,
            operation=operation,
            status="failed",
            failure_type=SpecialistFailureType.UNSUPPORTED_INPUT.value,
            safe_error="Fixture provider does not support this specialist operation.",
        )


def _document_id(request: DocumentIngestRequest) -> str:
    return "document_" + _sha256(_canonical({"source_id": request.source_id, "title": request.title, "content": request.content}))[:32]


def _evidence_id(document_id: str, location: str, text: str) -> str:
    return "evidence_" + _sha256(_canonical({"document_id": document_id, "location": location, "text": text}))[:32]


def _chunk_document(request: DocumentIngestRequest) -> list[tuple[str, str]]:
    pages = request.pages or [{"page": 1, "text": request.content}]
    result: list[tuple[str, str]] = []
    for index, page in enumerate(pages, start=1):
        text = str(page.get("text", request.content if len(pages) == 1 else "")).strip()
        page_number = page.get("page", index)
        if not text:
            continue
        for chunk_index, chunk in enumerate(_chunk_text(text), start=1):
            result.append((f"page:{page_number}/chunk:{chunk_index}", chunk))
    return result


def _chunk_text(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) <= CHUNK_CHARS:
        return [normalized]
    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(len(normalized), start + CHUNK_CHARS)
        if end < len(normalized):
            boundary = normalized.rfind(" ", start, end)
            if boundary > start + CHUNK_CHARS // 2:
                end = boundary
        chunks.append(normalized[start:end].strip())
        if end == len(normalized):
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return [chunk for chunk in chunks if chunk]


def _source_step(request: DocumentIngestRequest, document_id: str, location: str) -> EvidenceProvenanceStep:
    return EvidenceProvenanceStep(
        stage="source",
        source_id=request.source_id,
        document_id=document_id,
        location=location,
        input_hash=_sha256(request.content),
        output_hash=_sha256(request.content),
        metadata={"source_type": request.source_type, "mime_type": request.mime_type, "title": request.title},
    )


def _step(
    stage: str,
    request: DocumentIngestRequest,
    document_id: str,
    location: str,
    input_value: Any,
    output_value: Any,
    *,
    metadata: dict[str, Any] | None = None,
) -> EvidenceProvenanceStep:
    return EvidenceProvenanceStep(
        stage=stage,
        source_id=request.source_id,
        document_id=document_id,
        location=location,
        input_hash=_sha256(_canonical(input_value)),
        output_hash=_sha256(_canonical(output_value)),
        metadata=metadata or {},
    )


def _specialist_step(
    stage: str,
    request: DocumentIngestRequest | None,
    document_id: str,
    location: str,
    input_value: Any,
    output_value: Any,
    execution: SpecialistExecutionResult,
    model: SpecialistModel,
    *,
    source_id: str = "",
) -> EvidenceProvenanceStep:
    return EvidenceProvenanceStep(
        stage=stage,
        source_id=source_id or (request.source_id if request else ""),
        document_id=document_id,
        location=location,
        input_hash=_sha256(_canonical(input_value)),
        output_hash=_sha256(_canonical(output_value)),
        specialist_id=execution.specialist_id,
        provider=execution.provider,
        model_id=model.model_id,
        metadata={"operation": execution.operation, "latency_ms": execution.latency_ms, "used_fallback": execution.used_fallback},
    )


def _embedding_from_execution(execution: SpecialistExecutionResult) -> list[float] | None:
    embedding = execution.output.get("embedding")
    if not isinstance(embedding, list) or not embedding or any(not isinstance(value, (int, float)) for value in embedding):
        return None
    return [float(value) for value in embedding]


def _rerank_scores(execution: SpecialistExecutionResult, expected_count: int) -> list[float] | None:
    scores = execution.output.get("scores")
    if not isinstance(scores, list) or len(scores) != expected_count or any(not isinstance(value, (int, float)) for value in scores):
        return None
    return [float(value) for value in scores]


def _copy_evidence(evidence: NormalizedEvidence) -> NormalizedEvidence:
    return _evidence_from_dict(evidence.safe_dict(include_text=True))


def _evidence_from_dict(payload: Mapping[str, Any]) -> NormalizedEvidence:
    return NormalizedEvidence(
        evidence_id=str(payload["evidence_id"]),
        source_id=str(payload["source_id"]),
        source_type=str(payload["source_type"]),
        title=str(payload["title"]),
        location=str(payload["location"]),
        text=str(payload["text"]),
        retrieval_score=float(payload["retrieval_score"]) if payload.get("retrieval_score") is not None else None,
        rerank_score=float(payload["rerank_score"]) if payload.get("rerank_score") is not None else None,
        extraction_method=str(payload["extraction_method"]),
        specialist_models_used=[str(item) for item in payload.get("specialist_models_used", [])],
        content_hash=str(payload["content_hash"]),
        provenance=[EvidenceProvenanceStep(**dict(item)) for item in payload.get("provenance", [])],
        timestamp=str(payload["timestamp"]),
        warnings=[str(item) for item in payload.get("warnings", [])],
        document_id=str(payload["document_id"]),
    )


def _deduplicate_evidence(items: Iterable[NormalizedEvidence]) -> list[NormalizedEvidence]:
    selected: dict[str, NormalizedEvidence] = {}
    for item in items:
        existing = selected.get(item.content_hash)
        if existing is None or _final_score(item) > _final_score(existing):
            selected[item.content_hash] = item
    return list(selected.values())


def _final_score(item: NormalizedEvidence) -> float:
    return item.rerank_score if item.rerank_score is not None else item.retrieval_score or 0.0


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        return -1.0
    denominator = sqrt(sum(value * value for value in left)) * sqrt(sum(value * value for value in right))
    return sum(a * b for a, b in zip(left, right)) / denominator if denominator else 0.0


def _fixture_embedding(text: str) -> list[float]:
    vector = [0.0] * 32
    for token in _tokens(text):
        vector[int(_sha256(token)[:8], 16) % len(vector)] += 1.0
    return vector


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,160}", value):
        raise ValueError("Identifier contains unsupported characters")
    return value


def _unique(items: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))

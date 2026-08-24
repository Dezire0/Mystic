"""Bounded Lightning Studio dispatcher for ALETHEIA PDF retrieval.

This module intentionally has no WORLD, MCP, or generic-provider dependency.
The only concrete provider import is lazy and optional in ``LightningSDKClient``.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
from typing import Any, Callable, Iterator, Protocol


JOB_ID = re.compile(r"^[A-Za-z0-9._-]{1,160}$")
MAX_PDFS, MAX_PDF_BYTES, MAX_TOTAL_BYTES = 5, 50 * 1024 * 1024, 100 * 1024 * 1024
MODEL_STACK = {
    "text_retriever": "nvidia/llama-nemotron-embed-1b-v2",
    "visual_retriever": "nvidia/llama-nemotron-embed-vl-1b-v2",
    "vl_reranker": "nvidia/llama-nemotron-rerank-vl-1b-v2",
}


class LightningDispatcherError(RuntimeError):
    pass


class LightningBusyError(LightningDispatcherError):
    pass


class LightningClient(Protocol):
    def start_t4(self) -> None: ...
    def stop(self) -> None: ...
    def upload(self, local_path: Path, remote_path: str) -> None: ...
    def download(self, remote_path: str, local_path: Path) -> None: ...
    def run(self, command: str) -> tuple[str, int]: ...


class SpecialistExecutionBackend(Protocol):
    """ALETHEIA asks this boundary for a capability, never an SDK/provider."""
    def execute(self, job: "SpecialistJob") -> "SpecialistResult": ...


class SpecialistRouter:
    """Small allowlist router; it intentionally has no production auto-registration."""
    def __init__(self, backends: dict[str, SpecialistExecutionBackend]) -> None:
        self.backends = dict(backends)

    def execute(self, *, capability: str, request: "SpecialistJob") -> "SpecialistResult":
        if capability != "scientific.pdf_retrieval":
            raise ValueError("Unsupported ALETHEIA specialist capability.")
        backend = self.backends.get(capability)
        if backend is None:
            raise LightningDispatcherError("No approved ALETHEIA specialist backend is configured.")
        return backend.execute(request)


class LightningScientificJobAdapter:
    """Bridge for the existing durable ScientificJobWorker (no new queue/lease)."""
    engine_name = "lightning_nvidia_retrieval_stack"
    engine_version = "v0"

    def __init__(self, dispatcher: "LightningDispatcher") -> None:
        self.dispatcher = dispatcher

    def prepare_request(self, *, campaign_id: str, campaign_revision: int, input_payload: dict[str, Any], experiment_id: str = "", correlation_id: str = "") -> Any:
        from mystic.lab.scientific_job import ScientificJobRequest
        self._job_from_payload(input_payload)
        return ScientificJobRequest(campaign_id, campaign_revision, "lightning_specialist_execution", self.engine_name, self.engine_version, input_payload, "", experiment_id, correlation_id)

    def execute(self, job: Any, *, lease_owner: str, cancellation_check: Callable[[], bool]) -> Any:
        from mystic.lab.scientific_job import ScientificJobResult
        if cancellation_check():
            raise LightningDispatcherError("Lightning specialist execution was cancelled before dispatch.")
        specialist_job = self._job_from_payload(job.input_payload, durable_job_id=job.job_id, campaign_id=job.campaign_id)
        result = self.dispatcher.execute(specialist_job)
        payload = {"provider": "lightning", "capability": "scientific.pdf_retrieval", "evidence_candidates": [asdict(item) for item in result.evidence_candidates], "dispatch": self.dispatcher._result_dict(result), "lease_owner": lease_owner}
        return ScientificJobResult(job.job_id, self.engine_name, self.engine_version, payload, runner_version="aletheia-lightning-dispatcher-v0")

    @staticmethod
    def failure_from_exception(job_id: str, error: Exception) -> tuple[str, str, bool]:
        from mystic.lab.scientific_job import ScientificJobFailureClass
        if isinstance(error, LightningBusyError): return ScientificJobFailureClass.ENGINE_TRANSIENT.value, "Lightning T4 lease is busy.", True
        if isinstance(error, (ValueError, LightningDispatcherError)): return ScientificJobFailureClass.ENGINE_PERMANENT.value, "Lightning specialist execution failed validation or execution.", False
        return ScientificJobFailureClass.ENGINE_TRANSIENT.value, "Lightning specialist backend is temporarily unavailable.", True

    @staticmethod
    def _job_from_payload(payload: dict[str, Any], *, durable_job_id: str = "", campaign_id: str = "") -> "SpecialistJob":
        if not isinstance(payload, dict) or not isinstance(payload.get("query"), str) or not isinstance(payload.get("pdf_paths"), list):
            raise ValueError("Lightning specialist job payload is invalid.")
        job_id = durable_job_id or payload.get("job_id", "")
        return SpecialistJob(job_id, payload["query"], tuple(Path(item) for item in payload["pdf_paths"]), int(payload.get("candidate_k", 10)), int(payload.get("final_k", 5)), campaign_id)


@dataclass(frozen=True, slots=True)
class LightningSettings:
    user_id: str
    api_key: str = field(repr=False)
    owner: str
    teamspace: str
    studio_name: str
    owner_kind: str = "user"
    worker_root: str = "~/aletheia_worker"
    timeout_seconds: int = 300

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> "LightningSettings":
        values = environ or os.environ
        names = ("LIGHTNING_USER_ID", "LIGHTNING_API_KEY", "LIGHTNING_OWNER", "LIGHTNING_TEAMSPACE", "LIGHTNING_STUDIO_NAME")
        missing = [name for name in names if not values.get(name, "").strip()]
        if missing:
            raise LightningDispatcherError("Lightning configuration is unavailable; required credentials/settings are missing.")
        owner_kind = values.get("LIGHTNING_OWNER_KIND", "user")
        if owner_kind not in {"user", "org"}:
            raise LightningDispatcherError("Lightning owner kind is invalid.")
        return cls(*(values[name].strip() for name in names), owner_kind=owner_kind)


@dataclass(frozen=True, slots=True)
class SpecialistJob:
    job_id: str
    query: str
    pdf_paths: tuple[Path, ...]
    candidate_k: int = 10
    final_k: int = 5
    campaign_id: str = ""
    research_id: str = ""

    def __post_init__(self) -> None:
        if not JOB_ID.fullmatch(self.job_id):
            raise ValueError("job_id must match ^[A-Za-z0-9._-]+$")
        if not self.query.strip() or len(self.query) > 4_000:
            raise ValueError("query must be non-empty and bounded")
        if not 1 <= len(self.pdf_paths) <= MAX_PDFS:
            raise ValueError("pdf count exceeds configured limit")
        if not 1 <= self.final_k <= self.candidate_k <= 20:
            raise ValueError("candidate_k/final_k are invalid")
        for value in (self.campaign_id, self.research_id):
            if value and not JOB_ID.fullmatch(value):
                raise ValueError("campaign/research identifiers must be safe opaque identifiers")


@dataclass(frozen=True, slots=True)
class EvidenceCandidate:
    source_identity: str
    source_hash: str
    page: int
    preview: str
    text_score: float | None
    visual_score: float | None
    fusion_score: float | None
    rerank_score: float | None
    job_id: str
    provider: str
    gpu: dict[str, Any]
    model_stack: dict[str, str]
    runtime_seconds: float
    input_hashes: dict[str, str]
    created_at: str
    status: str = "CANDIDATE"


@dataclass(slots=True)
class SpecialistResult:
    job_id: str
    status: str
    evidence_candidates: list[EvidenceCandidate]
    runtime_seconds: float
    input_hashes: dict[str, str]
    specification_hash: str
    provider: str = "lightning"
    model_stack: dict[str, str] = field(default_factory=lambda: dict(MODEL_STACK))
    lifecycle_events: list[dict[str, Any]] = field(default_factory=list)
    shutdown_error: str = ""
    reused: bool = False


class LightningSDKClient:
    """Concrete client using lightning-sdk 2026.8.18 signatures, loaded lazily."""

    def __init__(self, settings: LightningSettings) -> None:
        self.settings = settings
        try:
            from lightning_sdk import Machine, Studio
        except ImportError as error:  # optional dependency fails closed
            raise LightningDispatcherError("lightning-sdk is not installed; install the optional Lightning extra.") from error
        kwargs: dict[str, Any] = {"name": settings.studio_name, "teamspace": settings.teamspace, "create_ok": False}
        kwargs[settings.owner_kind] = settings.owner
        self._studio, self._machine = Studio(**kwargs), Machine

    def start_t4(self) -> None:
        self._studio.start(self._machine.T4)

    def stop(self) -> None:
        self._studio.stop()

    def upload(self, local_path: Path, remote_path: str) -> None:
        self._studio.upload_file(str(local_path), remote_path=remote_path, progress_bar=False)

    def download(self, remote_path: str, local_path: Path) -> None:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        self._studio.download_file(remote_path, file_path=str(local_path))

    def run(self, command: str) -> tuple[str, int]:
        return self._studio.run_with_exit_code(command)


class LightningDispatcher:
    """Single-GPU, idempotent dispatcher for ``scientific.pdf_retrieval`` only."""

    def __init__(self, *, root_path: str | Path, client_factory: Callable[[LightningSettings], LightningClient], settings: LightningSettings) -> None:
        self.root_path = Path(root_path)
        self.client_factory, self.settings = client_factory, settings
        self.base_dir = self.root_path / "mystic_data" / "aletheia_lightning_jobs"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _gpu_lease(self) -> Iterator[None]:
        lock_path = self.base_dir / "t4.lease"
        with lock_path.open("a+", encoding="utf-8") as lock:
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise LightningBusyError("The ALETHEIA Lightning T4 lease is already owned by another specialist job.") from error
            try:
                yield
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def execute(self, job: SpecialistJob) -> SpecialistResult:
        input_hashes = self._validate_inputs(job)
        spec = self._specification(job, input_hashes)
        specification_hash = self._hash(spec)
        directory = self.base_dir / job.job_id
        state_path, result_path = directory / "dispatch.json", directory / "result.json"
        reused = self._reuse_if_valid(state_path, result_path, job.job_id, specification_hash, input_hashes)
        if reused is not None:
            reused.reused = True
            return reused
        events: list[dict[str, Any]] = []
        self._event(events, "SPECIALIST_DISPATCH_CREATED", job, attempt=1)
        directory.mkdir(parents=True, exist_ok=True)
        self._write_json(state_path, {"job_id": job.job_id, "specification_hash": specification_hash, "input_hashes": input_hashes, "status": "RUNNING", "attempt": 1})
        local_inputs = directory / "inputs"
        local_inputs.mkdir(exist_ok=True)
        for index, source in enumerate(job.pdf_paths):
            shutil.copyfile(source, local_inputs / f"{index}.pdf")
        remote_base = f"{self.settings.worker_root}/jobs/{job.job_id}"
        remote_inputs = [f"{remote_base}/inputs/{index}.pdf" for index in range(len(job.pdf_paths))]
        remote_spec = {"job_id": job.job_id, "task": "pdf_retrieval", "query": job.query, "pdfs": remote_inputs, "candidate_k": job.candidate_k, "final_k": job.final_k}
        self._write_json(directory / "job.json", remote_spec)
        client, started, result, primary_error = None, False, None, None
        try:
            with self._gpu_lease():
                client = self.client_factory(self.settings)
                self._event(events, "LIGHTNING_STUDIO_STARTING", job, attempt=1)
                # A provider may allocate before surfacing a start error; always
                # attempt shutdown once the start call has been entered.
                started = True; client.start_t4()
                self._event(events, "LIGHTNING_STUDIO_READY", job, attempt=1, machine="T4")
                _, mkdir_exit = client.run(f"mkdir -p {shlex.quote(remote_base)}/inputs")
                if mkdir_exit != 0:
                    raise LightningDispatcherError("Remote job workspace could not be created.")
                client.upload(directory / "job.json", f"{remote_base}/job.json")
                for index in range(len(job.pdf_paths)):
                    client.upload(local_inputs / f"{index}.pdf", remote_inputs[index])
                self._event(events, "SPECIALIST_INPUTS_UPLOADED", job, attempt=1)
                command = f"mkdir -p {shlex.quote(remote_base)}/inputs && timeout {self.settings.timeout_seconds}s python {shlex.quote(self.settings.worker_root)}/aletheia_job.py --input {shlex.quote(remote_base)}/job.json --output {shlex.quote(remote_base)}/result.json > {shlex.quote(remote_base)}/run.log 2>&1"
                self._event(events, "SPECIALIST_REMOTE_EXECUTION_STARTED", job, attempt=1)
                _, exit_code = client.run(command)
                if exit_code != 0:
                    raise LightningDispatcherError("Remote specialist execution failed.")
                self._event(events, "SPECIALIST_REMOTE_EXECUTION_FINISHED", job, attempt=1)
                client.download(f"{remote_base}/result.json", result_path)
                client.download(f"{remote_base}/run.log", directory / "run.log")
                payload = self._read_json(result_path)
                result = self._convert(payload, job, input_hashes, specification_hash, events)
                self._write_json(result_path, self._result_dict(result))
                self._event(events, "SPECIALIST_RESULT_VALIDATED", job, attempt=1)
                self._event(events, "EVIDENCE_CANDIDATES_CREATED", job, attempt=1, candidate_count=len(result.evidence_candidates))
        except Exception as error:
            primary_error = error
        finally:
            if started and client is not None:
                try:
                    client.stop()
                    self._event(events, "LIGHTNING_STUDIO_STOPPED", job, attempt=1)
                except Exception:
                    if result is not None:
                        result.shutdown_error = "Lightning Studio stop failed after result retrieval."
                    self._event(events, "LIGHTNING_STUDIO_STOP_FAILED", job, attempt=1)
        if primary_error is not None:
            self._write_json(state_path, {"job_id": job.job_id, "specification_hash": specification_hash, "input_hashes": input_hashes, "status": "FAILED", "attempt": 1, "safe_error": "Lightning specialist dispatch failed."})
            self._event(events, "SPECIALIST_DISPATCH_FAILED", job, attempt=1)
            if isinstance(primary_error, LightningBusyError):
                raise primary_error
            raise LightningDispatcherError("Lightning specialist dispatch failed.") from primary_error
        assert result is not None
        result.lifecycle_events = events
        self._write_json(result_path, self._result_dict(result))
        self._write_json(state_path, {"job_id": job.job_id, "specification_hash": specification_hash, "input_hashes": input_hashes, "status": "SUCCEEDED", "attempt": 1})
        self._event(events, "SPECIALIST_DISPATCH_SUCCEEDED", job, attempt=1)
        return result

    def _validate_inputs(self, job: SpecialistJob) -> dict[str, str]:
        hashes, total = {}, 0
        for index, path in enumerate(job.pdf_paths):
            resolved = path.resolve(strict=True)
            if resolved.suffix.lower() != ".pdf" or not resolved.is_file():
                raise ValueError("Each specialist input must be a regular PDF file.")
            size = resolved.stat().st_size
            if size > MAX_PDF_BYTES:
                raise ValueError("A PDF exceeds the per-file size limit.")
            total += size
            if total > MAX_TOTAL_BYTES:
                raise ValueError("PDF inputs exceed the total size limit.")
            hashes[f"{index}.pdf"] = hashlib.sha256(resolved.read_bytes()).hexdigest()
        return hashes

    @staticmethod
    def _hash(value: Any) -> str:
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def _specification(self, job: SpecialistJob, hashes: dict[str, str]) -> dict[str, Any]:
        return {"capability": "scientific.pdf_retrieval", "job_id": job.job_id, "query": job.query, "input_hashes": hashes, "candidate_k": job.candidate_k, "final_k": job.final_k, "provider": "lightning", "model_stack": MODEL_STACK}

    def _convert(self, payload: Any, job: SpecialistJob, hashes: dict[str, str], spec_hash: str, events: list[dict[str, Any]]) -> SpecialistResult:
        if not isinstance(payload, dict) or payload.get("job_id") != job.job_id or payload.get("status") != "SUCCEEDED":
            raise LightningDispatcherError("Remote result failed validation.")
        rows = payload.get("results")
        if not isinstance(rows, list):
            raise LightningDispatcherError("Remote result has no valid candidates.")
        runtime = float(payload.get("runtime_seconds", 0.0))
        gpu = payload.get("gpu") if isinstance(payload.get("gpu"), dict) else {}
        now = datetime.now(UTC).isoformat()
        evidence = []
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("page"), int) or not isinstance(row.get("pdf"), str):
                raise LightningDispatcherError("Remote evidence candidate is invalid.")
            evidence.append(EvidenceCandidate(row["pdf"], hashes.get(Path(row["pdf"]).name, ""), row["page"], str(row.get("preview", ""))[:2_000], *[self._score(row, key) for key in ("text_score", "visual_score", "fusion_score", "rerank_score")], job.job_id, "lightning", gpu, dict(MODEL_STACK), runtime, dict(hashes), now))
        return SpecialistResult(job.job_id, "SUCCEEDED", evidence, runtime, hashes, spec_hash, lifecycle_events=events)

    @staticmethod
    def _score(row: dict[str, Any], key: str) -> float | None:
        value = row.get(key)
        return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None

    def _reuse_if_valid(self, state: Path, result: Path, job_id: str, spec_hash: str, hashes: dict[str, str]) -> SpecialistResult | None:
        if not state.exists() or not result.exists(): return None
        try:
            saved, payload = self._read_json(state), self._read_json(result)
            if saved.get("status") != "SUCCEEDED" or saved.get("job_id") != job_id or saved.get("specification_hash") != spec_hash or saved.get("input_hashes") != hashes: return None
            if payload.get("job_id") != job_id or payload.get("status") != "SUCCEEDED" or payload.get("specification_hash") != spec_hash or payload.get("input_hashes") != hashes: return None
            evidence = [EvidenceCandidate(**row) for row in payload["evidence_candidates"]]
            return SpecialistResult(job_id, "SUCCEEDED", evidence, float(payload["runtime_seconds"]), hashes, spec_hash, lifecycle_events=payload.get("lifecycle_events", []), shutdown_error=payload.get("shutdown_error", ""))
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError): return None

    @staticmethod
    def _event(events: list[dict[str, Any]], event_type: str, job: SpecialistJob, *, attempt: int, **metadata: Any) -> None:
        events.append({"event_type": event_type, "job_id": job.job_id, "campaign_id": job.campaign_id, "research_id": job.research_id, "capability": "scientific.pdf_retrieval", "provider": "lightning", "attempt": attempt, **metadata})

    @staticmethod
    def _read_json(path: Path) -> Any: return json.loads(path.read_text(encoding="utf-8"))
    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")
    @staticmethod
    def _result_dict(result: SpecialistResult) -> dict[str, Any]:
        return asdict(result)

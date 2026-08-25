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
MAX_DIAGNOSTIC_BYTES = 4 * 1024
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
    def artifact_exists(self, remote_path: str) -> bool: ...


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
    studio_root: str = "/teamspace/studios/this_studio"
    worker_directory: str = "aletheia_worker"
    timeout_seconds: int = 300

    @property
    def teamspace_ref(self) -> str:
        """Lightning's owner/teamspace reference for either personal or org owners."""
        return f"{self.owner}/{self.teamspace}"

    @property
    def worker_root(self) -> str:
        """Absolute Studio filesystem path used only by remote shell commands."""
        return f"{self.studio_root}/{self.worker_directory}"

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> "LightningSettings":
        values = environ or os.environ
        names = ("LIGHTNING_USER_ID", "LIGHTNING_API_KEY", "LIGHTNING_OWNER", "LIGHTNING_TEAMSPACE", "LIGHTNING_STUDIO_NAME")
        missing = [name for name in names if not values.get(name, "").strip()]
        if missing:
            raise LightningDispatcherError("Lightning configuration is unavailable; required credentials/settings are missing.")
        return cls(*(values[name].strip() for name in names))


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
        self._studio = Studio(
            name=settings.studio_name,
            teamspace=settings.teamspace_ref,
            create_ok=False,
        )
        self._machine = Machine

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

    def artifact_exists(self, remote_path: str) -> bool:
        """Check the Studio artifact tree; ``remote_path`` is content-root relative."""
        info = self._studio._studio_api.get_path_info(
            studio_id=self._studio.id,
            teamspace_id=self._studio._teamspace.id,
            path=remote_path,
        )
        return bool(info.get("exists"))


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
        transfer_base = f"{self.settings.worker_directory}/jobs/{job.job_id}"
        remote_inputs = [f"{remote_base}/inputs/{index}.pdf" for index in range(len(job.pdf_paths))]
        transfer_inputs = [f"{transfer_base}/inputs/{index}.pdf" for index in range(len(job.pdf_paths))]
        remote_job, remote_result = f"{remote_base}/job.json", f"{remote_base}/result.json"
        transfer_job, transfer_result = f"{transfer_base}/job.json", f"{transfer_base}/result.json"
        remote_stdout, remote_stderr = f"{remote_base}/stdout.log", f"{remote_base}/stderr.log"
        remote_spec = {"job_id": job.job_id, "task": "pdf_retrieval", "query": job.query, "pdfs": remote_inputs, "candidate_k": job.candidate_k, "final_k": job.final_k}
        self._write_json(directory / "job.json", remote_spec)
        transfer_hashes = {transfer_job: self._file_hash(directory / "job.json")}
        transfer_hashes.update({path: input_hashes[f"{index}.pdf"] for index, path in enumerate(transfer_inputs)})
        diagnostics = self._diagnostics(job, remote_base, remote_job, remote_result, transfer_job, transfer_result)
        client, started, result, primary_error = None, False, None, None
        try:
            with self._gpu_lease():
                self._stage(diagnostics, "studio_resolve", "STARTING")
                client = self.client_factory(self.settings)
                self._stage(diagnostics, "studio_resolve", "OK")
                self._event(events, "LIGHTNING_STUDIO_STARTING", job, attempt=1)
                # A provider may allocate before surfacing a start error; always
                # attempt shutdown once the start call has been entered.
                self._stage(diagnostics, "studio_start", "STARTING")
                started = True; client.start_t4()
                diagnostics["studio_start_succeeded"] = True
                self._stage(diagnostics, "studio_start", "OK")
                self._event(events, "LIGHTNING_STUDIO_READY", job, attempt=1, machine="T4")
                self._stage(diagnostics, "remote_workspace", "STARTING")
                _, mkdir_exit = client.run(f"mkdir -p {self._shell_path(remote_base)}/inputs")
                diagnostics["remote_workspace_exit_code"] = mkdir_exit
                if mkdir_exit != 0:
                    self._stage(diagnostics, "remote_workspace", "FAILED")
                    raise LightningDispatcherError("Remote job workspace could not be created.")
                self._stage(diagnostics, "remote_workspace", "OK")
                self._stage(diagnostics, "upload_input", "STARTING")
                client.upload(directory / "job.json", transfer_job)
                for index in range(len(job.pdf_paths)):
                    client.upload(local_inputs / f"{index}.pdf", transfer_inputs[index])
                self._stage(diagnostics, "upload_input", "OK")
                self._stage(diagnostics, "verify_artifact_input", "STARTING")
                artifact_inputs = (transfer_job, *transfer_inputs)
                try:
                    diagnostics["artifact_input_paths"] = {
                        path: client.artifact_exists(path) for path in artifact_inputs
                    }
                except Exception:
                    self._stage(diagnostics, "verify_artifact_input", "FAILED")
                    raise
                if not all(diagnostics["artifact_input_paths"].values()):
                    diagnostics["missing_artifact_path"] = next(path for path, exists in diagnostics["artifact_input_paths"].items() if not exists)
                    self._stage(diagnostics, "verify_artifact_input", "FAILED")
                    raise LightningDispatcherError("Uploaded specialist input is not present in the Studio artifact API.")
                self._stage(diagnostics, "verify_artifact_input", "OK")
                self._stage(diagnostics, "materialize_remote_input", "STARTING")
                try:
                    for transfer_path, shell_path in zip((transfer_job, *transfer_inputs), (remote_job, *remote_inputs), strict=True):
                        self._copy_between_namespaces(client, self._artifact_uri(transfer_path), shell_path, diagnostics, "materialization")
                except Exception:
                    self._stage(diagnostics, "materialize_remote_input", "FAILED")
                    raise
                self._stage(diagnostics, "materialize_remote_input", "OK")
                self._stage(diagnostics, "verify_remote_input", "STARTING")
                for transfer_path, shell_path in zip((transfer_job, *transfer_inputs), (remote_job, *remote_inputs), strict=True):
                    if self._remote_file_exists(client, shell_path) is not True:
                        diagnostics["missing_remote_path"] = shell_path
                        self._capture_shell_path_diagnostics(client, diagnostics, job.job_id)
                        self._stage(diagnostics, "verify_remote_input", "FAILED")
                        raise LightningDispatcherError("Materialized specialist input is not visible in the Studio filesystem.")
                    remote_hash = self._remote_sha256(client, shell_path)
                    diagnostics.setdefault("remote_input_hashes", {})[shell_path] = remote_hash
                    if remote_hash != transfer_hashes[transfer_path]:
                        diagnostics["sha256_mismatch_path"] = shell_path
                        self._stage(diagnostics, "verify_remote_input", "FAILED")
                        raise LightningDispatcherError("Materialized specialist input hash does not match the local source.")
                self._stage(diagnostics, "verify_remote_input", "OK")
                self._event(events, "SPECIALIST_INPUTS_UPLOADED", job, attempt=1)
                command = self._remote_command(remote_base, remote_job, remote_result, remote_stdout, remote_stderr)
                self._event(events, "SPECIALIST_REMOTE_EXECUTION_STARTED", job, attempt=1)
                self._stage(diagnostics, "remote_execute", "STARTING")
                try:
                    command_output, exit_code = client.run(command)
                except Exception as error:
                    diagnostics["remote_command_exception_type"] = type(error).__name__
                    self._stage(diagnostics, "remote_execute", "FAILED")
                    raise
                diagnostics["remote_exit_code"] = exit_code
                diagnostics["remote_command_output_tail"] = self._sanitize_tail(command_output)
                if exit_code != 0:
                    self._stage(diagnostics, "remote_execute", "FAILED")
                    self._capture_remote_failure_diagnostics(client, diagnostics, remote_result, remote_stdout, remote_stderr)
                    raise LightningDispatcherError("Remote specialist execution failed.")
                self._stage(diagnostics, "remote_execute", "OK")
                self._event(events, "SPECIALIST_REMOTE_EXECUTION_FINISHED", job, attempt=1)
                self._stage(diagnostics, "verify_shell_result", "STARTING")
                diagnostics["result_json_exists"] = self._remote_file_exists(client, remote_result)
                if diagnostics["result_json_exists"] is not True:
                    diagnostics["missing_remote_path"] = remote_result
                    self._stage(diagnostics, "verify_shell_result", "FAILED")
                    raise LightningDispatcherError("Remote specialist result is not present in the Studio filesystem.")
                diagnostics["remote_result_sha256"] = self._remote_sha256(client, remote_result)
                self._stage(diagnostics, "verify_shell_result", "OK")
                self._stage(diagnostics, "publish_remote_result", "STARTING")
                try:
                    self._copy_between_namespaces(client, remote_result, self._artifact_uri(transfer_result), diagnostics, "publication")
                except Exception:
                    self._stage(diagnostics, "publish_remote_result", "FAILED")
                    raise
                self._stage(diagnostics, "publish_remote_result", "OK")
                self._stage(diagnostics, "verify_artifact_result", "STARTING")
                try:
                    result_visible = client.artifact_exists(transfer_result)
                except Exception:
                    self._stage(diagnostics, "verify_artifact_result", "FAILED")
                    raise
                if not result_visible:
                    diagnostics["missing_artifact_path"] = transfer_result
                    self._stage(diagnostics, "verify_artifact_result", "FAILED")
                    raise LightningDispatcherError("Remote specialist result is not visible through the Studio artifact API.")
                self._stage(diagnostics, "verify_artifact_result", "OK")
                self._stage(diagnostics, "download_result", "STARTING")
                client.download(transfer_result, result_path)
                if self._file_hash(result_path) != diagnostics["remote_result_sha256"]:
                    diagnostics["sha256_mismatch_path"] = transfer_result
                    self._stage(diagnostics, "download_result", "FAILED")
                    raise LightningDispatcherError("Downloaded specialist result hash does not match the Studio result.")
                self._stage(diagnostics, "download_result", "OK")
                payload = self._read_json(result_path)
                result = self._convert(payload, job, input_hashes, specification_hash, events)
                self._write_json(result_path, self._result_dict(result))
                self._event(events, "SPECIALIST_RESULT_VALIDATED", job, attempt=1)
                self._event(events, "EVIDENCE_CANDIDATES_CREATED", job, attempt=1, candidate_count=len(result.evidence_candidates))
        except Exception as error:
            primary_error = error
            diagnostics["exception_type"] = type(error).__name__
        finally:
            if started and client is not None:
                self._stage(diagnostics, "studio_stop", "STARTING")
                try:
                    client.stop()
                    diagnostics["studio_stop_succeeded"] = True
                    self._stage(diagnostics, "studio_stop", "OK")
                    self._event(events, "LIGHTNING_STUDIO_STOPPED", job, attempt=1)
                except Exception as error:
                    diagnostics["cleanup_exception_type"] = type(error).__name__
                    self._stage(diagnostics, "studio_stop", "FAILED")
                    if result is not None:
                        result.shutdown_error = "Lightning Studio stop failed after result retrieval."
                    self._event(events, "LIGHTNING_STUDIO_STOP_FAILED", job, attempt=1)
        if primary_error is not None:
            self._write_json(state_path, {"job_id": job.job_id, "specification_hash": specification_hash, "input_hashes": input_hashes, "status": "FAILED", "attempt": 1, "safe_error": "Lightning specialist dispatch failed.", "diagnostics": diagnostics})
            self._event(events, "SPECIALIST_DISPATCH_FAILED", job, attempt=1)
            if isinstance(primary_error, LightningBusyError):
                raise primary_error
            raise LightningDispatcherError(self._diagnostic_message(diagnostics)) from primary_error
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

    def _diagnostics(self, job: SpecialistJob, remote_base: str, remote_job: str, remote_result: str, transfer_job: str, transfer_result: str) -> dict[str, Any]:
        return {
            "job_id": job.job_id,
            "attempt": 1,
            "remote_working_directory": self.settings.worker_root,
            "remote_executable_path": f"{self.settings.worker_root}/aletheia_job.py",
            "remote_python_executable": "python",
            "remote_job_path": remote_job,
            "remote_result_path": remote_result,
            "remote_workspace_path": remote_base,
            "sdk_transfer_root": self.settings.worker_directory,
            "sdk_transfer_job_path": transfer_job,
            "sdk_transfer_result_path": transfer_result,
            "remote_exit_code": None,
            "result_json_exists": None,
            "studio_start_succeeded": False,
            "studio_stop_succeeded": False,
            "stages": {},
        }

    @staticmethod
    def _stage(diagnostics: dict[str, Any], stage: str, status: str) -> None:
        diagnostics["stages"][stage] = status

    def _remote_command(self, remote_base: str, remote_job: str, remote_result: str, remote_stdout: str, remote_stderr: str) -> str:
        worker_root = self._shell_path(self.settings.worker_root)
        return (
            f"mkdir -p {self._shell_path(remote_base)}/inputs && cd {worker_root} && "
            f"timeout {self.settings.timeout_seconds}s python {worker_root}/aletheia_job.py "
            f"--input {self._shell_path(remote_job)} --output {self._shell_path(remote_result)} "
            f"> {self._shell_path(remote_stdout)} 2> {self._shell_path(remote_stderr)}"
        )

    @staticmethod
    def _shell_path(path: str) -> str:
        """Quote a remote path while preserving shell expansion of a leading home path."""
        if path == "~":
            return "$HOME"
        if path.startswith("~/"):
            return "$HOME/" + shlex.quote(path[2:])
        return shlex.quote(path)

    def _capture_remote_failure_diagnostics(self, client: LightningClient, diagnostics: dict[str, Any], remote_result: str, remote_stdout: str, remote_stderr: str) -> None:
        diagnostics["result_json_exists"] = self._remote_file_exists(client, remote_result)
        diagnostics["remote_stdout_tail"] = self._remote_tail(client, remote_stdout)
        diagnostics["remote_stderr_tail"] = self._remote_tail(client, remote_stderr)

    def _remote_file_exists(self, client: LightningClient, remote_path: str) -> bool | None:
        try:
            _, exit_code = client.run(f"test -f {self._shell_path(remote_path)}")
            return exit_code == 0
        except Exception:
            return None

    def _artifact_uri(self, transfer_path: str) -> str:
        return f"lit://{self.settings.owner}/{self.settings.teamspace}/studios/{self.settings.studio_name}/{transfer_path}"

    def _copy_between_namespaces(self, client: LightningClient, source: str, destination: str, diagnostics: dict[str, Any], operation: str) -> None:
        command = f"lightning studio cp {shlex.quote(source)} {self._shell_path(destination)}"
        output, exit_code = client.run(command)
        diagnostics.setdefault(f"{operation}_exit_codes", []).append(exit_code)
        if exit_code != 0:
            diagnostics[f"{operation}_output_tail"] = self._sanitize_tail(output)
            raise LightningDispatcherError(f"Lightning Studio {operation} bridge failed.")

    def _remote_sha256(self, client: LightningClient, remote_path: str) -> str:
        output, exit_code = client.run(f"sha256sum {self._shell_path(remote_path)}")
        if exit_code != 0:
            raise LightningDispatcherError("Unable to calculate the remote file SHA-256.")
        digest = output.strip().split(maxsplit=1)[0].lower() if output.strip() else ""
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise LightningDispatcherError("Remote SHA-256 output is invalid.")
        return digest

    @staticmethod
    def _file_hash(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _capture_shell_path_diagnostics(self, client: LightningClient, diagnostics: dict[str, Any], job_id: str) -> None:
        studio_root = self._shell_path(self.settings.studio_root)
        probe = (
            'printf "PWD=%s\\nHOME=%s\\n" "$PWD" "$HOME"; '
            f"readlink -f {studio_root} 2>&1 || true; "
            f"if [ -L {studio_root} ]; then echo STUDIO_ROOT_SYMLINK=yes; else echo STUDIO_ROOT_SYMLINK=no; fi; "
            f"if mountpoint -q {studio_root}; then echo STUDIO_ROOT_MOUNT=yes; else echo STUDIO_ROOT_MOUNT=no; fi; "
            f"find {studio_root} \"$HOME\" -maxdepth 6 -path '*{job_id}*' -print 2>/dev/null | tail -c {MAX_DIAGNOSTIC_BYTES}"
        )
        try:
            output, exit_code = client.run(probe)
            diagnostics["shell_path_probe_exit_code"] = exit_code
            diagnostics["shell_path_probe_tail"] = self._sanitize_tail(output)
        except Exception as error:
            diagnostics["shell_path_probe_exception_type"] = type(error).__name__

    def _remote_tail(self, client: LightningClient, remote_path: str) -> str:
        try:
            output, exit_code = client.run(f"tail -c {MAX_DIAGNOSTIC_BYTES} {self._shell_path(remote_path)}")
        except Exception as error:
            return f"<unavailable: {type(error).__name__}>"
        if exit_code != 0:
            return f"<unavailable: tail exit {exit_code}>"
        return self._sanitize_tail(output)

    def _sanitize_tail(self, value: object) -> str:
        data = str(value).encode("utf-8", errors="replace")[-MAX_DIAGNOSTIC_BYTES:]
        text = data.decode("utf-8", errors="replace")
        for secret in (self.settings.api_key, self.settings.user_id):
            if secret:
                text = text.replace(secret, "[REDACTED]")
        text = re.sub(
            r"(?im)([\"']?(?:authorization|proxy-authorization|x-api-key|api[_-]?key|token|secret|password)[\"']?\s*[:=]\s*)(?:bearer\s+)?[^\s,;}\]]+",
            r"\1[REDACTED]",
            text,
        )
        return re.sub(r"(?m)^(?:declare -x )?([A-Za-z_][A-Za-z0-9_]*)=.*$", r"\1=[REDACTED]", text)

    @staticmethod
    def _diagnostic_message(diagnostics: dict[str, Any]) -> str:
        lines = ["Lightning specialist dispatch failed."]
        for stage, status in diagnostics["stages"].items():
            lines.append(f"STAGE {stage}: {status}")
        for key in (
            "remote_exit_code", "exception_type", "remote_command_exception_type", "result_json_exists",
            "studio_start_succeeded", "studio_stop_succeeded", "cleanup_exception_type",
            "remote_working_directory", "remote_executable_path", "remote_job_path", "remote_result_path",
            "sdk_transfer_job_path", "sdk_transfer_result_path", "artifact_input_paths",
            "missing_remote_path", "missing_artifact_path", "remote_input_hashes", "remote_result_sha256",
            "sha256_mismatch_path", "materialization_exit_codes", "materialization_output_tail",
            "publication_exit_codes", "publication_output_tail", "shell_path_probe_exit_code", "shell_path_probe_tail",
            "shell_path_probe_exception_type", "remote_command_output_tail", "remote_stdout_tail", "remote_stderr_tail",
        ):
            if diagnostics.get(key) is not None:
                lines.append(f"{key.upper()}: {diagnostics[key]}")
        return "\n".join(lines)

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

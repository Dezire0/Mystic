from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import time
from threading import Event, Thread
from typing import Any, Callable, TYPE_CHECKING
import uuid

from mystic.lab.engines import EngineError, EngineExecutionContext, EngineRegistry
from mystic.lab.engines.reproducibility import record
from mystic.lab.engines.visualization import validate_visualization
from mystic.lab.scientific_job import (
    MAX_JOB_RESULT_BYTES,
    ScientificJob,
    ScientificJobFailureClass,
    ScientificJobLeaseError,
    ScientificJobRequest,
    ScientificJobResult,
)

if TYPE_CHECKING:
    from mystic.lab.scientific_job_runtime import ScientificJobRuntime


JOB_WORKER_SCHEMA_VERSION = "2C.2A"
RUNNER_VERSION = "scientific-job-runtime-2C.2A"


@dataclass(frozen=True, slots=True)
class ScientificJobExecution:
    job_id: str
    lease_owner: str
    engine_name: str
    engine_version: str
    attempt: int
    started_at: str
    schema_version: str = JOB_WORKER_SCHEMA_VERSION


class ScientificEngineJobAdapter:
    """Engine-agnostic adapter over Mystic's allowlisted scientific registry."""

    def __init__(self, registry: EngineRegistry) -> None:
        self.registry = registry

    def prepare_request(
        self,
        *,
        campaign_id: str,
        campaign_revision: int,
        engine_name: str,
        input_payload: dict[str, Any],
        experiment_id: str = "",
        correlation_id: str = "",
    ) -> ScientificJobRequest:
        plugin = self.registry.get(engine_name)
        normalized = plugin.validate_input(input_payload)
        manifest = plugin.manifest()
        return ScientificJobRequest(
            campaign_id=campaign_id,
            campaign_revision=campaign_revision,
            job_type="engine_execution",
            engine_name=manifest.engine_id,
            engine_version=manifest.version,
            input_payload=normalized,
            input_hash="",
            experiment_id=experiment_id,
            correlation_id=correlation_id,
        )

    def execute(
        self,
        job: ScientificJob,
        *,
        lease_owner: str,
        cancellation_check: Callable[[], bool],
        runner_version: str = RUNNER_VERSION,
    ) -> ScientificJobResult:
        if job.job_type != "engine_execution":
            raise EngineError("engine_job_type_invalid", "The scientific job type is not executable by this adapter.")
        plugin = self.registry.get(job.engine_name)
        manifest = plugin.manifest()
        if manifest.version != job.engine_version:
            raise EngineError("engine_version_mismatch", "The selected engine version is not available for this job.")
        normalized = plugin.validate_input(job.input_payload)
        if normalized != job.input_payload:
            raise EngineError("engine_input_invalid", "Persisted scientific job input no longer matches the validated engine contract.")
        started_at = datetime.now(UTC).isoformat()
        started_clock = time.monotonic()
        execution = ScientificJobExecution(
            job_id=job.job_id,
            lease_owner=lease_owner,
            engine_name=manifest.engine_id,
            engine_version=manifest.version,
            attempt=job.attempt,
            started_at=started_at,
        )
        context = EngineExecutionContext(
            run_id=f"scientific-job-run-{uuid.uuid4().hex}",
            cancelled=cancellation_check,
            resource_limits={"output_bytes_max": MAX_JOB_RESULT_BYTES, "job_id": job.job_id},
        )
        result = plugin.execute(job.input_payload, context)
        completed_at = datetime.now(UTC).isoformat()
        duration_ms = round((time.monotonic() - started_clock) * 1000)
        raw = {
            "summary": plugin.summarize(result),
            "values": result.values,
            "series": result.series,
            "events": result.events,
            "warnings": result.warnings,
            "assumptions": result.assumptions,
            "units": result.units,
            "artifacts": result.artifacts,
            "visualization": validate_visualization(plugin.build_visualization(result)),
            "evidence": result.evidence,
            "execution": {
                "job_id": execution.job_id,
                "lease_owner": execution.lease_owner,
                "attempt": execution.attempt,
                "started_at": execution.started_at,
                "completed_at": completed_at,
                "duration_ms": duration_ms,
                "runner_version": runner_version,
                "schema_version": execution.schema_version,
            },
        }
        raw["reproducibility"] = record(
            engine_id=manifest.engine_id,
            engine_version=manifest.version,
            normalized_input=job.input_payload,
            output=raw,
            deterministic=manifest.deterministic,
            seed=None,
            backend=manifest.execution_backend,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            resource_limits=context.resource_limits,
            links={"campaign_id": job.campaign_id, "job_id": job.job_id, "experiment_id": job.experiment_id},
            warnings=result.warnings,
            assumptions=result.assumptions,
        )
        encoded = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        if len(encoded) > MAX_JOB_RESULT_BYTES:
            raise EngineError("engine_artifact_too_large", "The structured scientific job result exceeds the runtime output limit.")
        return ScientificJobResult(
            job_id=job.job_id,
            engine_name=manifest.engine_id,
            engine_version=manifest.version,
            result_payload=raw,
            runner_version=runner_version,
        )

    @staticmethod
    def failure_from_exception(job_id: str, error: Exception) -> tuple[str, str, bool]:
        if isinstance(error, EngineError):
            if error.code == "engine_cancelled":
                return ScientificJobFailureClass.CANCELLED.value, error.message, False
            if error.code in {"engine_execution_failed", "engine_runner_offline"}:
                return ScientificJobFailureClass.ENGINE_TRANSIENT.value, error.message, True
            return ScientificJobFailureClass.ENGINE_PERMANENT.value, error.message, False
        return (
            ScientificJobFailureClass.INTERNAL.value,
            "The trusted scientific engine could not complete this job.",
            True,
        )


class ScientificJobWorker:
    """Internal worker facade. It is deliberately not an MCP public tool."""

    def __init__(
        self,
        runtime: ScientificJobRuntime,
        adapter: ScientificEngineJobAdapter,
        *,
        heartbeat_interval_seconds: int | None = None,
    ) -> None:
        if heartbeat_interval_seconds is not None and not 1 <= heartbeat_interval_seconds <= 120:
            raise ValueError("heartbeat_interval_seconds must be between 1 and 120")
        self.runtime = runtime
        self.adapter = adapter
        self.heartbeat_interval_seconds = heartbeat_interval_seconds

    def run_once(self, *, worker_id: str, lease_seconds: int = 60) -> ScientificJob | None:
        lease = self.runtime.acquire_next(worker_id=worker_id, lease_seconds=lease_seconds)
        if lease is None:
            return None
        job, lease_token = lease
        try:
            running = self.runtime.start(job.job_id, worker_id=worker_id, lease_token=lease_token)
        except ScientificJobLeaseError:
            # Cancellation or a lost lease is an expected cooperative-stop path;
            # the durable aggregate contains the audit result already.
            return self.runtime.get(job.job_id)
        stop_heartbeat = Event()
        lease_lost = Event()
        configured_heartbeat_interval = self.heartbeat_interval_seconds or max(5, lease_seconds // 3)
        heartbeat_interval = min(configured_heartbeat_interval, max(1, lease_seconds // 2))

        def heartbeat() -> None:
            while not stop_heartbeat.wait(heartbeat_interval):
                try:
                    self.runtime.heartbeat(
                        running.job_id,
                        worker_id=worker_id,
                        lease_token=lease_token,
                        lease_seconds=lease_seconds,
                    )
                except Exception:
                    # A worker that cannot renew must stop cooperatively rather
                    # than try to complete using a stale lease capability.
                    lease_lost.set()
                    return

        heartbeat_thread = Thread(
            target=heartbeat,
            name=f"scientific-job-heartbeat-{running.job_id}",
            daemon=True,
        )
        heartbeat_thread.start()
        try:
            result = self.adapter.execute(
                running,
                lease_owner=worker_id,
                cancellation_check=lambda: lease_lost.is_set()
                or self.runtime.is_cancellation_requested(
                    running.job_id, worker_id=worker_id, lease_token=lease_token
                ),
            )
        except Exception as error:
            stop_heartbeat.set()
            heartbeat_thread.join(timeout=1)
            if lease_lost.is_set():
                return self.runtime.get(running.job_id)
            failure_class, safe_error, retryable = self.adapter.failure_from_exception(running.job_id, error)
            return self.runtime.fail(
                running.job_id,
                worker_id=worker_id,
                lease_token=lease_token,
                failure_class=failure_class,
                safe_error=safe_error,
                retryable=retryable,
            )
        stop_heartbeat.set()
        heartbeat_thread.join(timeout=1)
        if lease_lost.is_set():
            return self.runtime.get(running.job_id)
        return self.runtime.complete(
            running.job_id,
            worker_id=worker_id,
            lease_token=lease_token,
            result=result,
        )

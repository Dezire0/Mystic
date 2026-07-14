from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import json
import time
import uuid
from typing import Any

from .base import EngineExecutionContext
from .errors import EngineError
from .registry import EngineRegistry
from .reproducibility import record
from .visualization import validate_visualization


MAX_OUTPUT_BYTES = 262_144


@dataclass
class EngineJob:
    job_id: str
    engine_id: str
    input_payload: dict[str, Any]
    session_id: str = ""
    experiment_id: str = ""
    scene_id: str = ""
    seed: int | None = None
    status: str = "pending"
    cancellation_requested: bool = False
    claimed_by: str = ""
    attempts: int = 0
    safe_error: str = ""


class InMemoryEngineQueue:
    """Test/local runner queue. Production claiming is supplied by Supabase RPCs."""
    def __init__(self) -> None: self.jobs: dict[str, EngineJob] = {}; self.results: dict[str, dict[str, Any]] = {}
    def create(self, job: EngineJob) -> EngineJob: self.jobs[job.job_id] = job; return job
    def claim_next(self, runner_id: str) -> EngineJob | None:
        for job in sorted(self.jobs.values(), key=lambda item: item.job_id):
            if job.status == "pending" and not job.cancellation_requested:
                job.status="running"; job.claimed_by=runner_id; job.attempts += 1; return job
        return None
    def request_cancellation(self, job_id: str) -> EngineJob:
        job=self.jobs[job_id]; job.cancellation_requested=True
        if job.status == "pending": job.status="cancelled"
        return job


class EngineRuntime:
    def __init__(self, registry: EngineRegistry, queue: InMemoryEngineQueue | None = None) -> None:
        self.registry, self.queue = registry, queue or InMemoryEngineQueue()
    def create_job(self, *, engine_id: str, input_payload: dict[str, Any], session_id: str = "", experiment_id: str = "", scene_id: str = "", seed: int | None = None) -> dict[str, Any]:
        plugin=self.registry.get(engine_id); normalized=plugin.validate_input(input_payload); estimate=plugin.estimate(normalized)
        if estimate.resource_class in {"large","external_required"}: raise EngineError("external_compute_required", "This engine requires an external compute backend.")
        job=EngineJob(job_id=f"engine-job-{uuid.uuid4().hex}",engine_id=engine_id,input_payload=normalized,session_id=session_id,experiment_id=experiment_id,scene_id=scene_id,seed=seed)
        self.queue.create(job)
        return {"job_id":job.job_id,"status":job.status,"selected_engine":engine_id,"estimated_resource_class":estimate.resource_class,"validation":"valid","polling_interval_seconds":2,"next_action":"Poll lab_engine_job_get or wait for the trusted runner."}
    def execute_next(self, runner_id: str = "local-trusted-runner") -> dict[str, Any] | None:
        job=self.queue.claim_next(runner_id)
        if job is None: return None
        start_clock=time.monotonic(); started=datetime.now(UTC).isoformat()
        try:
            plugin=self.registry.get(job.engine_id); context=EngineExecutionContext(run_id=f"run-{uuid.uuid4().hex}",seed=job.seed,cancelled=lambda: job.cancellation_requested,resource_limits={"output_bytes_max":MAX_OUTPUT_BYTES})
            result=plugin.execute(job.input_payload,context); visualization=validate_visualization(plugin.build_visualization(result)); completed=datetime.now(UTC).isoformat(); duration=round((time.monotonic()-start_clock)*1000)
            raw={"summary":plugin.summarize(result),"values":result.values,"series":result.series,"events":result.events,"warnings":result.warnings,"assumptions":result.assumptions,"units":result.units,"artifacts":result.artifacts,"visualization":visualization,"evidence":result.evidence}
            if len(json.dumps(raw, separators=(",",":"), allow_nan=False).encode()) > MAX_OUTPUT_BYTES: raise EngineError("engine_artifact_too_large","The structured engine result exceeds the Phase 2A output limit.")
            reproducibility=record(engine_id=job.engine_id,engine_version=plugin.manifest().version,normalized_input=job.input_payload,output=raw,deterministic=plugin.manifest().deterministic,seed=job.seed,backend=plugin.manifest().execution_backend,started_at=started,completed_at=completed,duration_ms=duration,resource_limits=context.resource_limits,links={"session_id":job.session_id,"experiment_id":job.experiment_id,"scene_id":job.scene_id,"parent_run_id":""},warnings=result.warnings,assumptions=result.assumptions)
            response={"run_id":context.run_id,"engine_id":job.engine_id,"engine_version":plugin.manifest().version,"status":"completed","safe_error":"","started_at":started,"completed_at":completed,"duration_ms":duration,"reproducibility":reproducibility,**raw}
            job.status="completed"; self.queue.results[job.job_id]=response; return response
        except EngineError as error:
            job.status="cancelled" if error.code=="engine_cancelled" else "failed"; job.safe_error=error.message
            return {"job_id":job.job_id,"engine_id":job.engine_id,"status":job.status,"safe_error":error.message,"error":error.safe_payload()}
        except Exception:
            job.status="failed"; job.safe_error="The trusted engine could not complete this job."
            return {"job_id":job.job_id,"engine_id":job.engine_id,"status":"failed","safe_error":job.safe_error,"error":{"code":"engine_execution_failed","message":job.safe_error,"retryable":False,"next_action":"Review validated engine input."}}

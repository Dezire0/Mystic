from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Event, Lock
from time import monotonic
from typing import Callable, Protocol

from mystic.lab.scientific_job import ScientificJob, ScientificJobStatus
from mystic.lab.scientific_job_adapter import ScientificEngineJobAdapter, ScientificJobWorker
from mystic.lab.scientific_job_runtime import ScientificJobRuntime

from .backoff import IdlePollingBackoff
from .config import ScientificWorkerConfig
from .health import WorkerHealth, WorkerState, engine_capabilities
from .metrics import WorkerMetrics
from .status_store import WorkerControlStorage, WorkerStatusStorage


WORKER_EVENT_TYPES = frozenset(
    {
        "job_succeeded",
        "job_failed",
        "job_cancelled",
        "job_dead_lettered",
        "result_attached",
        "evidence_available",
    }
)


class WorkerEventHook(Protocol):
    def __call__(self, event_type: str, job: ScientificJob) -> None: ...


@dataclass(frozen=True, slots=True)
class WorkerPollResult:
    acquired: int
    active_jobs: int
    reconciliation_actions: int


class ScientificJobWorkerService:
    """Bounded, stateless worker over the authoritative durable job runtime.

    It owns only transient tasks and opaque lease capabilities. Job state,
    outbox state, retries, campaign attachment, and audit history remain in
    ``ScientificJobRuntime``. This class is intentionally not an MCP handler.
    """

    def __init__(
        self,
        runtime: ScientificJobRuntime,
        config: ScientificWorkerConfig,
        *,
        adapter: ScientificEngineJobAdapter | None = None,
        hooks: tuple[WorkerEventHook, ...] = (),
    ) -> None:
        self.runtime = runtime
        self.config = config
        self.adapter = adapter or runtime.adapter
        self._worker = ScientificJobWorker(
            runtime,
            self.adapter,
            heartbeat_interval_seconds=config.heartbeat_interval_seconds,
        )
        engines, versions = engine_capabilities(runtime.registry)
        self.health = WorkerHealth(
            worker_id=config.worker_id,
            worker_version=config.worker_version,
            runtime_version=config.runtime_version,
            process_start_time=config.process_start_time,
            maximum_concurrency=config.maximum_concurrency,
            supported_engines=engines,
            supported_engine_versions=versions,
            resource_classes=config.resource_classes,
        )
        self.metrics = WorkerMetrics()
        self.status_storage = WorkerStatusStorage(config.root_path)
        self.control_storage = WorkerControlStorage(config.root_path)
        self._hooks = tuple(hooks)
        self._executor = ThreadPoolExecutor(
            max_workers=config.maximum_concurrency,
            thread_name_prefix="mystic-scientific-job",
        )
        self._tasks: dict[Future[ScientificJob], str] = {}
        self._lock = Lock()
        self._stopped = Event()
        self._last_reconciliation = 0.0
        self._backoff = IdlePollingBackoff(
            config.worker_id,
            initial_seconds=config.idle_poll_seconds,
            maximum_seconds=config.max_idle_poll_seconds,
        )
        self.health.status = WorkerState.READY
        self._persist_health()

    def safe_health(self) -> dict[str, object]:
        with self._lock:
            self.health.active_jobs = len(self._tasks)
            self._refresh_state_locked()
            return self.health.safe_payload()

    def safe_metrics(self) -> dict[str, object]:
        with self._lock:
            return self.metrics.snapshot(active_jobs=len(self._tasks), worker_capacity=self.config.maximum_concurrency)

    def request_drain(self) -> None:
        with self._lock:
            if self.health.status not in {WorkerState.STOPPED, WorkerState.UNHEALTHY}:
                self.health.status = WorkerState.DRAINING
        self._persist_health()

    def poll_once(self, *, wait_for_completion: bool = False) -> WorkerPollResult:
        """Reconcile bounded durable state and fill currently available capacity."""
        if self.control_storage.drain_requested(self.config.worker_id):
            self.request_drain()
        with self._lock:
            if self.health.status in {WorkerState.DRAINING, WorkerState.STOPPED, WorkerState.UNHEALTHY}:
                return WorkerPollResult(0, len(self._tasks), 0)
        self._reap_completed()
        reconciliation_actions = self._reconcile_if_due(force=False)
        started = monotonic()
        try:
            self.runtime.dispatch_outbox(limit=self.config.poll_batch_size)
            self._touch_backend()
        except Exception:
            self._mark_degraded("Durable job outbox dispatch could not be reached.")
            return WorkerPollResult(0, self._active_count(), reconciliation_actions)
        acquired = 0
        while acquired < self.config.poll_batch_size and self._active_count() < self.config.maximum_concurrency:
            started_acquire = monotonic()
            try:
                lease = self.runtime.acquire_next(
                    worker_id=self.config.worker_id,
                    lease_seconds=self.config.lease_seconds,
                )
                self._touch_backend()
            except Exception:
                self._mark_degraded("Durable job lease acquisition could not be completed.")
                break
            self.metrics.record_duration("acquisition_latency_ms", started_acquire)
            if lease is None:
                break
            job, lease_token = lease
            self.metrics.increment("jobs_acquired_total")
            future = self._executor.submit(self._execute_leased_job, job, lease_token)
            with self._lock:
                self._tasks[future] = job.job_id
                self.health.active_jobs = len(self._tasks)
                self.health.status = WorkerState.BUSY
            self._persist_health()
            acquired += 1
        self.metrics.record_duration("queue_wait_duration_ms", started)
        if wait_for_completion:
            self.wait_for_idle(timeout_seconds=self.config.graceful_shutdown_seconds)
        if acquired:
            self._backoff.reset()
        return WorkerPollResult(acquired, self._active_count(), reconciliation_actions)

    def run_forever(self) -> None:
        """Poll until draining/stopped; never busy-loop when the queue is idle."""
        while not self._stopped.is_set():
            result = self.poll_once()
            if self.health.status == WorkerState.DRAINING:
                break
            delay = self.config.idle_poll_seconds if result.acquired or result.active_jobs else self._backoff.next_delay()
            self._stopped.wait(delay)
        self.drain_and_stop()

    def reconcile_once(self) -> dict[str, int]:
        return self._reconcile_if_due(force=True, return_stats=True)

    def wait_for_idle(self, *, timeout_seconds: float) -> bool:
        with self._lock:
            futures = tuple(self._tasks)
        if not futures:
            return True
        _, not_done = wait(futures, timeout=max(0.0, timeout_seconds))
        self._reap_completed()
        return not not_done

    def drain_and_stop(self) -> bool:
        self.request_drain()
        self._stopped.set()
        drained = self.wait_for_idle(timeout_seconds=self.config.graceful_shutdown_seconds)
        self._executor.shutdown(wait=drained, cancel_futures=False)
        with self._lock:
            self.health.active_jobs = len(self._tasks)
            self.health.status = WorkerState.STOPPED
        self._persist_health()
        return drained

    def _execute_leased_job(self, job: ScientificJob, lease_token: str) -> ScientificJob:
        started = monotonic()
        try:
            self.metrics.increment("jobs_started_total")
            completed = self._worker.execute_acquired(
                job,
                worker_id=self.config.worker_id,
                lease_token=lease_token,
                lease_seconds=self.config.lease_seconds,
            )
            self._touch_backend()
            self._record_outcome(completed)
            return completed
        except Exception:
            self._mark_degraded("A trusted scientific job task ended unexpectedly.")
            raise
        finally:
            self.metrics.record_duration("execution_duration_ms", started)

    def _record_outcome(self, job: ScientificJob) -> None:
        if job.status == ScientificJobStatus.SUCCEEDED:
            self.metrics.increment("jobs_completed_total")
            with self._lock:
                self.health.completed_count += 1
            self._emit("job_succeeded", job)
            if job.attachment and job.attachment.status.value == "ATTACHED":
                self._emit("result_attached", job)
                self._emit("evidence_available", job)
        elif job.status == ScientificJobStatus.CANCELLED:
            self.metrics.increment("jobs_cancelled_total")
            with self._lock:
                self.health.cancelled_count += 1
            self._emit("job_cancelled", job)
        elif job.status == ScientificJobStatus.DEAD_LETTER:
            self.metrics.increment("jobs_dead_lettered_total")
            self._emit("job_dead_lettered", job)
        elif job.status == ScientificJobStatus.FAILED:
            self.metrics.increment("jobs_failed_total")
            with self._lock:
                self.health.failed_count += 1
            self._emit("job_failed", job)
        elif job.status in {ScientificJobStatus.LEASED, ScientificJobStatus.RUNNING}:
            # The facade only returns an active state after a heartbeat lost
            # ownership. It intentionally does not attempt stale completion.
            self.metrics.increment("leases_lost_total")
            self.metrics.increment("lease_renewal_failures_total")
            with self._lock:
                self.health.stale_lease_count += 1
        if any(event.event_type == "LEASE_EXPIRED_RECOVERED" for event in job.events):
            self.metrics.increment("leases_lost_total")
        self._persist_health()

    def _emit(self, event_type: str, job: ScientificJob) -> None:
        if event_type not in WORKER_EVENT_TYPES:
            raise ValueError("Unknown worker event hook")
        for hook in self._hooks:
            try:
                hook(event_type, job)
            except Exception:
                # Future orchestration hooks are observers. They cannot roll
                # back a durable worker or campaign result.
                self._mark_degraded("A worker event observer failed safely.")

    def _reconcile_if_due(self, *, force: bool, return_stats: bool = False) -> dict[str, int] | int:
        now = monotonic()
        if not force and now - self._last_reconciliation < self.config.reconciliation_interval_seconds:
            return {} if return_stats else 0
        try:
            stats = self.runtime.reconcile(limit=self.config.poll_batch_size)
            self._last_reconciliation = now
            actions = int(stats.get("reconciliation_actions", 0))
            self.metrics.increment("reconciliation_actions_total", actions)
            self.metrics.increment("jobs_retried_total", int(stats.get("retry_scheduled", 0)))
            with self._lock:
                self.health.reconciliation_count += 1
            self._touch_backend()
            return stats if return_stats else actions
        except Exception:
            self._mark_degraded("Durable scientific job reconciliation could not be completed.")
            return {} if return_stats else 0

    def _reap_completed(self) -> None:
        with self._lock:
            completed = [future for future in self._tasks if future.done()]
        for future in completed:
            try:
                future.result()
            except Exception:
                # The execution path already persisted safe failure state when
                # possible. Do not let one task stop unrelated leased jobs.
                self._mark_degraded("A worker task reported an unexpected safe failure.")
            finally:
                with self._lock:
                    self._tasks.pop(future, None)
                    self.health.active_jobs = len(self._tasks)
                    self._refresh_state_locked()
                self._persist_health()

    def _active_count(self) -> int:
        with self._lock:
            return len(self._tasks)

    def _touch_backend(self) -> None:
        now = datetime.now(UTC).isoformat()
        with self._lock:
            self.health.last_poll_at = now
            self.health.last_successful_backend_contact = now
            self.health.safe_last_error = ""
            if self.health.status == WorkerState.DEGRADED:
                self._refresh_state_locked()
        self._persist_health()

    def _mark_degraded(self, safe_error: str) -> None:
        with self._lock:
            if self.health.status not in {WorkerState.DRAINING, WorkerState.STOPPED}:
                self.health.status = WorkerState.DEGRADED
            self.health.safe_last_error = safe_error
        self._persist_health()

    def _persist_health(self) -> None:
        """Persist only the fixed-schema safe status record.

        A status-write failure is intentionally non-fatal for a leased task:
        lease/campaign correctness stays inside the durable job runtime.
        """
        try:
            self.status_storage.save(self.safe_health())
        except Exception:
            # This is monitoring only; recursively calling _mark_degraded here
            # could turn an observability disk failure into an execution loop.
            return

    def _refresh_state_locked(self) -> None:
        if self.health.status in {WorkerState.DRAINING, WorkerState.STOPPED, WorkerState.UNHEALTHY}:
            return
        self.health.status = WorkerState.BUSY if self._tasks else WorkerState.READY

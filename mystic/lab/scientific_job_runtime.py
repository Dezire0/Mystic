from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
from pathlib import Path
import secrets
from typing import Any, Callable, Protocol
import uuid

from mystic.lab.campaign import (
    CampaignConflictError,
    CampaignNotFoundError,
    IllegalCampaignTransition,
)
from mystic.lab.campaign_runtime import CampaignRuntime
from mystic.lab.engines import EngineRegistry, builtin_registry
from mystic.lab.scientific_job import (
    IllegalScientificJobTransition,
    ScientificJob,
    ScientificJobAttachment,
    ScientificJobAttachmentStatus,
    ScientificJobConflictError,
    ScientificJobFailure,
    ScientificJobFailureClass,
    ScientificJobIntegrityError,
    ScientificJobLease,
    ScientificJobLeaseError,
    ScientificJobNotFoundError,
    ScientificJobOutboxEvent,
    ScientificJobOutboxStatus,
    ScientificJobResult,
    ScientificJobStatus,
    TERMINAL_JOB_STATUSES,
    new_scientific_job_id,
    validate_job_transition,
)
from mystic.lab.scientific_job_adapter import ScientificEngineJobAdapter
from mystic.lab.scientific_job_storage import ScientificJobStorage


class ScientificJobDispatchTransport(Protocol):
    def dispatch(self, event: ScientificJobOutboxEvent, job: ScientificJob) -> bool: ...


class PollingScientificJobDispatchTransport:
    """Initial transport: durable pollers rediscover READY work without a broker."""

    def dispatch(self, event: ScientificJobOutboxEvent, job: ScientificJob) -> bool:
        del event, job
        return True


class ScientificJobRuntime:
    """Durable at-least-once job execution with logically exactly-once campaign attachment."""

    def __init__(
        self,
        root_path: str | Path,
        *,
        campaign_runtime: CampaignRuntime | None = None,
        storage: ScientificJobStorage | None = None,
        registry: EngineRegistry | None = None,
        transport: ScientificJobDispatchTransport | None = None,
        clock: Callable[[], datetime] | None = None,
        retry_base_seconds: int = 5,
        retry_max_seconds: int = 3_600,
        outbox_stale_seconds: int = 60,
    ) -> None:
        if not 1 <= retry_base_seconds <= retry_max_seconds <= 86_400:
            raise ValueError("retry intervals are invalid")
        if not 10 <= outbox_stale_seconds <= 86_400:
            raise ValueError("outbox_stale_seconds must be between 10 and 86400")
        self.root_path = Path(root_path)
        self.campaign_runtime = campaign_runtime or CampaignRuntime(self.root_path)
        self.storage = storage or ScientificJobStorage(self.root_path)
        self.registry = registry or builtin_registry()
        self.adapter = ScientificEngineJobAdapter(self.registry)
        self.transport = transport or PollingScientificJobDispatchTransport()
        self._clock = clock or (lambda: datetime.now(UTC))
        self.retry_base_seconds = retry_base_seconds
        self.retry_max_seconds = retry_max_seconds
        self.outbox_stale_seconds = outbox_stale_seconds

    def create_job(
        self,
        *,
        campaign_id: str,
        engine_name: str,
        input_payload: dict[str, Any],
        experiment_id: str = "",
        max_attempts: int = 3,
        idempotency_key: str = "",
        correlation_id: str = "",
    ) -> ScientificJob:
        self._validate_text("campaign_id", campaign_id, minimum=1, maximum=160)
        self._validate_text("engine_name", engine_name, minimum=1, maximum=160)
        self._validate_text("experiment_id", experiment_id, maximum=160)
        self._validate_text("idempotency_key", idempotency_key, maximum=160)
        self._validate_text("correlation_id", correlation_id, maximum=160)
        if not isinstance(max_attempts, int) or not 1 <= max_attempts <= 10:
            raise ValueError("max_attempts must be between 1 and 10")
        campaign = self.campaign_runtime.get(campaign_id)
        request = self.adapter.prepare_request(
            campaign_id=campaign_id,
            campaign_revision=campaign.revision,
            engine_name=engine_name,
            input_payload=input_payload,
            experiment_id=experiment_id,
            correlation_id=correlation_id,
        )
        job_id = (
            f"job_{uuid.uuid5(uuid.NAMESPACE_URL, f'mystic-scientific-job:{campaign_id}:{idempotency_key}').hex}"
            if idempotency_key
            else new_scientific_job_id()
        )
        if idempotency_key:
            try:
                existing = self.storage.load(job_id)
            except ScientificJobNotFoundError:
                existing = None
            if existing is not None:
                if (
                    existing.idempotency_key == idempotency_key
                    and existing.input_hash == request.input_hash
                    and existing.engine_name == request.engine_name
                    and existing.engine_version == request.engine_version
                    and existing.campaign_id == campaign_id
                    and existing.experiment_id == experiment_id
                    and existing.max_attempts == max_attempts
                ):
                    return self._ensure_campaign_intent(existing.job_id)
                raise ScientificJobConflictError("Idempotency key already belongs to another scientific job")
        now = self._now()
        job = ScientificJob(
            job_id=job_id,
            campaign_id=campaign_id,
            campaign_revision=request.campaign_revision,
            job_type=request.job_type,
            engine_name=request.engine_name,
            engine_version=request.engine_version,
            input_payload=request.input_payload,
            input_hash=request.input_hash,
            max_attempts=max_attempts,
            created_at=self._iso(now),
            updated_at=self._iso(now),
            ready_at=self._iso(now),
            idempotency_key=idempotency_key,
            correlation_id=correlation_id or job_id,
            experiment_id=experiment_id,
        )
        job.outbox_events.append(
            ScientificJobOutboxEvent(job_id=job_id, payload_hash=job.input_hash, available_at=self._iso(now))
        )
        job.append_event(
            "JOB_PERSISTED",
            "Scientific job and durable dispatch intent persisted.",
            metadata={"campaign_revision": campaign.revision, "engine_name": job.engine_name},
        )
        try:
            self.storage.create(job)
        except ScientificJobConflictError:
            if not idempotency_key:
                raise
            existing = self.storage.load(job_id)
            if (
                existing.idempotency_key == idempotency_key
                and existing.input_hash == request.input_hash
                and existing.engine_name == request.engine_name
                and existing.engine_version == request.engine_version
                and existing.campaign_id == campaign_id
                and existing.experiment_id == experiment_id
                and existing.max_attempts == max_attempts
            ):
                return self._ensure_campaign_intent(existing.job_id)
            raise ScientificJobConflictError("Idempotency key already belongs to another scientific job")
        return self._ensure_campaign_intent(job_id)

    def get(self, job_id: str) -> ScientificJob:
        return self.storage.load(job_id)

    def list(
        self,
        *,
        limit: int = 50,
        status: str | None = None,
        campaign_id: str | None = None,
    ) -> list[ScientificJob]:
        if status:
            ScientificJobStatus(status)
        return self.storage.list(limit=limit, status=status, campaign_id=campaign_id)

    def acquire_next(self, *, worker_id: str, lease_seconds: int = 60) -> tuple[ScientificJob, str] | None:
        for job in sorted(self.storage.list(limit=500, status=ScientificJobStatus.READY.value), key=lambda item: (item.ready_at, item.job_id)):
            acquired = self.acquire(job.job_id, worker_id=worker_id, lease_seconds=lease_seconds)
            if acquired is not None:
                return acquired
        return None

    def acquire(self, job_id: str, *, worker_id: str, lease_seconds: int = 60) -> tuple[ScientificJob, str] | None:
        self._validate_text("worker_id", worker_id, minimum=1, maximum=160)
        self._validate_lease_seconds(lease_seconds)
        now = self._now()
        lease_token = secrets.token_urlsafe(32)
        token_hash = self._token_hash(lease_token)

        def mutation(job: ScientificJob) -> tuple[bool, str]:
            if job.status != ScientificJobStatus.READY or self._parse_time(job.ready_at) > now:
                return False, ""
            if job.cancellation_requested:
                self._transition(job, ScientificJobStatus.CANCELLED, "JOB_CANCELLED", "Ready job cancellation accepted.")
                self._ack_terminal_outbox(job, now)
                return False, ""
            if job.attempt >= job.max_attempts:
                raise ScientificJobIntegrityError("Ready scientific job exceeded its retry budget")
            job.attempt += 1
            job.lease_owner = worker_id
            job.lease_token_hash = token_hash
            job.lease_acquired_at = self._iso(now)
            job.lease_expires_at = self._iso(now + timedelta(seconds=lease_seconds))
            job.lease_history.append(
                ScientificJobLease(
                    job_id=job.job_id,
                    lease_owner=worker_id,
                    token_hash=token_hash,
                    acquired_at=job.lease_acquired_at,
                    expires_at=job.lease_expires_at,
                )
            )
            self._transition(
                job,
                ScientificJobStatus.LEASED,
                "LEASE_ACQUIRED",
                "Scientific job leased to one worker.",
                metadata={"lease_owner": worker_id, "attempt": job.attempt},
            )
            self._ack_dispatch_outbox(job, now)
            return True, lease_token

        persisted, result = self.storage.mutate(job_id, mutation)
        if not result[0]:
            if persisted.status == ScientificJobStatus.DEAD_LETTER:
                self._attempt_failure_attachment(persisted.job_id)
            return None
        return persisted, result[1]

    def start(self, job_id: str, *, worker_id: str, lease_token: str) -> ScientificJob:
        now = self._now()

        def mutation(job: ScientificJob) -> str:
            self._require_current_lease(job, worker_id, lease_token, now, required_status=ScientificJobStatus.LEASED)
            if job.cancellation_requested:
                self._release_lease(job, reason="cancelled", now=now)
                self._transition(job, ScientificJobStatus.CANCELLED, "JOB_CANCELLED", "Leased job cancellation accepted before execution.")
                return "cancelled"
            job.started_at = self._iso(now)
            self._transition(job, ScientificJobStatus.RUNNING, "JOB_STARTED", "Scientific engine execution started.")
            return "running"

        persisted, result = self.storage.mutate(job_id, mutation)
        if result == "cancelled":
            raise ScientificJobLeaseError("Scientific job was cancelled before execution")
        return persisted

    def heartbeat(self, job_id: str, *, worker_id: str, lease_token: str, lease_seconds: int = 60) -> ScientificJob:
        self._validate_lease_seconds(lease_seconds)
        now = self._now()

        def mutation(job: ScientificJob) -> None:
            self._require_current_lease(job, worker_id, lease_token, now)
            if job.cancellation_requested:
                raise ScientificJobLeaseError("Scientific job cancellation was requested")
            job.lease_expires_at = self._iso(now + timedelta(seconds=lease_seconds))
            active = job.active_lease
            if active is None:
                raise ScientificJobIntegrityError("Scientific job has no active lease history")
            active.expires_at = job.lease_expires_at
            active.heartbeat_count += 1
            self._touch(job)
            job.append_event("LEASE_HEARTBEAT", "Scientific job lease renewed.", metadata={"lease_owner": worker_id})

        persisted, _ = self.storage.mutate(job_id, mutation)
        return persisted

    def complete(
        self,
        job_id: str,
        *,
        worker_id: str,
        lease_token: str,
        result: ScientificJobResult,
        attempt_attachment: bool = True,
    ) -> ScientificJob:
        if result.job_id != job_id:
            raise ScientificJobConflictError("Scientific job result belongs to another job")
        now = self._now()
        supplied_hash = self._token_hash(lease_token)

        def mutation(job: ScientificJob) -> str:
            if job.status == ScientificJobStatus.SUCCEEDED:
                if job.completed_lease_owner != worker_id or not hmac.compare_digest(job.completed_lease_token_hash, supplied_hash):
                    raise ScientificJobLeaseError("Stale lease token cannot replay scientific job completion")
                if job.result_hash != result.result_hash:
                    job.conflicting_result_count += 1
                    job.duplicate_completion_rejected_count += 1
                    self._touch(job)
                    job.append_event("RESULT_CONFLICT_REJECTED", "Conflicting duplicate result rejected.")
                    return "conflict"
                job.duplicate_completion_count += 1
                job.result_replay_count += 1
                self._touch(job)
                job.append_event("RESULT_REPLAY_IGNORED", "Duplicate scientific job completion replay ignored.")
                return "replay"
            self._require_current_lease(job, worker_id, lease_token, now, required_status=ScientificJobStatus.RUNNING)
            if job.cancellation_requested:
                self._release_lease(job, reason="cancelled", now=now)
                self._transition(job, ScientificJobStatus.CANCELLED, "RESULT_REJECTED_AFTER_CANCEL", "Result rejected because cancellation was requested.")
                return "cancelled"
            if result.engine_name != job.engine_name or result.engine_version != job.engine_version:
                raise ScientificJobConflictError("Scientific job result engine provenance does not match the job")
            job.result = result
            job.result_hash = result.result_hash
            job.finished_at = self._iso(now)
            job.completed_lease_owner = worker_id
            job.completed_lease_token_hash = supplied_hash
            job.attachment = ScientificJobAttachment(
                job_id=job.job_id,
                campaign_id=job.campaign_id,
                campaign_revision=job.attachment_campaign_revision,
                attachment_key=f"scientific-job:{job.job_id}:{result.result_hash}",
                result_hash=result.result_hash,
            )
            self._release_lease(job, reason="completed", now=now)
            self._transition(
                job,
                ScientificJobStatus.SUCCEEDED,
                "JOB_SUCCEEDED",
                "Scientific engine result persisted pending campaign attachment.",
                metadata={"result_hash": result.result_hash},
            )
            return "completed"

        persisted, outcome = self.storage.mutate(job_id, mutation)
        if outcome == "conflict":
            raise ScientificJobConflictError("Conflicting duplicate scientific job result was rejected")
        if outcome == "cancelled":
            raise ScientificJobLeaseError("Scientific job result was rejected after cancellation")
        if attempt_attachment:
            return self._attempt_result_attachment(persisted.job_id)
        return persisted

    def fail(
        self,
        job_id: str,
        *,
        worker_id: str,
        lease_token: str,
        failure_class: str,
        safe_error: str,
        retryable: bool,
    ) -> ScientificJob:
        now = self._now()
        failure = ScientificJobFailure(
            job_id=job_id,
            failure_class=failure_class,
            safe_error=safe_error,
            retryable=retryable,
        )
        supplied_hash = self._token_hash(lease_token)

        def mutation(job: ScientificJob) -> str:
            if job.status == ScientificJobStatus.FAILED and job.failure is not None:
                if job.completed_lease_owner != worker_id or not hmac.compare_digest(job.completed_lease_token_hash, supplied_hash):
                    raise ScientificJobLeaseError("Stale lease token cannot replay scientific job failure")
                if job.failure.failure_class != failure.failure_class or job.failure.safe_error != failure.safe_error:
                    raise ScientificJobConflictError("Conflicting duplicate scientific job failure was rejected")
                self._touch(job)
                job.append_event("FAILURE_REPLAY_IGNORED", "Duplicate scientific job failure replay ignored.")
                return "replay"
            self._require_current_lease(job, worker_id, lease_token, now, required_status=ScientificJobStatus.RUNNING)
            if job.cancellation_requested or failure.failure_class == ScientificJobFailureClass.CANCELLED.value:
                self._release_lease(job, reason="cancelled", now=now)
                self._transition(job, ScientificJobStatus.CANCELLED, "JOB_CANCELLED", "Running job stopped cooperatively after cancellation.")
                return "cancelled"
            job.failure = failure
            job.failure_class = failure.failure_class
            job.error = failure.safe_error
            job.finished_at = self._iso(now)
            job.completed_lease_owner = worker_id
            job.completed_lease_token_hash = supplied_hash
            self._release_lease(job, reason="failed", now=now)
            self._transition(
                job,
                ScientificJobStatus.FAILED,
                "JOB_FAILED",
                "Scientific engine failure persisted for deterministic retry evaluation.",
                metadata={"failure_class": failure.failure_class, "retryable": retryable},
            )
            return "failed"

        persisted, _ = self.storage.mutate(job_id, mutation)
        return persisted

    def cancel(self, job_id: str) -> ScientificJob:
        now = self._now()

        def mutation(job: ScientificJob) -> None:
            if job.status == ScientificJobStatus.CANCELLED:
                return
            if job.status in {ScientificJobStatus.SUCCEEDED, ScientificJobStatus.DEAD_LETTER}:
                raise IllegalScientificJobTransition("Terminal scientific jobs cannot be cancelled")
            if job.status in {ScientificJobStatus.PENDING, ScientificJobStatus.READY, ScientificJobStatus.RETRY_WAIT, ScientificJobStatus.FAILED}:
                self._release_lease(job, reason="cancelled", now=now)
                self._transition(job, ScientificJobStatus.CANCELLED, "JOB_CANCELLED", "Scientific job cancellation accepted.")
                self._ack_terminal_outbox(job, now)
                return
            if job.status in {ScientificJobStatus.LEASED, ScientificJobStatus.RUNNING}:
                if job.cancellation_requested:
                    return
                job.cancellation_requested = True
                self._touch(job)
                job.append_event("CANCELLATION_REQUESTED", "Worker must stop cooperatively before a result can attach.")
                return
            raise IllegalScientificJobTransition(f"Cannot cancel scientific job from {job.status.value}")

        persisted, _ = self.storage.mutate(job_id, mutation)
        return persisted

    def retry(self, job_id: str) -> ScientificJob:
        now = self._now()

        def mutation(job: ScientificJob) -> None:
            if job.status == ScientificJobStatus.RETRY_WAIT:
                return
            if job.status != ScientificJobStatus.FAILED:
                raise IllegalScientificJobTransition(f"Cannot retry scientific job from {job.status.value}")
            if job.failure is None or not job.failure.retryable or job.attempt >= job.max_attempts:
                self._transition(job, ScientificJobStatus.DEAD_LETTER, "JOB_DEAD_LETTERED", "Scientific job cannot be retried safely.")
                return
            self._schedule_retry(job, now, event_type="RETRY_SCHEDULED")

        persisted, _ = self.storage.mutate(job_id, mutation)
        if persisted.status == ScientificJobStatus.DEAD_LETTER:
            return self._attempt_failure_attachment(persisted.job_id)
        return persisted

    def is_cancellation_requested(self, job_id: str, *, worker_id: str, lease_token: str) -> bool:
        try:
            job = self.get(job_id)
            self._require_current_lease(job, worker_id, lease_token, self._now())
            return job.cancellation_requested
        except ScientificJobLeaseError:
            # A worker that lost its lease must stop instead of continuing with a stale capability.
            return True

    def dispatch_outbox(self, *, limit: int = 100) -> dict[str, int]:
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500")
        now = self._now()
        dispatched = 0
        failed = 0
        for job in self.storage.list(limit=500):
            if dispatched + failed >= limit or job.status != ScientificJobStatus.READY:
                continue
            for event in job.outbox_events:
                if dispatched + failed >= limit:
                    break
                if event.status not in {ScientificJobOutboxStatus.PENDING, ScientificJobOutboxStatus.FAILED}:
                    continue
                if self._parse_time(event.available_at) > now:
                    continue
                selected = self._mark_outbox_dispatched(job.job_id, event.event_id, now)
                if selected is None:
                    continue
                selected_job, selected_event = selected
                try:
                    accepted = self.transport.dispatch(selected_event, selected_job)
                except Exception:
                    accepted = False
                if accepted:
                    dispatched += 1
                else:
                    failed += 1
                    self._mark_outbox_failed(selected_job.job_id, selected_event.event_id, "Dispatch transport did not accept the event.")
        return {"dispatched": dispatched, "failed": failed}

    def reconcile(self, *, limit: int = 500) -> dict[str, int]:
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500")
        now = self._now()
        stats = {
            "jobs_scanned": 0,
            "campaign_intents_recovered": 0,
            "expired_leases_recovered": 0,
            "orphaned_running_jobs": 0,
            "retry_scheduled": 0,
            "retry_released": 0,
            "stale_outbox_requeued": 0,
            "terminal_outbox_acknowledged": 0,
            "result_attachments_completed": 0,
            "result_attachments_rejected": 0,
            "failure_attachments_completed": 0,
        }
        for original in self.storage.list(limit=limit):
            stats["jobs_scanned"] += 1
            job = self.get(original.job_id)
            if job.status == ScientificJobStatus.PENDING:
                before = job.revision
                job = self._ensure_campaign_intent(job.job_id)
                if job.revision != before and job.status == ScientificJobStatus.READY:
                    stats["campaign_intents_recovered"] += 1
            if job.status in {ScientificJobStatus.LEASED, ScientificJobStatus.RUNNING} and job.lease_expires_at and self._parse_time(job.lease_expires_at) <= now:
                was_running = job.status == ScientificJobStatus.RUNNING
                job = self._reclaim_expired_lease(job.job_id, now)
                stats["expired_leases_recovered"] += 1
                if was_running:
                    stats["orphaned_running_jobs"] += 1
            if job.status == ScientificJobStatus.FAILED:
                before = job.status
                job = self.retry(job.job_id)
                if before != job.status and job.status == ScientificJobStatus.RETRY_WAIT:
                    stats["retry_scheduled"] += 1
            if job.status == ScientificJobStatus.RETRY_WAIT and self._parse_time(job.ready_at) <= now:
                job = self._release_retry_wait(job.job_id, now)
                if job.status == ScientificJobStatus.READY:
                    stats["retry_released"] += 1
            if job.status == ScientificJobStatus.SUCCEEDED and job.attachment and job.attachment.status == ScientificJobAttachmentStatus.PENDING:
                job = self._attempt_result_attachment(job.job_id)
                if job.attachment and job.attachment.status == ScientificJobAttachmentStatus.ATTACHED:
                    stats["result_attachments_completed"] += 1
                elif job.attachment and job.attachment.status == ScientificJobAttachmentStatus.REJECTED:
                    stats["result_attachments_rejected"] += 1
            if job.status == ScientificJobStatus.DEAD_LETTER and not job.failure_attachment_state:
                job = self._attempt_failure_attachment(job.job_id)
                if job.failure_attachment_state == "ATTACHED":
                    stats["failure_attachments_completed"] += 1
            if job.status in TERMINAL_JOB_STATUSES:
                if self._has_unacknowledged_outbox(job):
                    self._ack_terminal_outbox_persisted(job.job_id, now)
                    stats["terminal_outbox_acknowledged"] += 1
            else:
                for event in job.outbox_events:
                    if (
                        event.status == ScientificJobOutboxStatus.DISPATCHED
                        and event.dispatched_at
                        and self._parse_time(event.dispatched_at) <= now - timedelta(seconds=self.outbox_stale_seconds)
                    ):
                        self._requeue_stale_outbox(job.job_id, event.event_id, now)
                        stats["stale_outbox_requeued"] += 1
        dispatch = self.dispatch_outbox(limit=limit)
        stats["outbox_dispatched"] = dispatch["dispatched"]
        stats["outbox_dispatch_failed"] = dispatch["failed"]
        stats["reconciliation_actions"] = sum(value for key, value in stats.items() if key != "jobs_scanned")
        return stats

    def statistics(self, *, campaign_id: str | None = None) -> dict[str, Any]:
        jobs = self.storage.list(limit=500, campaign_id=campaign_id)
        counts = {status.value.lower(): 0 for status in ScientificJobStatus}
        for job in jobs:
            counts[job.status.value.lower()] += 1
        attempts = [job.attempt for job in jobs]
        return {
            "campaign_id": campaign_id or "",
            "job_count": len(jobs),
            "pending_jobs": counts["pending"],
            "ready_jobs": counts["ready"],
            "leased_jobs": counts["leased"],
            "running_jobs": counts["running"],
            "succeeded_jobs": counts["succeeded"],
            "failed_jobs": counts["failed"],
            "retry_wait_jobs": counts["retry_wait"],
            "cancelled_jobs": counts["cancelled"],
            "dead_letter_jobs": counts["dead_letter"],
            "expired_leases_recovered": sum(1 for job in jobs for event in job.events if event.event_type == "LEASE_EXPIRED_RECOVERED"),
            "duplicate_completions_rejected": sum(job.duplicate_completion_rejected_count for job in jobs),
            "duplicate_completions_ignored": sum(job.duplicate_completion_count for job in jobs),
            "result_replays_ignored": sum(job.result_replay_count for job in jobs),
            "conflicting_results_rejected": sum(job.conflicting_result_count for job in jobs),
            "reconciliation_actions": sum(job.reconciliation_count for job in jobs),
            "average_attempts": round(sum(attempts) / len(attempts), 3) if attempts else 0.0,
        }

    def public_payload(self, job: ScientificJob) -> dict[str, Any]:
        return {
            "job_id": job.job_id,
            "campaign_id": job.campaign_id,
            "campaign_revision": job.campaign_revision,
            "attachment_campaign_revision": job.attachment_campaign_revision,
            "job_type": job.job_type,
            "engine_name": job.engine_name,
            "engine_version": job.engine_version,
            "input_metadata": {"hash": job.input_hash, "keys": sorted(job.input_payload), "byte_limit": 131_072},
            "status": job.status.value,
            "attempt": job.attempt,
            "max_attempts": job.max_attempts,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
            "ready_at": job.ready_at,
            "lease": {
                "owner": job.lease_owner,
                "acquired_at": job.lease_acquired_at,
                "expires_at": job.lease_expires_at,
                "cancellation_requested": job.cancellation_requested,
            },
            "started_at": job.started_at,
            "finished_at": job.finished_at,
            "result_metadata": {
                "hash": job.result_hash,
                "keys": sorted(job.result.result_payload) if job.result else [],
                "engine_name": job.result.engine_name if job.result else "",
                "engine_version": job.result.engine_version if job.result else "",
            },
            "error": job.error,
            "failure_class": job.failure_class,
            "failure": asdict(job.failure) if job.failure else None,
            "attachment": asdict(job.attachment) if job.attachment else None,
            "failure_attachment_state": job.failure_attachment_state,
            "failure_attachment_error": job.failure_attachment_error,
            "lease_history": [
                {
                    "lease_id": lease.lease_id,
                    "lease_owner": lease.lease_owner,
                    "acquired_at": lease.acquired_at,
                    "expires_at": lease.expires_at,
                    "heartbeat_count": lease.heartbeat_count,
                    "released_at": lease.released_at,
                    "release_reason": lease.release_reason,
                }
                for lease in job.lease_history
            ],
            "outbox": [
                {"event_id": event.event_id, "status": event.status.value, "attempt": event.attempt, "dispatched_at": event.dispatched_at, "acknowledged_at": event.acknowledged_at, "safe_error": event.safe_error}
                for event in job.outbox_events
            ],
            "events": [asdict(event) for event in job.events[-200:]],
            "provenance": {
                "input_hash": job.input_hash,
                "result_hash": job.result_hash,
                "campaign_revision": job.campaign_revision,
                "job_revision": job.revision,
                "schema_version": job.schema_version,
            },
            "revision": job.revision,
            "schema_version": job.schema_version,
        }

    def _ensure_campaign_intent(self, job_id: str) -> ScientificJob:
        job = self.get(job_id)
        if job.status != ScientificJobStatus.PENDING:
            return job
        try:
            reference = self.campaign_runtime.register_scientific_job_intent(
                campaign_id=job.campaign_id,
                job_id=job.job_id,
                job_type=job.job_type,
                engine_name=job.engine_name,
                engine_version=job.engine_version,
                source_campaign_revision=job.campaign_revision,
                experiment_id=job.experiment_id,
                idempotency_key=f"scientific-job-intent:{job.job_id}",
            )
        except (CampaignConflictError, CampaignNotFoundError, IllegalCampaignTransition) as error:
            safe_error = self._safe_error(error)

            def cancel(job_to_cancel: ScientificJob) -> None:
                if job_to_cancel.status != ScientificJobStatus.PENDING:
                    return
                job_to_cancel.error = safe_error
                job_to_cancel.failure_class = ScientificJobFailureClass.CAMPAIGN_STALE.value
                self._transition(job_to_cancel, ScientificJobStatus.CANCELLED, "CAMPAIGN_INTENT_REJECTED", "Scientific job cancelled because its campaign intent was stale.")
                self._ack_terminal_outbox(job_to_cancel, self._now())

            persisted, _ = self.storage.mutate(job_id, cancel)
            return persisted

        def activate(job_to_activate: ScientificJob) -> None:
            if job_to_activate.status != ScientificJobStatus.PENDING:
                return
            job_to_activate.attachment_campaign_revision = reference.attachment_campaign_revision
            self._transition(job_to_activate, ScientificJobStatus.READY, "JOB_READY", "Campaign intent confirmed; job is ready for durable dispatch.")

        persisted, _ = self.storage.mutate(job_id, activate)
        return persisted

    def _attempt_result_attachment(self, job_id: str) -> ScientificJob:
        job = self.get(job_id)
        attachment = job.attachment
        if job.status != ScientificJobStatus.SUCCEEDED or attachment is None or attachment.status != ScientificJobAttachmentStatus.PENDING:
            return job
        try:
            campaign_attachment = self.campaign_runtime.attach_scientific_job_result(
                campaign_id=job.campaign_id,
                job_id=job.job_id,
                result_hash=job.result_hash,
                expected_campaign_revision=job.attachment_campaign_revision,
                engine_name=job.engine_name,
                engine_version=job.engine_version,
                attachment_key=attachment.attachment_key,
            )
        except (CampaignConflictError, CampaignNotFoundError, IllegalCampaignTransition, ValueError) as error:
            safe_error = self._safe_error(error)

            def reject(job_to_reject: ScientificJob) -> None:
                current = job_to_reject.attachment
                if current is None or current.status != ScientificJobAttachmentStatus.PENDING:
                    return
                current.status = ScientificJobAttachmentStatus.REJECTED
                current.safe_error = safe_error
                self._touch(job_to_reject)
                job_to_reject.append_event("RESULT_ATTACHMENT_REJECTED", "Result was not attached because the campaign revision was incompatible.")

            persisted, _ = self.storage.mutate(job_id, reject)
            return persisted
        except Exception:
            # Leave PENDING after transient storage/runtime faults so reconciliation can retry.
            return job

        def attach(job_to_attach: ScientificJob) -> None:
            current = job_to_attach.attachment
            if current is None:
                raise ScientificJobIntegrityError("Succeeded job is missing its result attachment record")
            if current.status == ScientificJobAttachmentStatus.ATTACHED:
                return
            if current.status != ScientificJobAttachmentStatus.PENDING or current.result_hash != campaign_attachment.result_hash:
                raise ScientificJobConflictError("Scientific job attachment state conflicts with campaign state")
            current.status = ScientificJobAttachmentStatus.ATTACHED
            current.artifact_id = campaign_attachment.artifact_id
            current.attached_at = self._iso(self._now())
            self._touch(job_to_attach)
            job_to_attach.append_event("RESULT_ATTACHED", "Scientific job result attached exactly once to campaign state.", metadata={"artifact_id": current.artifact_id})

        persisted, _ = self.storage.mutate(job_id, attach)
        return persisted

    def _attempt_failure_attachment(self, job_id: str) -> ScientificJob:
        job = self.get(job_id)
        if job.status != ScientificJobStatus.DEAD_LETTER or job.failure is None or job.failure_attachment_state:
            return job
        try:
            self.campaign_runtime.record_scientific_job_failure(
                campaign_id=job.campaign_id,
                job_id=job.job_id,
                expected_campaign_revision=job.attachment_campaign_revision,
                failure_class=job.failure.failure_class,
                safe_error=job.failure.safe_error,
                retryable=job.failure.retryable,
            )
        except (CampaignConflictError, CampaignNotFoundError, IllegalCampaignTransition, ValueError) as error:
            safe_error = self._safe_error(error)

            def reject(job_to_reject: ScientificJob) -> None:
                if job_to_reject.failure_attachment_state:
                    return
                job_to_reject.failure_attachment_state = "REJECTED"
                job_to_reject.failure_attachment_error = safe_error
                self._touch(job_to_reject)
                job_to_reject.append_event("FAILURE_ATTACHMENT_REJECTED", "Terminal failure could not modify an incompatible campaign revision.")

            persisted, _ = self.storage.mutate(job_id, reject)
            return persisted
        except Exception:
            return job

        def attach(job_to_attach: ScientificJob) -> None:
            if job_to_attach.failure_attachment_state:
                return
            job_to_attach.failure_attachment_state = "ATTACHED"
            self._touch(job_to_attach)
            job_to_attach.append_event("FAILURE_ATTACHED", "Terminal scientific job failure archived in campaign state.")

        persisted, _ = self.storage.mutate(job_id, attach)
        return persisted

    def _reclaim_expired_lease(self, job_id: str, now: datetime) -> ScientificJob:
        def mutation(job: ScientificJob) -> None:
            if job.status not in {ScientificJobStatus.LEASED, ScientificJobStatus.RUNNING} or not job.lease_expires_at:
                return
            if self._parse_time(job.lease_expires_at) > now:
                return
            self._release_lease(job, reason="expired", now=now)
            job.failure = ScientificJobFailure(
                job_id=job.job_id,
                failure_class=ScientificJobFailureClass.LEASE_EXPIRED.value,
                safe_error="Scientific job lease expired before the worker completed the operation.",
                retryable=not job.cancellation_requested and job.attempt < job.max_attempts,
            )
            job.failure_class = job.failure.failure_class
            job.error = job.failure.safe_error
            if job.cancellation_requested:
                self._transition(job, ScientificJobStatus.CANCELLED, "LEASE_EXPIRED_CANCELLED", "Expired worker lease reclaimed after cancellation.")
                self._ack_terminal_outbox(job, now)
            elif job.attempt >= job.max_attempts:
                self._transition(job, ScientificJobStatus.DEAD_LETTER, "LEASE_EXPIRED_RECOVERED", "Expired worker lease exhausted the retry budget.")
            else:
                job.ready_at = self._retry_time(job, now)
                self._transition(job, ScientificJobStatus.RETRY_WAIT, "LEASE_EXPIRED_RECOVERED", "Expired worker lease scheduled for deterministic retry.")
            job.reconciliation_count += 1

        persisted, _ = self.storage.mutate(job_id, mutation)
        if persisted.status == ScientificJobStatus.DEAD_LETTER:
            return self._attempt_failure_attachment(persisted.job_id)
        return persisted

    def _release_retry_wait(self, job_id: str, now: datetime) -> ScientificJob:
        def mutation(job: ScientificJob) -> None:
            if job.status != ScientificJobStatus.RETRY_WAIT or self._parse_time(job.ready_at) > now:
                return
            if job.cancellation_requested:
                self._transition(job, ScientificJobStatus.CANCELLED, "JOB_CANCELLED", "Retry-wait job cancellation accepted.")
                self._ack_terminal_outbox(job, now)
                return
            self._transition(job, ScientificJobStatus.READY, "RETRY_READY", "Deterministic retry delay elapsed; job is ready for dispatch.")
            job.reconciliation_count += 1

        persisted, _ = self.storage.mutate(job_id, mutation)
        return persisted

    def _mark_outbox_dispatched(
        self, job_id: str, event_id: str, now: datetime
    ) -> tuple[ScientificJob, ScientificJobOutboxEvent] | None:
        def mutation(job: ScientificJob) -> ScientificJobOutboxEvent | None:
            if job.status != ScientificJobStatus.READY:
                return None
            event = next((item for item in job.outbox_events if item.event_id == event_id), None)
            if event is None or event.status not in {ScientificJobOutboxStatus.PENDING, ScientificJobOutboxStatus.FAILED}:
                return None
            event.status = ScientificJobOutboxStatus.DISPATCHED
            event.attempt += 1
            event.dispatched_at = self._iso(now)
            event.safe_error = ""
            event.revision += 1
            self._touch(job)
            job.append_event("OUTBOX_DISPATCHED", "Durable scientific job dispatch intent published.", metadata={"event_id": event.event_id})
            return event

        persisted, event = self.storage.mutate(job_id, mutation)
        return (persisted, event) if event is not None else None

    def _mark_outbox_failed(self, job_id: str, event_id: str, safe_error: str) -> ScientificJob:
        def mutation(job: ScientificJob) -> None:
            event = next((item for item in job.outbox_events if item.event_id == event_id), None)
            if event is None or event.status != ScientificJobOutboxStatus.DISPATCHED:
                return
            event.status = ScientificJobOutboxStatus.FAILED
            event.safe_error = self._safe_error(safe_error)
            event.revision += 1
            self._touch(job)
            job.append_event("OUTBOX_DISPATCH_FAILED", "Scientific job dispatch transport did not acknowledge the event.")

        persisted, _ = self.storage.mutate(job_id, mutation)
        return persisted

    def _requeue_stale_outbox(self, job_id: str, event_id: str, now: datetime) -> ScientificJob:
        def mutation(job: ScientificJob) -> None:
            event = next((item for item in job.outbox_events if item.event_id == event_id), None)
            if event is None or event.status != ScientificJobOutboxStatus.DISPATCHED:
                return
            event.status = ScientificJobOutboxStatus.PENDING
            event.available_at = self._iso(now)
            event.safe_error = ""
            event.revision += 1
            self._touch(job)
            job.append_event("OUTBOX_REQUEUED", "Stale dispatch intent returned to the durable outbox.")

        persisted, _ = self.storage.mutate(job_id, mutation)
        return persisted

    def _ack_terminal_outbox_persisted(self, job_id: str, now: datetime) -> ScientificJob:
        def mutation(job: ScientificJob) -> None:
            self._ack_terminal_outbox(job, now)
            self._touch(job)
            job.append_event("OUTBOX_ACKNOWLEDGED", "Terminal job dispatch intent acknowledged.")

        persisted, _ = self.storage.mutate(job_id, mutation)
        return persisted

    @staticmethod
    def _has_unacknowledged_outbox(job: ScientificJob) -> bool:
        return any(event.status != ScientificJobOutboxStatus.ACKNOWLEDGED for event in job.outbox_events)

    @staticmethod
    def _ack_terminal_outbox(job: ScientificJob, now: datetime) -> None:
        for event in job.outbox_events:
            if event.status != ScientificJobOutboxStatus.ACKNOWLEDGED:
                event.status = ScientificJobOutboxStatus.ACKNOWLEDGED
                event.acknowledged_at = now.isoformat()
                event.revision += 1

    @staticmethod
    def _ack_dispatch_outbox(job: ScientificJob, now: datetime) -> None:
        for event in job.outbox_events:
            if event.status == ScientificJobOutboxStatus.DISPATCHED:
                event.status = ScientificJobOutboxStatus.ACKNOWLEDGED
                event.acknowledged_at = now.isoformat()
                event.revision += 1

    def _schedule_retry(self, job: ScientificJob, now: datetime, *, event_type: str) -> None:
        job.ready_at = self._retry_time(job, now)
        self._transition(
            job,
            ScientificJobStatus.RETRY_WAIT,
            event_type,
            "Retryable scientific job failure entered deterministic retry wait.",
            metadata={"ready_at": job.ready_at, "attempt": job.attempt},
        )

    def _retry_time(self, job: ScientificJob, now: datetime) -> str:
        delay = min(self.retry_base_seconds * (2 ** max(0, job.attempt - 1)), self.retry_max_seconds)
        return self._iso(now + timedelta(seconds=delay))

    def _transition(
        self,
        job: ScientificJob,
        target: ScientificJobStatus,
        event_type: str,
        summary: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        source = job.status
        validate_job_transition(source, target)
        job.status = target
        self._touch(job)
        job.append_event(event_type, summary, metadata={"from_status": source.value, "to_status": target.value, **(metadata or {})})

    def _release_lease(self, job: ScientificJob, *, reason: str, now: datetime) -> None:
        active = job.active_lease
        if active is not None:
            active.released_at = self._iso(now)
            active.release_reason = reason
        job.lease_owner = ""
        job.lease_token_hash = ""
        job.lease_acquired_at = ""
        job.lease_expires_at = ""

    def _require_current_lease(
        self,
        job: ScientificJob,
        worker_id: str,
        lease_token: str,
        now: datetime,
        *,
        required_status: ScientificJobStatus | None = None,
    ) -> None:
        self._validate_text("worker_id", worker_id, minimum=1, maximum=160)
        self._validate_text("lease_token", lease_token, minimum=1, maximum=512)
        if required_status is not None and job.status != required_status:
            raise ScientificJobLeaseError(f"Scientific job is not {required_status.value}")
        if job.status not in {ScientificJobStatus.LEASED, ScientificJobStatus.RUNNING}:
            raise ScientificJobLeaseError("Scientific job does not have an active lease")
        if job.lease_owner != worker_id or not job.lease_token_hash:
            raise ScientificJobLeaseError("Scientific job lease ownership was not proven")
        if not hmac.compare_digest(job.lease_token_hash, self._token_hash(lease_token)):
            raise ScientificJobLeaseError("Scientific job lease token was rejected")
        if not job.lease_expires_at or self._parse_time(job.lease_expires_at) <= now:
            raise ScientificJobLeaseError("Scientific job lease has expired")

    def _touch(self, job: ScientificJob) -> None:
        job.revision += 1
        job.updated_at = self._iso(self._now())

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _iso(value: datetime) -> str:
        return value.astimezone(UTC).isoformat()

    @staticmethod
    def _parse_time(value: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(value)
        except (TypeError, ValueError) as exc:
            raise ScientificJobIntegrityError("Scientific job timestamp is malformed") from exc
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _validate_text(name: str, value: str, *, minimum: int = 0, maximum: int) -> None:
        if not isinstance(value, str) or len(value.strip()) < minimum or len(value) > maximum:
            raise ValueError(f"{name} must contain between {minimum} and {maximum} characters")

    @staticmethod
    def _validate_lease_seconds(value: int) -> None:
        if not isinstance(value, int) or not 10 <= value <= 300:
            raise ValueError("lease_seconds must be between 10 and 300")

    @staticmethod
    def _safe_error(error: Exception | str) -> str:
        value = str(error).replace("\n", " ").strip()
        return value[:1_000] or "Scientific job runtime operation was rejected."

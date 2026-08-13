from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest

from mystic.lab.campaign import CampaignConflictError
from mystic.lab.campaign_runtime import CampaignRuntime
from mystic.lab.scientific_job import (
    JOB_ALLOWED_TRANSITIONS,
    JOB_SCHEMA_VERSION,
    IllegalScientificJobTransition,
    ScientificJob,
    ScientificJobAttachmentStatus,
    ScientificJobConflictError,
    ScientificJobFailureClass,
    ScientificJobIntegrityError,
    ScientificJobLeaseError,
    ScientificJobOutboxEvent,
    ScientificJobOutboxStatus,
    ScientificJobResult,
    ScientificJobStatus,
    canonical_hash,
    validate_job_transition,
)
from mystic.lab.scientific_job_adapter import ScientificJobWorker
from mystic.lab.scientific_job_runtime import ScientificJobDispatchTransport, ScientificJobRuntime
from mystic.mcp.tools import MysticToolbox


PROJECTILE_INPUT = {
    "initial_position": [0, 0, 0],
    "initial_velocity": [1, 4, 0],
    "duration_seconds": 1,
}


class MutableClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.value

    def advance(self, seconds: int) -> None:
        self.value += timedelta(seconds=seconds)


class RecordingTransport(ScientificJobDispatchTransport):
    def __init__(self, accepted: bool = True) -> None:
        self.accepted = accepted
        self.calls: list[tuple[str, str]] = []

    def dispatch(self, event: ScientificJobOutboxEvent, job: ScientificJob) -> bool:
        self.calls.append((event.event_id, job.job_id))
        return self.accepted


class ScientificJobRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.clock = MutableClock()
        self.campaigns = CampaignRuntime(self.root)
        self.runtime = ScientificJobRuntime(
            self.root,
            campaign_runtime=self.campaigns,
            clock=self.clock,
            retry_base_seconds=10,
            retry_max_seconds=80,
            outbox_stale_seconds=10,
        )
        self.campaign = self.campaigns.create_campaign(title="Durable job campaign", goal="Exercise job runtime")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def create_job(self, **overrides: object) -> ScientificJob:
        values: dict[str, object] = {
            "campaign_id": self.campaign.campaign_id,
            "engine_name": "physics.simple_projectile",
            "input_payload": PROJECTILE_INPUT,
        }
        values.update(overrides)
        return self.runtime.create_job(**values)  # type: ignore[arg-type]

    def start(self, job: ScientificJob, *, worker_id: str = "worker-a") -> tuple[ScientificJob, str]:
        lease = self.runtime.acquire(job.job_id, worker_id=worker_id, lease_seconds=20)
        self.assertIsNotNone(lease)
        leased, token = lease or (None, "")
        return self.runtime.start(leased.job_id, worker_id=worker_id, lease_token=token), token

    @staticmethod
    def result(job: ScientificJob, payload: dict[str, object] | None = None) -> ScientificJobResult:
        return ScientificJobResult(
            job_id=job.job_id,
            engine_name=job.engine_name,
            engine_version=job.engine_version,
            result_payload=payload or {"summary": {"answer": 42}},
            runner_version="test-runner",
        )

    def test_all_declared_legal_transitions_validate(self) -> None:
        for source, targets in JOB_ALLOWED_TRANSITIONS.items():
            for target in targets:
                validate_job_transition(source, target)

    def test_all_non_declared_transitions_are_rejected(self) -> None:
        for source in ScientificJobStatus:
            for target in ScientificJobStatus:
                if target in JOB_ALLOWED_TRANSITIONS[source]:
                    continue
                with self.assertRaises(IllegalScientificJobTransition):
                    validate_job_transition(source, target)

    def test_job_is_versioned_and_persisted_with_outbox(self) -> None:
        job = self.create_job()
        self.assertEqual(job.schema_version, JOB_SCHEMA_VERSION)
        self.assertEqual(job.status, ScientificJobStatus.READY)
        self.assertEqual(len(job.outbox_events), 1)
        self.assertEqual(job.outbox_events[0].status, ScientificJobOutboxStatus.PENDING)
        self.assertTrue(self.runtime.storage.job_path(job.job_id).exists())

    def test_restart_loads_identical_job(self) -> None:
        job = self.create_job()
        restarted = ScientificJobRuntime(self.root, campaign_runtime=CampaignRuntime(self.root), clock=self.clock)
        self.assertEqual(restarted.get(job.job_id).to_dict(), job.to_dict())

    def test_input_hash_and_unknown_persisted_field_fail_closed(self) -> None:
        job = self.create_job()
        path = self.runtime.storage.job_path(job.job_id)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["unknown"] = True
        path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaises(ScientificJobIntegrityError):
            self.runtime.get(job.job_id)

    def test_corrupt_job_is_not_silently_hidden_from_reconciliation_scans(self) -> None:
        job = self.create_job()
        path = self.runtime.storage.job_path(job.job_id)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["unknown"] = True
        path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaises(ScientificJobIntegrityError):
            self.runtime.reconcile()

    def test_bad_hash_is_rejected_before_persistence(self) -> None:
        with self.assertRaises(ScientificJobIntegrityError):
            ScientificJob(
                job_id="job_bad_hash",
                campaign_id=self.campaign.campaign_id,
                campaign_revision=0,
                job_type="engine_execution",
                engine_name="physics.simple_projectile",
                engine_version="2.0.0",
                input_payload={},
                input_hash="0" * 64,
            )

    def test_idempotent_create_returns_same_job(self) -> None:
        first = self.create_job(idempotency_key="same-job")
        second = self.create_job(idempotency_key="same-job")
        self.assertEqual(first.job_id, second.job_id)
        self.assertEqual(len(self.runtime.list()), 1)

    def test_idempotent_create_rejects_different_logical_request(self) -> None:
        self.create_job(idempotency_key="same-job")
        with self.assertRaises(ScientificJobConflictError):
            self.create_job(idempotency_key="same-job", max_attempts=4)

    def test_concurrent_idempotent_create_has_one_job_and_one_campaign_reference(self) -> None:
        barrier = threading.Barrier(6)
        jobs: list[ScientificJob] = []
        errors: list[Exception] = []

        def create() -> None:
            try:
                barrier.wait()
                jobs.append(self.create_job(idempotency_key="concurrent"))
            except Exception as error:  # pragma: no cover - diagnostic assertion below
                errors.append(error)

        threads = [threading.Thread(target=create) for _ in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertEqual({job.job_id for job in jobs}, {jobs[0].job_id})
        campaign = self.campaigns.get(self.campaign.campaign_id)
        self.assertEqual(len(campaign.scientific_jobs), 1)

    def test_acquisition_is_atomic_under_contention(self) -> None:
        job = self.create_job()
        barrier = threading.Barrier(8)
        acquired: list[str] = []

        def acquire(index: int) -> None:
            barrier.wait()
            result = self.runtime.acquire(job.job_id, worker_id=f"worker-{index}", lease_seconds=20)
            if result:
                acquired.append(result[0].lease_owner)

        threads = [threading.Thread(target=acquire, args=(index,)) for index in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        persisted = self.runtime.get(job.job_id)
        self.assertEqual(len(acquired), 1)
        self.assertEqual(persisted.status, ScientificJobStatus.LEASED)
        self.assertEqual(len([lease for lease in persisted.lease_history if not lease.released_at]), 1)

    def test_acquire_next_returns_one_ready_job(self) -> None:
        first = self.create_job()
        second = self.create_job()
        acquired = self.runtime.acquire_next(worker_id="worker-a", lease_seconds=20)
        self.assertIsNotNone(acquired)
        self.assertIn(acquired[0].job_id, {first.job_id, second.job_id})

    def test_start_requires_current_token(self) -> None:
        job = self.create_job()
        leased = self.runtime.acquire(job.job_id, worker_id="worker-a", lease_seconds=20)
        self.assertIsNotNone(leased)
        with self.assertRaises(ScientificJobLeaseError):
            self.runtime.start(job.job_id, worker_id="worker-a", lease_token="bad-token")
        self.assertEqual(self.runtime.get(job.job_id).status, ScientificJobStatus.LEASED)

    def test_heartbeat_renews_only_current_lease(self) -> None:
        job = self.create_job()
        running, token = self.start(job)
        previous_expiry = running.lease_expires_at
        self.clock.advance(1)
        renewed = self.runtime.heartbeat(job.job_id, worker_id="worker-a", lease_token=token, lease_seconds=30)
        self.assertGreater(renewed.lease_expires_at, previous_expiry)
        self.assertEqual(renewed.active_lease.heartbeat_count, 1)

    def test_stale_owner_is_rejected_after_expiry_and_reclaim(self) -> None:
        job = self.create_job()
        running, token = self.start(job)
        self.clock.advance(21)
        self.runtime.reconcile()
        self.clock.advance(10)
        self.runtime.reconcile()
        replacement = self.runtime.acquire(job.job_id, worker_id="worker-b", lease_seconds=20)
        self.assertIsNotNone(replacement)
        with self.assertRaises(ScientificJobLeaseError):
            self.runtime.heartbeat(job.job_id, worker_id="worker-a", lease_token=token)
        self.assertEqual(self.runtime.get(job.job_id).lease_owner, "worker-b")

    def test_expired_running_job_is_reclaimed_to_retry_wait(self) -> None:
        job = self.create_job()
        self.start(job)
        self.clock.advance(21)
        stats = self.runtime.reconcile()
        reclaimed = self.runtime.get(job.job_id)
        self.assertEqual(reclaimed.status, ScientificJobStatus.RETRY_WAIT)
        self.assertEqual(reclaimed.failure_class, ScientificJobFailureClass.LEASE_EXPIRED.value)
        self.assertEqual(stats["expired_leases_recovered"], 1)
        self.assertEqual(stats["orphaned_running_jobs"], 1)

    def test_ready_cancellation_is_terminal_and_idempotent(self) -> None:
        job = self.create_job()
        first = self.runtime.cancel(job.job_id)
        second = self.runtime.cancel(job.job_id)
        self.assertEqual(first.status, ScientificJobStatus.CANCELLED)
        self.assertEqual(second.revision, first.revision)
        self.assertIsNone(self.runtime.acquire(job.job_id, worker_id="worker", lease_seconds=20))

    def test_running_cancellation_sets_cooperative_intent(self) -> None:
        job = self.create_job()
        _, token = self.start(job)
        cancelling = self.runtime.cancel(job.job_id)
        self.assertEqual(cancelling.status, ScientificJobStatus.RUNNING)
        self.assertTrue(cancelling.cancellation_requested)
        self.assertTrue(self.runtime.is_cancellation_requested(job.job_id, worker_id="worker-a", lease_token=token))

    def test_cancelled_running_job_rejects_late_result(self) -> None:
        job = self.create_job()
        running, token = self.start(job)
        self.runtime.cancel(job.job_id)
        with self.assertRaises(ScientificJobLeaseError):
            self.runtime.complete(job.job_id, worker_id="worker-a", lease_token=token, result=self.result(running))
        self.assertEqual(self.runtime.get(job.job_id).status, ScientificJobStatus.CANCELLED)

    def test_completed_job_cannot_be_cancelled(self) -> None:
        job = self.create_job()
        running, token = self.start(job)
        self.runtime.complete(job.job_id, worker_id="worker-a", lease_token=token, result=self.result(running))
        with self.assertRaises(IllegalScientificJobTransition):
            self.runtime.cancel(job.job_id)

    def test_retryable_failure_gets_deterministic_delay(self) -> None:
        job = self.create_job()
        _, token = self.start(job)
        failed = self.runtime.fail(job.job_id, worker_id="worker-a", lease_token=token, failure_class="ENGINE_TRANSIENT", safe_error="engine unavailable", retryable=True)
        queued = self.runtime.retry(failed.job_id)
        self.assertEqual(queued.status, ScientificJobStatus.RETRY_WAIT)
        self.assertEqual(queued.ready_at, (self.clock.value + timedelta(seconds=10)).isoformat())

    def test_failed_job_can_be_cancelled_before_retry(self) -> None:
        job = self.create_job()
        _, token = self.start(job)
        self.runtime.fail(
            job.job_id,
            worker_id="worker-a",
            lease_token=token,
            failure_class="ENGINE_TRANSIENT",
            safe_error="engine unavailable",
            retryable=True,
        )
        cancelled = self.runtime.cancel(job.job_id)
        self.assertEqual(cancelled.status, ScientificJobStatus.CANCELLED)
        self.assertEqual(self.runtime.cancel(job.job_id).revision, cancelled.revision)

    def test_retry_wait_becomes_ready_only_after_due_time(self) -> None:
        job = self.create_job()
        _, token = self.start(job)
        self.runtime.fail(job.job_id, worker_id="worker-a", lease_token=token, failure_class="ENGINE_TRANSIENT", safe_error="temporary", retryable=True)
        self.runtime.retry(job.job_id)
        self.runtime.reconcile()
        self.assertEqual(self.runtime.get(job.job_id).status, ScientificJobStatus.RETRY_WAIT)
        self.clock.advance(10)
        self.runtime.reconcile()
        self.assertEqual(self.runtime.get(job.job_id).status, ScientificJobStatus.READY)

    def test_terminal_failure_moves_to_dead_letter_and_archives_failure(self) -> None:
        job = self.create_job()
        _, token = self.start(job)
        self.runtime.fail(job.job_id, worker_id="worker-a", lease_token=token, failure_class="ENGINE_PERMANENT", safe_error="invalid model", retryable=False)
        dead_letter = self.runtime.retry(job.job_id)
        self.assertEqual(dead_letter.status, ScientificJobStatus.DEAD_LETTER)
        self.assertEqual(dead_letter.failure_attachment_state, "ATTACHED")
        campaign = self.campaigns.get(self.campaign.campaign_id)
        self.assertEqual(len(campaign.failures), 1)
        self.assertEqual(campaign.failures[0].source_id, job.job_id)

    def test_retry_never_exceeds_max_attempts(self) -> None:
        job = self.create_job(max_attempts=1)
        _, token = self.start(job)
        self.runtime.fail(job.job_id, worker_id="worker-a", lease_token=token, failure_class="ENGINE_TRANSIENT", safe_error="temporary", retryable=True)
        dead_letter = self.runtime.retry(job.job_id)
        self.assertEqual(dead_letter.status, ScientificJobStatus.DEAD_LETTER)
        self.assertEqual(dead_letter.attempt, 1)

    def test_duplicate_same_result_replay_is_ignored(self) -> None:
        job = self.create_job()
        running, token = self.start(job)
        result = self.result(running)
        completed = self.runtime.complete(job.job_id, worker_id="worker-a", lease_token=token, result=result)
        replay = self.runtime.complete(job.job_id, worker_id="worker-a", lease_token=token, result=result)
        self.assertEqual(completed.result_hash, replay.result_hash)
        self.assertEqual(replay.duplicate_completion_count, 1)
        self.assertEqual(replay.attachment.status, ScientificJobAttachmentStatus.ATTACHED)
        campaign = self.campaigns.get(self.campaign.campaign_id)
        self.assertEqual(len(campaign.scientific_job_attachments), 1)

    def test_conflicting_same_token_result_is_rejected_and_audited(self) -> None:
        job = self.create_job()
        running, token = self.start(job)
        self.runtime.complete(job.job_id, worker_id="worker-a", lease_token=token, result=self.result(running, {"value": 1}))
        with self.assertRaises(ScientificJobConflictError):
            self.runtime.complete(job.job_id, worker_id="worker-a", lease_token=token, result=self.result(running, {"value": 2}))
        persisted = self.runtime.get(job.job_id)
        self.assertEqual(persisted.conflicting_result_count, 1)
        self.assertEqual(persisted.duplicate_completion_rejected_count, 1)
        self.assertEqual(len(self.campaigns.get(self.campaign.campaign_id).scientific_job_attachments), 1)

    def test_conflicting_result_from_stale_token_cannot_mutate_job(self) -> None:
        job = self.create_job()
        running, token = self.start(job)
        self.clock.advance(21)
        self.runtime.reconcile()
        with self.assertRaises(ScientificJobLeaseError):
            self.runtime.complete(job.job_id, worker_id="worker-a", lease_token=token, result=self.result(running))
        self.assertEqual(self.runtime.get(job.job_id).status, ScientificJobStatus.RETRY_WAIT)

    def test_result_persisted_before_attachment_is_recovered(self) -> None:
        job = self.create_job()
        running, token = self.start(job)
        persisted = self.runtime.complete(job.job_id, worker_id="worker-a", lease_token=token, result=self.result(running), attempt_attachment=False)
        self.assertEqual(persisted.attachment.status, ScientificJobAttachmentStatus.PENDING)
        recovered = self.runtime.reconcile()
        self.assertEqual(recovered["result_attachments_completed"], 1)
        self.assertEqual(self.runtime.get(job.job_id).attachment.status, ScientificJobAttachmentStatus.ATTACHED)

    def test_campaign_attachment_before_job_ack_is_recovered_idempotently(self) -> None:
        job = self.create_job()
        running, token = self.start(job)
        persisted = self.runtime.complete(job.job_id, worker_id="worker-a", lease_token=token, result=self.result(running), attempt_attachment=False)
        self.campaigns.attach_scientific_job_result(
            campaign_id=persisted.campaign_id,
            job_id=persisted.job_id,
            result_hash=persisted.result_hash,
            expected_campaign_revision=persisted.attachment_campaign_revision,
            engine_name=persisted.engine_name,
            engine_version=persisted.engine_version,
            attachment_key=persisted.attachment.attachment_key,
        )
        recovered = self.runtime.reconcile()
        self.assertEqual(recovered["result_attachments_completed"], 1)
        self.assertEqual(self.runtime.get(job.job_id).attachment.status, ScientificJobAttachmentStatus.ATTACHED)

    def test_stale_campaign_revision_rejects_attachment_without_corruption(self) -> None:
        job = self.create_job()
        self.campaigns.checkpoint(self.campaign.campaign_id, label="before-result")
        running, token = self.start(job)
        completed = self.runtime.complete(job.job_id, worker_id="worker-a", lease_token=token, result=self.result(running))
        self.assertEqual(completed.attachment.status, ScientificJobAttachmentStatus.REJECTED)
        campaign = self.campaigns.get(self.campaign.campaign_id)
        self.assertEqual(len(campaign.scientific_job_attachments), 0)

    def test_rollback_removes_post_checkpoint_reference_but_preserves_job_history(self) -> None:
        checkpoint_id = self.campaign.checkpoints[0].checkpoint_id
        job = self.create_job()
        rolled_back = self.campaigns.rollback(self.campaign.campaign_id, checkpoint_id)
        self.assertEqual(len(rolled_back.scientific_jobs), 0)
        running, token = self.start(job)
        completed = self.runtime.complete(job.job_id, worker_id="worker-a", lease_token=token, result=self.result(running))
        self.assertEqual(completed.attachment.status, ScientificJobAttachmentStatus.REJECTED)
        self.assertEqual(self.runtime.get(job.job_id).status, ScientificJobStatus.SUCCEEDED)

    def test_dispatch_outbox_marks_event_and_transport_receives_safe_job(self) -> None:
        transport = RecordingTransport()
        runtime = ScientificJobRuntime(self.root, campaign_runtime=self.campaigns, transport=transport, clock=self.clock)
        job = runtime.create_job(campaign_id=self.campaign.campaign_id, engine_name="physics.simple_projectile", input_payload=PROJECTILE_INPUT)
        result = runtime.dispatch_outbox()
        self.assertEqual(result, {"dispatched": 1, "failed": 0})
        self.assertEqual(transport.calls[0][1], job.job_id)
        self.assertEqual(runtime.get(job.job_id).outbox_events[0].status, ScientificJobOutboxStatus.DISPATCHED)

    def test_failed_dispatch_is_retryable(self) -> None:
        transport = RecordingTransport(accepted=False)
        runtime = ScientificJobRuntime(self.root, campaign_runtime=self.campaigns, transport=transport, clock=self.clock)
        job = runtime.create_job(campaign_id=self.campaign.campaign_id, engine_name="physics.simple_projectile", input_payload=PROJECTILE_INPUT)
        self.assertEqual(runtime.dispatch_outbox(), {"dispatched": 0, "failed": 1})
        self.assertEqual(runtime.get(job.job_id).outbox_events[0].status, ScientificJobOutboxStatus.FAILED)

    def test_stale_dispatched_outbox_is_requeued(self) -> None:
        transport = RecordingTransport()
        runtime = ScientificJobRuntime(self.root, campaign_runtime=self.campaigns, transport=transport, clock=self.clock, outbox_stale_seconds=10)
        job = runtime.create_job(campaign_id=self.campaign.campaign_id, engine_name="physics.simple_projectile", input_payload=PROJECTILE_INPUT)
        runtime.dispatch_outbox()
        self.clock.advance(10)
        stats = runtime.reconcile()
        self.assertGreaterEqual(stats["stale_outbox_requeued"], 1)
        self.assertGreaterEqual(stats["outbox_dispatched"], 1)

    def test_terminal_jobs_acknowledge_outbox(self) -> None:
        job = self.create_job()
        self.runtime.cancel(job.job_id)
        self.assertEqual(self.runtime.get(job.job_id).outbox_events[0].status, ScientificJobOutboxStatus.ACKNOWLEDGED)

    def test_pending_job_recovers_campaign_intent_after_crash(self) -> None:
        campaign = self.campaigns.get(self.campaign.campaign_id)
        job = ScientificJob(
            job_id="job_recover_pending",
            campaign_id=campaign.campaign_id,
            campaign_revision=campaign.revision,
            job_type="engine_execution",
            engine_name="physics.simple_projectile",
            engine_version="2.0.0",
            input_payload={"duration_seconds": 1},
            input_hash=canonical_hash({"duration_seconds": 1}),
            created_at=self.clock.value.isoformat(),
            updated_at=self.clock.value.isoformat(),
            ready_at=self.clock.value.isoformat(),
        )
        job.outbox_events.append(ScientificJobOutboxEvent(job_id=job.job_id, payload_hash=job.input_hash, available_at=self.clock.value.isoformat()))
        self.runtime.storage.create(job)
        stats = self.runtime.reconcile()
        self.assertEqual(stats["campaign_intents_recovered"], 1)
        self.assertEqual(self.runtime.get(job.job_id).status, ScientificJobStatus.READY)

    def test_reconciliation_is_idempotent_on_correct_state(self) -> None:
        job = self.create_job()
        before = self.runtime.get(job.job_id).to_dict()
        first = self.runtime.reconcile()
        second = self.runtime.reconcile()
        self.assertEqual(first["reconciliation_actions"], 1)  # initial outbox publication
        self.assertEqual(second["reconciliation_actions"], 0)
        after = self.runtime.get(job.job_id).to_dict()
        self.assertEqual(before["status"], after["status"])

    def test_statistics_derive_from_runtime_state(self) -> None:
        ready = self.create_job()
        leased = self.create_job()
        self.runtime.acquire(leased.job_id, worker_id="worker-a", lease_seconds=20)
        stats = self.runtime.statistics(campaign_id=self.campaign.campaign_id)
        self.assertEqual(stats["job_count"], 2)
        self.assertEqual(stats["ready_jobs"], 1)
        self.assertEqual(stats["leased_jobs"], 1)
        self.assertEqual(stats["average_attempts"], 0.5)
        self.assertEqual(ready.status, ScientificJobStatus.READY)

    def test_worker_executes_allowlisted_engine_and_attaches_once(self) -> None:
        job = self.create_job()
        completed = ScientificJobWorker(self.runtime, self.runtime.adapter).run_once(worker_id="trusted-worker")
        self.assertIsNotNone(completed)
        self.assertEqual(completed.status, ScientificJobStatus.SUCCEEDED)
        self.assertEqual(completed.attachment.status, ScientificJobAttachmentStatus.ATTACHED)

    def test_worker_renews_lease_while_an_engine_execution_is_in_progress(self) -> None:
        job = self.create_job()

        class SlowAdapter:
            @staticmethod
            def execute(
                running_job: ScientificJob,
                *,
                lease_owner: str,
                cancellation_check: object,
            ) -> ScientificJobResult:
                del lease_owner, cancellation_check
                time.sleep(1.15)
                return ScientificJobResult(
                    job_id=running_job.job_id,
                    engine_name=running_job.engine_name,
                    engine_version=running_job.engine_version,
                    result_payload={"slow": True},
                    runner_version="slow-test-runner",
                )

        completed = ScientificJobWorker(
            self.runtime,
            SlowAdapter(),  # type: ignore[arg-type]
            heartbeat_interval_seconds=1,
        ).run_once(worker_id="heartbeat-worker", lease_seconds=10)
        self.assertIsNotNone(completed)
        self.assertEqual(completed.status, ScientificJobStatus.SUCCEEDED)
        self.assertGreaterEqual(completed.lease_history[-1].heartbeat_count, 1)

    def test_engine_adapter_rejects_unknown_engine(self) -> None:
        with self.assertRaises(Exception):
            self.create_job(engine_name="../../bin/sh")

    def test_public_payload_redacts_tokens_and_raw_payloads(self) -> None:
        job = self.create_job()
        leased = self.runtime.acquire(job.job_id, worker_id="worker-a", lease_seconds=20)
        self.assertIsNotNone(leased)
        payload = self.runtime.public_payload(self.runtime.get(job.job_id))
        serialized = json.dumps(payload)
        self.assertNotIn("lease_token_hash", payload)
        self.assertNotIn("input_payload", payload)
        self.assertNotIn("lease_token_hash", serialized)
        self.assertIn("input_metadata", payload)

    def test_public_mcp_surface_exposes_only_operator_job_controls(self) -> None:
        toolbox = MysticToolbox.__new__(MysticToolbox)
        toolbox.campaign_runtime = self.campaigns
        toolbox.scientific_job_runtime = self.runtime
        payload = toolbox.lab_job_create(
            campaign_id=self.campaign.campaign_id,
            engine_name="physics.simple_projectile",
            input_payload=PROJECTILE_INPUT,
            idempotency_key="public-job",
        )
        self.assertEqual(payload["status"], "READY")
        self.assertNotIn("lease_token_hash", payload)
        self.assertEqual(toolbox.lab_job_list(campaign_id=self.campaign.campaign_id)["count"], 1)
        self.assertNotIn("acquire", " ".join(name for name in dir(toolbox) if name.startswith("lab_job_")))

    def test_storage_compare_and_swap_rejects_stale_write(self) -> None:
        job = self.create_job()
        first = self.runtime.storage.load(job.job_id)
        second = self.runtime.storage.load(job.job_id)
        first.revision += 1
        first.updated_at = (self.clock.value + timedelta(seconds=1)).isoformat()
        self.runtime.storage.save(first, expected_revision=job.revision)
        second.revision += 1
        second.updated_at = (self.clock.value + timedelta(seconds=1)).isoformat()
        with self.assertRaises(ScientificJobConflictError):
            self.runtime.storage.save(second, expected_revision=job.revision)

    def test_competing_completions_apply_campaign_once(self) -> None:
        job = self.create_job()
        running, token = self.start(job)
        result = self.result(running)
        barrier = threading.Barrier(2)
        outcomes: list[ScientificJob] = []
        errors: list[Exception] = []

        def complete() -> None:
            try:
                barrier.wait()
                outcomes.append(self.runtime.complete(job.job_id, worker_id="worker-a", lease_token=token, result=result))
            except Exception as error:  # pragma: no cover - assertion below
                errors.append(error)

        threads = [threading.Thread(target=complete) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertEqual(len(outcomes), 2)
        self.assertEqual(len(self.campaigns.get(self.campaign.campaign_id).scientific_job_attachments), 1)

    def test_campaign_runtime_detects_conflicting_direct_attachment(self) -> None:
        job = self.create_job()
        running, token = self.start(job)
        completed = self.runtime.complete(job.job_id, worker_id="worker-a", lease_token=token, result=self.result(running))
        with self.assertRaises(CampaignConflictError):
            self.campaigns.attach_scientific_job_result(
                campaign_id=completed.campaign_id,
                job_id=completed.job_id,
                result_hash="0" * 64,
                expected_campaign_revision=completed.attachment_campaign_revision,
                engine_name=completed.engine_name,
                engine_version=completed.engine_version,
                attachment_key=completed.attachment.attachment_key,
            )

from __future__ import annotations

from pathlib import Path
from contextlib import redirect_stdout
import hashlib
import io
import os
import tempfile
import unittest
from unittest.mock import patch

from mystic.lab.campaign_runtime import CampaignRuntime
from mystic.lab.engines import EngineError
from mystic.lab.scientific_job import ScientificJobStatus
from mystic.lab.scientific_job_runtime import ScientificJobRuntime
from mystic.lab.worker.auth import WorkerCredentialError, WorkerCredentialVerifier
from mystic.lab.worker.config import ScientificWorkerConfig
from mystic.lab.worker.health import WorkerState
from mystic.lab.worker.retry import WorkerFailureCategory, classify_execution_error
from mystic.lab.worker.service import ScientificJobWorkerService
from mystic.lab.worker.status_store import WorkerControlStorage, WorkerStatusStorage, validate_worker_status_payload
from mystic.lab.worker.__main__ import main as worker_main


PROJECTILE_INPUT = {
    "initial_position": [0, 0, 0],
    "initial_velocity": [1, 4, 0],
    "duration_seconds": 1,
}


class ScientificJobWorkerServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.campaigns = CampaignRuntime(self.root)
        self.runtime = ScientificJobRuntime(self.root, campaign_runtime=self.campaigns)
        self.campaign = self.campaigns.create_campaign(title="Worker campaign", goal="Exercise trusted worker")
        self.config = ScientificWorkerConfig(
            worker_id="trusted_worker_test",
            root_path=self.root,
            maximum_concurrency=2,
            lease_seconds=12,
            heartbeat_interval_seconds=4,
            reconciliation_interval_seconds=1,
        )
        self.events: list[tuple[str, str]] = []
        self.service = ScientificJobWorkerService(
            self.runtime,
            self.config,
            hooks=(lambda event, job: self.events.append((event, job.job_id)),),
        )

    def tearDown(self) -> None:
        self.service.drain_and_stop()
        self.temporary.cleanup()

    def create_job(self, **overrides: object):
        values: dict[str, object] = {
            "campaign_id": self.campaign.campaign_id,
            "engine_name": "physics.simple_projectile",
            "input_payload": PROJECTILE_INPUT,
        }
        values.update(overrides)
        return self.runtime.create_job(**values)  # type: ignore[arg-type]

    def test_service_executes_via_durable_lease_and_attaches_once(self) -> None:
        job = self.create_job()
        result = self.service.poll_once(wait_for_completion=True)
        persisted = self.runtime.get(job.job_id)
        health = self.service.safe_health()
        self.assertEqual(result.acquired, 1)
        self.assertEqual(persisted.status, ScientificJobStatus.SUCCEEDED)
        self.assertEqual(persisted.attachment.status.value, "ATTACHED")
        self.assertEqual(health["status"], WorkerState.READY.value)
        self.assertIn(("job_succeeded", job.job_id), self.events)
        self.assertIn(("result_attached", job.job_id), self.events)
        self.assertIn(("evidence_available", job.job_id), self.events)
        self.assertEqual(self.service.safe_metrics()["jobs_completed_total"], 1)

    def test_configured_capacity_bounds_concurrent_durable_jobs(self) -> None:
        first = self.create_job()
        second = self.create_job()
        result = self.service.poll_once(wait_for_completion=True)
        self.assertEqual(result.acquired, 2)
        self.assertEqual(self.runtime.get(first.job_id).status, ScientificJobStatus.SUCCEEDED)
        self.assertEqual(self.runtime.get(second.job_id).status, ScientificJobStatus.SUCCEEDED)
        self.assertLessEqual(int(self.service.safe_health()["active_jobs"]), self.config.maximum_concurrency)

    def test_drain_stops_new_acquisition_without_cancelling_durable_work(self) -> None:
        job = self.create_job()
        self.service.request_drain()
        result = self.service.poll_once()
        self.assertEqual(result.acquired, 0)
        self.assertEqual(self.runtime.get(job.job_id).status, ScientificJobStatus.READY)
        self.assertEqual(self.service.safe_health()["status"], WorkerState.DRAINING.value)

    def test_ready_cancellation_is_observed_without_success_attachment(self) -> None:
        job = self.create_job()
        self.runtime.cancel(job.job_id)
        result = self.service.poll_once(wait_for_completion=True)
        persisted = self.runtime.get(job.job_id)
        self.assertEqual(result.acquired, 0)
        self.assertEqual(persisted.status, ScientificJobStatus.CANCELLED)
        self.assertIsNone(persisted.attachment)

    def test_reconcile_once_uses_existing_idempotent_runtime_repair(self) -> None:
        job = self.create_job()
        stats = self.service.reconcile_once()
        self.assertIn("reconciliation_actions", stats)
        self.assertEqual(self.runtime.get(job.job_id).status, ScientificJobStatus.READY)
        self.assertGreaterEqual(int(self.service.safe_health()["reconciliation_count"]), 1)

    def test_safe_health_and_metrics_exclude_credentials_and_private_paths(self) -> None:
        health = str(self.service.safe_health())
        metrics = str(self.service.safe_metrics())
        self.assertNotIn(str(self.root), health)
        self.assertNotIn("credential", health.lower())
        self.assertNotIn("token", health.lower())
        self.assertNotIn("job_", metrics)

    def test_worker_publishes_fixed_schema_redacted_health_only(self) -> None:
        payload = WorkerStatusStorage(self.root).get(self.config.worker_id)
        self.assertEqual(payload["worker_id"], self.config.worker_id)
        self.assertEqual(payload["status"], WorkerState.READY.value)
        self.assertNotIn("lease_token", payload)
        self.assertNotIn("credential", str(payload).lower())
        self.assertNotIn(str(self.root), str(payload))
        malformed = dict(payload)
        malformed["lease_token"] = "must-not-persist"
        with self.assertRaises(ValueError):
            validate_worker_status_payload(malformed)

    def test_authenticated_drain_intent_stops_new_acquisition_without_exposing_worker_mutation(self) -> None:
        job = self.create_job()
        request = WorkerControlStorage(self.root).request_drain(self.config.worker_id)
        self.assertEqual(request["action"], "drain")
        result = self.service.poll_once()
        self.assertEqual(result.acquired, 0)
        self.assertEqual(self.runtime.get(job.job_id).status, ScientificJobStatus.READY)
        self.assertEqual(self.service.safe_health()["status"], WorkerState.DRAINING.value)

    def test_lost_lease_is_counted_as_a_renewal_failure(self) -> None:
        job = self.create_job()
        # The internal facade only returns an active aggregate when lease
        # renewal lost ownership, and the service turns that signal into safe
        # operational metrics without attempting stale completion.
        result, _ = self.runtime.acquire_next(worker_id=self.config.worker_id, lease_seconds=10)
        self.assertEqual(result.job_id, job.job_id)
        self.service._record_outcome(result)  # noqa: SLF001 - metric boundary
        self.assertEqual(self.service.safe_metrics()["lease_renewal_failures_total"], 1)


class WorkerSecurityAndRetryTests(unittest.TestCase):
    def test_dedicated_credential_verifier_supports_rotation_and_revocation(self) -> None:
        old = WorkerCredentialVerifier.from_secret("old-worker-credential")
        new = WorkerCredentialVerifier.from_secret("new-worker-credential")
        hashes = (
            hashlib.sha256(b"old-worker-credential").hexdigest(),
            hashlib.sha256(b"new-worker-credential").hexdigest(),
        )
        rotating = WorkerCredentialVerifier(hashes)
        self.assertTrue(rotating.verify("old-worker-credential"))
        self.assertTrue(rotating.verify("new-worker-credential"))
        self.assertFalse(rotating.verify("mcp-oauth-token"))
        with self.assertRaises(WorkerCredentialError):
            rotating.require("")
        revoked = WorkerCredentialVerifier((hashes[1],))
        self.assertFalse(revoked.verify("old-worker-credential"))
        self.assertTrue(revoked.verify("new-worker-credential"))
        self.assertNotIn("old-worker-credential", str(rotating.safe_metadata()))

    def test_failure_taxonomy_does_not_retry_scientific_input_or_policy_rejection(self) -> None:
        input_failure = classify_execution_error(EngineError("engine_input_invalid", "bad input"))
        policy_failure = classify_execution_error(EngineError("engine_artifact_too_large", "oversized"))
        transient_failure = classify_execution_error(EngineError("engine_runner_offline", "offline"))
        timeout_failure = classify_execution_error(TimeoutError())
        self.assertEqual(input_failure.category, WorkerFailureCategory.SCIENTIFIC_INPUT)
        self.assertFalse(input_failure.retryable)
        self.assertEqual(policy_failure.category, WorkerFailureCategory.POLICY_SAFETY)
        self.assertFalse(policy_failure.retryable)
        self.assertEqual(transient_failure.category, WorkerFailureCategory.INFRASTRUCTURE)
        self.assertTrue(transient_failure.retryable)
        self.assertTrue(timeout_failure.retryable)
        self.assertTrue(timeout_failure.diagnostic_id.startswith("diag_"))

    def test_status_and_drain_require_an_explicit_authenticated_worker_identity(self) -> None:
        credential = "isolated-worker-test-credential"
        digest = hashlib.sha256(credential.encode("utf-8")).hexdigest()
        with tempfile.TemporaryDirectory() as temporary_root:
            base_environment = {
                "MYSTIC_SCIENTIFIC_WORKER_ROOT": temporary_root,
                "MYSTIC_SCIENTIFIC_WORKER_CREDENTIAL_HASHES": digest,
                "MYSTIC_SCIENTIFIC_WORKER_CREDENTIAL": credential,
            }
            with patch.dict(os.environ, base_environment, clear=False), redirect_stdout(io.StringIO()):
                os.environ.pop("MYSTIC_SCIENTIFIC_WORKER_ID", None)
                self.assertEqual(worker_main(["--status"]), 2)
                self.assertEqual(worker_main(["--drain"]), 2)
                os.environ["MYSTIC_SCIENTIFIC_WORKER_ID"] = "trusted_worker_cli_test"
                self.assertEqual(worker_main(["--drain"]), 0)
            self.assertTrue(WorkerControlStorage(temporary_root).drain_requested("trusted_worker_cli_test"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

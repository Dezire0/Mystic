from __future__ import annotations

from pathlib import Path
import re
import unittest


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "supabase"
    / "migrations"
    / "20260807010000_durable_scientific_job_runtime_phase2c2a.sql"
)


class ScientificJobMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sql = MIGRATION.read_text(encoding="utf-8").lower()

    def test_additive_schema_contains_durable_job_aggregate_tables_and_indexes(self) -> None:
        for fragment in (
            "create table if not exists public.lab_scientific_jobs",
            "create table if not exists public.lab_scientific_job_leases",
            "create table if not exists public.lab_scientific_job_outbox_events",
            "create table if not exists public.lab_scientific_job_attachments",
            "create table if not exists public.lab_scientific_job_events",
            "lab_scientific_jobs_ready_idx",
            "lab_scientific_jobs_lease_expiry_idx",
            "lab_scientific_job_leases_one_active_idx",
            "lab_scientific_jobs_campaign_idempotency_idx",
            "schema_version text not null default '2c.2a'",
        ):
            self.assertIn(fragment, self.sql)
        self.assertIsNone(re.search(r"\bdrop\s+", self.sql))

    def test_service_role_rpc_contracts_cover_atomic_lease_recovery_and_attachment(self) -> None:
        for function in (
            "mystic_create_scientific_job",
            "mystic_acquire_scientific_job_lease",
            "mystic_dispatch_scientific_job_outbox",
            "mystic_start_scientific_job",
            "mystic_heartbeat_scientific_job_lease",
            "mystic_complete_scientific_job",
            "mystic_fail_scientific_job",
            "mystic_retry_scientific_job",
            "mystic_cancel_scientific_job",
            "mystic_attach_scientific_job_result",
            "mystic_attach_scientific_job_failure",
            "mystic_reconcile_scientific_jobs",
        ):
            self.assertIn(f"function public.{function}", self.sql)
        self.assertIn("for update skip locked", self.sql)
        self.assertIn("mystic_scientific_job_payload_hash", self.sql)
        self.assertIn("p_result->'result_payload'", self.sql)
        self.assertIn("p_result - array['job_id','engine_name'", self.sql)
        self.assertIn("extensions.digest", self.sql)
        self.assertIn("enable row level security", self.sql)
        self.assertIn("from anon, authenticated", self.sql)

    def test_result_and_campaign_reference_contracts_fail_closed(self) -> None:
        self.assertIn("p_result - array['job_id','engine_name'", self.sql)
        self.assertIn("p_result->'result_payload'", self.sql)
        self.assertIn("scientific_job_result_hash_mismatch", self.sql)
        self.assertIn("scientific_job_experiment_not_found", self.sql)
        self.assertIn("current_job.experiment_id = p_experiment_id", self.sql)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

from __future__ import annotations

from pathlib import Path
import unittest

from scripts.mystic_engine_runner import RUNNER_PROTOCOL_VERSION, runner_registration
from mystic.lab.engines import builtin_registry


ROOT = Path(__file__).resolve().parents[1]


class RunnerFleetAssetTests(unittest.TestCase):
    def test_runner_registration_is_safe_and_declares_protocol(self) -> None:
        registration = runner_registration(builtin_registry())

        self.assertEqual(registration["protocol_version"], RUNNER_PROTOCOL_VERSION)
        self.assertEqual(registration["max_concurrent_jobs"], 1)
        self.assertNotIn("token", registration)
        self.assertNotIn("path", registration)
        self.assertTrue(registration["engines"])

    def test_fleet_migration_has_additive_registry_lease_and_audit_contracts(self) -> None:
        migration = (ROOT / "supabase/migrations/20260730090000_issue_112_runner_fleet.sql").read_text()

        for required in (
            "lab_engine_runner_credentials",
            "lab_engine_job_attempts",
            "lab_engine_runner_audit_events",
            "assigned_runner_id",
            "lease_owner",
            "maximum_attempts",
            "dead_letter",
            "mystic_fleet_claim_next_engine_job",
            "mystic_fleet_renew_engine_job_lease",
            "mystic_fleet_recover_expired_engine_leases",
            "mystic_fleet_request_engine_job_cancellation",
            "mystic_fleet_complete_engine_job",
            "mystic_fleet_fail_engine_job",
        ):
            self.assertIn(required, migration)
        self.assertNotIn("credential_token", migration)

    def test_linux_runner_is_non_root_read_only_and_has_no_shell_execution(self) -> None:
        dockerfile = (ROOT / "runners/linux/Dockerfile").read_text()
        compose = (ROOT / "runners/linux/compose.yaml").read_text()

        self.assertIn("USER 10001:10001", dockerfile)
        self.assertIn("read_only: true", compose)
        self.assertIn("cap_drop: [\"ALL\"]", compose)
        self.assertIn("no-new-privileges:true", compose)
        self.assertNotIn("shell=True", dockerfile)
        self.assertNotIn("exec", dockerfile.lower())


if __name__ == "__main__":
    unittest.main()

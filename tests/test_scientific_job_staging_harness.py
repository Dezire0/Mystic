from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_scientific_job_runtime_staging.py"
SPEC = importlib.util.spec_from_file_location("scientific_job_staging_harness", SCRIPT)
assert SPEC and SPEC.loader
HARNESS = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = HARNESS
SPEC.loader.exec_module(HARNESS)


class ScientificJobStagingHarnessTests(unittest.TestCase):
    def environment(self, **overrides: str) -> dict[str, str]:
        values = {
            "MYSTIC_STAGING_SUPABASE_PROJECT_REF": HARNESS.STAGING_PROJECT_REF,
            "MYSTIC_STAGING_DATABASE_URL": (
                f"postgresql://fixture_user:fixture_password@{HARNESS.STAGING_HOST}:5432/postgres"
            ),
        }
        values.update(overrides)
        return values

    def test_requires_exact_project_ref_and_direct_staging_host(self) -> None:
        with patch.dict(os.environ, self.environment(MYSTIC_STAGING_SUPABASE_PROJECT_REF="different"), clear=True):
            with self.assertRaises(HARNESS.StagingHarnessError):
                HARNESS.StagingConfig.from_environment()
        with patch.dict(
            os.environ,
            self.environment(MYSTIC_STAGING_DATABASE_URL="postgresql://fixture_user:fixture_password@db.other.supabase.co/postgres"),
            clear=True,
        ):
            with self.assertRaises(HARNESS.StagingHarnessError):
                HARNESS.StagingConfig.from_environment()

    def test_safe_metadata_never_contains_connection_material(self) -> None:
        with patch.dict(os.environ, self.environment(), clear=True):
            config = HARNESS.StagingConfig.from_environment()
        safe = config.safe_metadata()
        rendered = str(safe)
        self.assertEqual(safe["project_ref"], HARNESS.STAGING_PROJECT_REF)
        self.assertNotIn("fixture_password", rendered)
        self.assertNotIn("fixture_user", rendered)
        self.assertNotIn("postgresql://", rendered)

    def test_sql_literal_escapes_fixture_identifiers(self) -> None:
        self.assertEqual(HARNESS._quote("a'b"), "'a''b'")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

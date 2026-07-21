from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts import install_mystic_engine_runner_launchd as installer


class EngineRunnerLaunchdTests(unittest.TestCase):
    def test_installer_rejects_temporary_checkout(self) -> None:
        with self.assertRaisesRegex(ValueError, "persistent repository checkout"):
            installer.persistent_repository_root("/private/tmp/mystic-stale")

    def test_service_definition_uses_validated_persistent_root(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.home() / "Library" / "Caches") as directory:
            root = Path(directory)
            runner = root / "scripts" / "mystic_engine_runner.py"
            runner.parent.mkdir(parents=True)
            runner.touch()
            validated = installer.persistent_repository_root(root)
            definition = installer.service_definition(validated, "/opt/mystic/.venv/bin/python")

        self.assertEqual(definition["WorkingDirectory"], str(root))
        self.assertEqual(definition["ProgramArguments"], ["/opt/mystic/.venv/bin/python", str(runner), "--start"])
        self.assertNotIn("MYSTIC_ENGINE_RUNNER_TOKEN", definition["EnvironmentVariables"])

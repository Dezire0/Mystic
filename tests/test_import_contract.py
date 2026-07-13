from __future__ import annotations

from pathlib import Path
import subprocess
import unittest


class ImportContractTests(unittest.TestCase):
    def test_installed_mystic_and_script_helpers_import(self) -> None:
        import mystic  # noqa: F401
        from scripts import run_research_table_e2e  # noqa: F401

    def test_worker_module_imports_without_runtime_secrets(self) -> None:
        root = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            ["node", "--input-type=module", "-e", "import './cloudflare/mystic_public_gateway_worker.js'; console.log('worker-ok');"],
            cwd=root,
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(completed.stdout.strip(), "worker-ok")

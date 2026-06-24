from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mystic.training.environment import audit_training_environment
from mystic.training.executor import build_backend_command, record_training_job
from mystic.training.launcher import build_training_plan
from mystic.training.modeling import run_local_training


class TrainingExecutionTests(unittest.TestCase):
    def test_environment_audit_has_backend_map(self):
        payload = audit_training_environment()
        self.assertIn("recommended_backends", payload)
        self.assertIn("manual", payload["recommended_backends"])

    def test_backend_command_for_manual(self):
        root = Path(__file__).resolve().parents[1]
        plan = build_training_plan(root, "raven")
        command = build_backend_command(plan, "manual")
        self.assertIn("mystic.training.run", command)
        self.assertEqual(command[0], plan["python_executable"])
        self.assertIn("--dry-run", command)

    def test_backend_command_for_manual_execute(self):
        root = Path(__file__).resolve().parents[1]
        plan = build_training_plan(root, "raven")
        command = build_backend_command(plan, "manual", dry_run=False)
        self.assertIn("--execute", command)

    def test_record_training_job_writes_manifest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "mystic_data" / "logs").mkdir(parents=True, exist_ok=True)
            plan = {
                "agent": "raven",
                "adapter_name": "raven_lora_v0",
                "base_model": "qwen3-14b",
                "train_ready_path": "path.jsonl",
                "source_manifest": "manifest.json",
                "output_dir": "output",
            }
            path = record_training_job(root, plan, "manual", ["python3"], True)
            self.assertTrue(path.exists())

    def test_local_training_plan_uses_smoke_model(self):
        root = Path(__file__).resolve().parents[1]
        payload = run_local_training(root, "raven", dry_run=True)
        self.assertEqual(payload["plan"]["model_name"], "sshleifer/tiny-gpt2")
        self.assertEqual(payload["executed"], False)


if __name__ == "__main__":
    unittest.main()

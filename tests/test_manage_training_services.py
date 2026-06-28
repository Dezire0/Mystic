from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.manage_continuous_training import daemon_command as continuous_daemon_command
from scripts.manage_continuous_training import plist_payload as continuous_plist_payload
from scripts.manage_continuous_training import service_program_arguments as continuous_service_program_arguments
from scripts.manage_remote_cycle_service import daemon_command as remote_daemon_command
from scripts.manage_remote_cycle_service import plist_payload as remote_plist_payload
from scripts.manage_remote_cycle_service import service_program_arguments as remote_service_program_arguments


class ManageTrainingServicesTests(unittest.TestCase):
    def test_continuous_service_uses_caffeinate_by_default(self):
        args = argparse.Namespace(
            base_dir="/tmp/mystic_data",
            backend="manual",
            cycle_sleep_seconds=0,
            error_sleep_seconds=60,
            hf_base_rows=25,
            numina_base_limit=1500,
            public_base_rows_per_agent=50,
            epochs=1,
            max_steps=20,
            learning_rate=0.00015,
            sequence_length=512,
            step_timeout_seconds=600,
            cycle_timeout_seconds=7200,
            hf_slugs=["openmathinstruct_2"],
            allow_system_sleep=False,
        )
        with patch("scripts.manage_continuous_training.ROOT", Path("/repo")):
            daemon = continuous_daemon_command(args)
            wrapped = continuous_service_program_arguments(args)
        self.assertEqual(daemon[0], "/repo/.venv-training/bin/python")
        self.assertEqual(wrapped[:3], ["/usr/bin/caffeinate", "-i", "-s"])
        self.assertEqual(wrapped[3:], daemon)

    def test_continuous_plist_can_opt_out_of_sleep_prevention(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            args = argparse.Namespace(
                base_dir=temp_dir,
                backend="manual",
                cycle_sleep_seconds=0,
                error_sleep_seconds=60,
                hf_base_rows=25,
                numina_base_limit=1500,
                public_base_rows_per_agent=50,
                epochs=1,
                max_steps=20,
                learning_rate=0.00015,
                sequence_length=512,
                step_timeout_seconds=600,
                cycle_timeout_seconds=7200,
                hf_slugs=[],
                allow_system_sleep=True,
            )
            with patch("scripts.manage_continuous_training.ROOT", Path("/repo")):
                payload = continuous_plist_payload(args)
        self.assertEqual(payload["ProgramArguments"][0], "/repo/.venv-training/bin/python")

    def test_remote_service_uses_caffeinate_by_default(self):
        args = argparse.Namespace(
            base_dir="/tmp/mystic_data",
            base_model="Qwen/Qwen2.5-0.5B-Instruct",
            cycle_prefix="remote_cycle",
            adapter_prefix="raven_lora_remote",
            model_suffix="qwen_0_5b",
            sleep_seconds=0,
            error_sleep_seconds=180,
            poll_seconds=60,
            timeout_minutes=240,
            limit=0,
            train_limit=1000,
            eval_limit=100,
            learning_rate=0.00015,
            epochs=1,
            batch_size=1,
            max_length=2048,
            run_limit=20,
            compare_limit=100,
            allow_system_sleep=False,
        )
        with patch("scripts.manage_remote_cycle_service.ROOT", Path("/repo")):
            daemon = remote_daemon_command(args)
            wrapped = remote_service_program_arguments(args)
        self.assertEqual(daemon[0], "/repo/.venv-training/bin/python")
        self.assertEqual(wrapped[:3], ["/usr/bin/caffeinate", "-i", "-s"])
        self.assertEqual(wrapped[3:], daemon)

    def test_remote_plist_writes_launchd_logs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            args = argparse.Namespace(
                base_dir=temp_dir,
                base_model="Qwen/Qwen2.5-0.5B-Instruct",
                cycle_prefix="remote_cycle",
                adapter_prefix="raven_lora_remote",
                model_suffix="qwen_0_5b",
                sleep_seconds=0,
                error_sleep_seconds=180,
                poll_seconds=60,
                timeout_minutes=240,
                limit=0,
                train_limit=1000,
                eval_limit=100,
                learning_rate=0.00015,
                epochs=1,
                batch_size=1,
                max_length=2048,
                run_limit=20,
                compare_limit=100,
                allow_system_sleep=False,
            )
            with patch("scripts.manage_remote_cycle_service.ROOT", Path("/repo")):
                payload = remote_plist_payload(args)
        self.assertTrue(payload["StandardOutPath"].endswith("remote_cycle.launchd.stdout.log"))
        self.assertEqual(payload["ProgramArguments"][0], "/usr/bin/caffeinate")


if __name__ == "__main__":
    unittest.main()

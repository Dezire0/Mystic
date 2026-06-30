from __future__ import annotations

import argparse
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.manage_mystic_public_tunnel_service import daemon_command, plist_payload


class MysticPublicTunnelServiceTests(unittest.TestCase):
    def test_daemon_command_includes_gist_and_local_url(self):
        args = argparse.Namespace(
            base_dir="/tmp/mystic",
            python_bin="/tmp/python",
            local_url="http://127.0.0.1:8765",
            gist_id="gist-123",
            gist_file="mystic-origin.json",
            public_url="https://mystic.dexproject.workers.dev",
        )
        with patch("scripts.manage_mystic_public_tunnel_service.ROOT", Path("/repo")):
            command = daemon_command(args)
        self.assertEqual(command[0], str(Path("/tmp/python").resolve()))
        self.assertEqual(command[1], str(Path("/repo/scripts/run_mystic_public_tunnel.py")))
        self.assertIn("--gist-id", command)
        self.assertIn("gist-123", command)
        self.assertIn("--local-url", command)
        self.assertIn("http://127.0.0.1:8765", command)

    def test_plist_payload_writes_expected_logs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            args = argparse.Namespace(
                base_dir=temp_dir,
                python_bin="/tmp/python",
                local_url="http://127.0.0.1:8765",
                gist_id="gist-123",
                gist_file="mystic-origin.json",
                public_url="https://mystic.dexproject.workers.dev",
            )
            with patch("scripts.manage_mystic_public_tunnel_service.ROOT", Path("/repo")):
                payload = plist_payload(args)
        self.assertEqual(payload["Label"], "com.mystic.public-tunnel")
        self.assertTrue(payload["StandardOutPath"].endswith("mystic_public_tunnel.launchd.stdout.log"))
        self.assertTrue(payload["StandardErrorPath"].endswith("mystic_public_tunnel.launchd.stderr.log"))


if __name__ == "__main__":
    unittest.main()

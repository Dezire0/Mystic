from __future__ import annotations

import argparse
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.manage_mystic_web_service import daemon_command, healthcheck, plist_payload


class MysticWebServiceTests(unittest.TestCase):
    def test_daemon_command_uses_uvicorn_with_host_and_port(self):
        args = argparse.Namespace(
            base_dir="/tmp/mystic",
            python_bin="/tmp/python",
            host="127.0.0.1",
            port=8765,
        )
        command = daemon_command(args)
        self.assertEqual(
            command,
            [
                str(Path("/tmp/python").resolve()),
                "-m",
                "uvicorn",
                "mystic.app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8765",
            ],
        )

    def test_plist_payload_writes_expected_logs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            args = argparse.Namespace(
                base_dir=temp_dir,
                python_bin="/tmp/python",
                host="127.0.0.1",
                port=8765,
            )
            with patch("scripts.manage_mystic_web_service.ROOT", Path("/repo")):
                payload = plist_payload(args)
        self.assertEqual(payload["Label"], "com.mystic.web")
        self.assertTrue(payload["StandardOutPath"].endswith("mystic_web.launchd.stdout.log"))
        self.assertTrue(payload["StandardErrorPath"].endswith("mystic_web.launchd.stderr.log"))

    def test_healthcheck_reports_error_when_server_is_unavailable(self):
        result = healthcheck("127.0.0.1", 65534)
        self.assertFalse(result["ok"])
        self.assertIn("/health", result["url"])


if __name__ == "__main__":
    unittest.main()

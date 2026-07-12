from __future__ import annotations

import io
import json
from pathlib import Path
import struct
import unittest

from scripts import mystic_gemini_app_native_host as host


ROOT = Path(__file__).resolve().parents[1]


class GeminiAppManualRelayTests(unittest.TestCase):
    def test_extension_has_only_native_messaging_and_storage_permissions(self) -> None:
        manifest = json.loads((ROOT / "local/gemini_app_bridge_extension/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["permissions"], ["nativeMessaging", "storage"])
        self.assertNotIn("host_permissions", manifest)
        self.assertNotIn("content_scripts", manifest)
        self.assertNotIn("cookies", json.dumps(manifest))
        self.assertNotIn("debugger", json.dumps(manifest))
        self.assertNotIn("webRequest", json.dumps(manifest))

    def test_extension_is_manual_send_only(self) -> None:
        source = (ROOT / "local/gemini_app_bridge_extension/background.js").read_text(encoding="utf-8")
        popup = (ROOT / "local/gemini_app_bridge_extension/popup.js").read_text(encoding="utf-8")
        self.assertIn('complianceLevel: "manual_send"', source)
        self.assertIn("bridge_import_visible_response", popup)
        self.assertIn("Preview Response", (ROOT / "local/gemini_app_bridge_extension/popup.html").read_text(encoding="utf-8"))
        self.assertNotIn("scripting.executeScript", source)
        self.assertNotIn("document.querySelector", source)

    def test_native_message_framing_and_size_limit(self) -> None:
        payload = json.dumps({"operation": "relay_status"}).encode("utf-8")
        self.assertEqual(host.read_frame(io.BytesIO(struct.pack("<I", len(payload)) + payload)), {"operation": "relay_status"})
        with self.assertRaises(ValueError):
            host.read_frame(io.BytesIO(struct.pack("<I", host.MAX_MESSAGE_BYTES + 1)))

    def test_native_host_rejects_unknown_operations_and_unapproved_origins(self) -> None:
        with self.assertRaises(ValueError):
            host.validate_operation({"operation": "run_shell"})
        extension_id = "abcdefghijklmnopabcdefghijklmnop"
        self.assertTrue(host.approved_extension(["host", f"chrome-extension://{extension_id}/"], {"extension_id": extension_id}))
        self.assertFalse(host.approved_extension(["host", "chrome-extension://other/"], {"extension_id": extension_id}))

    def test_response_requires_explicit_visible_text(self) -> None:
        relay = host.RelayHost(io.BytesIO())
        relay.handle({"operation": "relay_start"}, local=False)
        relay.handle({"operation": "job_next", "job": {"job_id": "job-1", "run_id": "run-1", "session_id": "session-1", "prompt_text": "manual prompt"}}, local=True)
        self.assertEqual(relay.handle({"operation": "response_submit", "job_id": "job-1", "response_text": ""}, local=False)["status"], "invalid_response")
        self.assertEqual(relay.handle({"operation": "response_submit", "job_id": "job-1", "response_text": "Visible answer"}, local=False)["status"], "response_ready")

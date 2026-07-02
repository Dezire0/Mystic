from __future__ import annotations

import json
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKER_PATH = ROOT / "cloudflare" / "mystic_public_gateway_worker.js"


def run_worker_helper(helper: str, payload: dict[str, object]) -> dict[str, object]:
    script = """
import { __test } from './cloudflare/mystic_public_gateway_worker.js';
const helper = process.argv[1];
const payload = JSON.parse(process.argv[2]);
const result = await __test[helper](payload);
console.log(JSON.stringify(result));
"""
    completed = subprocess.run(
        ["node", "--input-type=module", "-e", script, helper, json.dumps(payload)],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(completed.stdout)


class OAuthMetadataTests(unittest.TestCase):
    def test_oauth_disabled_reports_not_configured(self) -> None:
        result = run_worker_helper("describeOAuth", {"env": {}, "requestUrl": "https://mystic.dexproject.workers.dev/mcp"})
        self.assertFalse(result["enabled"])
        self.assertFalse(result["configured"])
        self.assertFalse(result["metadataAvailable"])

    def test_oauth_metadata_present_exposes_expected_endpoints(self) -> None:
        env = {
            "MYSTIC_OAUTH_ENABLED": "true",
            "MYSTIC_OAUTH_ISSUER": "https://mystic.dexproject.workers.dev",
            "MYSTIC_OAUTH_SIGNING_SECRET": "secret-signing-key",
        }
        protected_resource = run_worker_helper(
            "buildProtectedResourceMetadata",
            {"env": env, "requestUrl": "https://mystic.dexproject.workers.dev/mcp"},
        )
        authorization_server = run_worker_helper(
            "buildAuthorizationServerMetadata",
            {"env": env, "requestUrl": "https://mystic.dexproject.workers.dev/mcp"},
        )
        self.assertEqual(protected_resource["resource"], "https://mystic.dexproject.workers.dev/mcp")
        self.assertEqual(
            protected_resource["authorization_servers"],
            ["https://mystic.dexproject.workers.dev"],
        )
        self.assertEqual(
            authorization_server["authorization_endpoint"],
            "https://mystic.dexproject.workers.dev/oauth/authorize",
        )
        self.assertEqual(
            authorization_server["token_endpoint"],
            "https://mystic.dexproject.workers.dev/oauth/token",
        )
        self.assertNotIn("registration_endpoint", authorization_server)


if __name__ == "__main__":
    unittest.main()

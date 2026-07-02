from __future__ import annotations

import json
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


def run_worker_helper(helper: str, payload: dict[str, object]) -> dict[str, object] | str:
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


class PublicGatewayOAuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.env = {
            "MYSTIC_OAUTH_ENABLED": "true",
            "MYSTIC_OAUTH_ISSUER": "https://mystic.dexproject.workers.dev",
            "MYSTIC_OAUTH_SIGNING_SECRET": "secret-signing-key",
            "MYSTIC_OAUTH_DEV_STATIC_TOKEN": "dev-static-token",
        }
        self.request_url = "https://mystic.dexproject.workers.dev/mcp"

    def test_missing_token_returns_auth_required(self) -> None:
        result = run_worker_helper("simulateMcpAuth", {"env": self.env, "requestUrl": self.request_url})
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], 401)
        self.assertIn("www-authenticate", result["headers"])
        self.assertIn("resource_metadata", result["headers"]["www-authenticate"])

    def test_valid_static_bearer_token_is_accepted(self) -> None:
        result = run_worker_helper(
            "simulateMcpAuth",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": {"Authorization": "Bearer dev-static-token"},
            },
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["auth"]["sub"], "mystic-dev-static-token")

    def test_invalid_bearer_token_is_rejected(self) -> None:
        result = run_worker_helper(
            "simulateMcpAuth",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "headers": {"Authorization": "Bearer wrong-token"},
            },
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], 401)

    def test_authorization_code_exchange_issues_valid_access_token(self) -> None:
        code_verifier = "pkce-secret-verifier"
        code_challenge = run_worker_helper("pkceChallenge", {"codeVerifier": code_verifier})
        code = run_worker_helper(
            "issueAuthorizationCode",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "clientId": "chatgpt-client",
                "redirectUri": "https://example.com/callback",
                "codeChallenge": code_challenge,
            },
        )
        exchanged = run_worker_helper(
            "exchangeAuthorizationCode",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "code": code,
                "clientId": "chatgpt-client",
                "redirectUri": "https://example.com/callback",
                "codeVerifier": code_verifier,
            },
        )
        self.assertTrue(exchanged["ok"])
        validated = run_worker_helper(
            "validateAccessToken",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "token": exchanged["access_token"],
            },
        )
        self.assertTrue(validated["valid"])
        self.assertEqual(validated["payload"]["aud"], self.request_url)


if __name__ == "__main__":
    unittest.main()

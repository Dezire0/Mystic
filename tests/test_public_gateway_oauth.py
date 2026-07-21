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
        self.chatgpt_client_id = "mystic-chatgpt"
        self.chatgpt_callback = "https://chatgpt.com/connector/oauth/wpja_UKVNtTE"

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
                "clientId": self.chatgpt_client_id,
                "redirectUri": self.chatgpt_callback,
                "codeChallenge": code_challenge,
            },
        )
        exchanged = run_worker_helper(
            "exchangeAuthorizationCode",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "code": code,
                "clientId": self.chatgpt_client_id,
                "redirectUri": self.chatgpt_callback,
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

    def test_fixed_chatgpt_callback_is_exact_and_unknown_client_is_rejected(self) -> None:
        verifier = "fixed-callback-verifier"
        challenge = run_worker_helper("pkceChallenge", {"codeVerifier": verifier})
        allowed = run_worker_helper(
            "simulateRequest",
            {"env": self.env, "requestUrl": f"https://mystic.dexproject.workers.dev/oauth/authorize?response_type=code&client_id={self.chatgpt_client_id}&redirect_uri={self.chatgpt_callback}&state=state&scope=tools%3Aread%20tools%3Aexecute&code_challenge={challenge}&code_challenge_method=S256", "method": "GET"},
        )
        self.assertEqual(allowed["status"], 200)
        modified = run_worker_helper(
            "simulateRequest",
            {"env": self.env, "requestUrl": f"https://mystic.dexproject.workers.dev/oauth/authorize?response_type=code&client_id={self.chatgpt_client_id}&redirect_uri=https%3A%2F%2Fchatgpt.com%2Fconnector%2Foauth%2Fwrong&state=state&scope=tools%3Aread&code_challenge={challenge}&code_challenge_method=S256", "method": "GET"},
        )
        self.assertEqual(modified["status"], 400)
        self.assertIn("registered OAuth client", modified["body"]["error"])
        unknown = run_worker_helper(
            "simulateRequest",
            {"env": self.env, "requestUrl": f"https://mystic.dexproject.workers.dev/oauth/authorize?response_type=code&client_id=unknown&redirect_uri={self.chatgpt_callback}&state=state&scope=tools%3Aread&code_challenge={challenge}&code_challenge_method=S256", "method": "GET"},
        )
        self.assertEqual(unknown["status"], 400)

    def test_metadata_does_not_advertise_unimplemented_dcr_or_oidc(self) -> None:
        env = {**self.env, "MYSTIC_OAUTH_DYNAMIC_CLIENT_REGISTRATION_ENABLED": "true"}
        metadata = run_worker_helper("simulateRequest", {"env": env, "requestUrl": "https://mystic.dexproject.workers.dev/.well-known/oauth-authorization-server", "method": "GET"})
        self.assertEqual(metadata["status"], 200)
        self.assertNotIn("registration_endpoint", metadata["body"])
        self.assertNotIn("userinfo_endpoint", metadata["body"])
        self.assertNotIn("example.com", json.dumps(metadata["body"]))
        registration = run_worker_helper("simulateRequest", {"env": env, "requestUrl": "https://mystic.dexproject.workers.dev/oauth/register", "method": "POST"})
        self.assertEqual(registration["status"], 404)

    def test_plain_pkce_and_unallowlisted_scope_are_rejected(self) -> None:
        verifier = "pkce-enforcement-verifier"
        challenge = run_worker_helper("pkceChallenge", {"codeVerifier": verifier})
        plain = run_worker_helper(
            "simulateRequest",
            {"env": self.env, "requestUrl": f"https://mystic.dexproject.workers.dev/oauth/authorize?response_type=code&client_id={self.chatgpt_client_id}&redirect_uri={self.chatgpt_callback}&state=state&scope=tools%3Aread&code_challenge={challenge}&code_challenge_method=plain", "method": "GET"},
        )
        self.assertEqual(plain["status"], 400)
        self.assertIn("PKCE S256", plain["body"]["error"])
        scope = run_worker_helper(
            "simulateRequest",
            {"env": self.env, "requestUrl": f"https://mystic.dexproject.workers.dev/oauth/authorize?response_type=code&client_id={self.chatgpt_client_id}&redirect_uri={self.chatgpt_callback}&state=state&scope=tools%3Aread%20home%3Acontrol&code_challenge={challenge}&code_challenge_method=S256", "method": "GET"},
        )
        self.assertEqual(scope["status"], 400)
        self.assertIn("scope is not allowed", scope["body"]["error"])

    def test_authorization_code_is_single_use_and_bound_to_registered_redirect_uri(self) -> None:
        verifier = "single-use-pkce-verifier"
        challenge = run_worker_helper("pkceChallenge", {"codeVerifier": verifier})
        flow = run_worker_helper(
            "exerciseAuthorizeFlow",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "clientId": self.chatgpt_client_id,
                "redirectUri": self.chatgpt_callback,
                "stateValue": "single-use-state",
                "codeChallenge": challenge,
                "codeVerifier": verifier,
            },
        )
        self.assertEqual(flow["pageStatus"], 200)
        self.assertEqual(flow["approvalStatus"], 302)
        self.assertTrue(flow["firstExchange"]["ok"])
        self.assertFalse(flow["secondExchange"]["ok"])
        self.assertEqual(flow["secondExchange"]["error"], "invalid_grant")

        code = run_worker_helper(
            "issueAuthorizationCode",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "clientId": self.chatgpt_client_id,
                "redirectUri": self.chatgpt_callback,
                "codeChallenge": challenge,
            },
        )
        mismatch = run_worker_helper(
            "exchangeAuthorizationCode",
            {
                "env": self.env,
                "requestUrl": self.request_url,
                "code": code,
                "clientId": self.chatgpt_client_id,
                "redirectUri": "https://chatgpt.com/connector/oauth/wrong",
                "codeVerifier": verifier,
            },
        )
        self.assertFalse(mismatch["ok"])
        self.assertEqual(mismatch["error"], "invalid_grant")


if __name__ == "__main__":
    unittest.main()

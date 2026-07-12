# Mystic LAB Provider Connect

## Purpose

Provider Connect is the safe connection layer for external model providers in Mystic LAB.

It exists to let Mystic expose:

- provider status
- provider setup guidance
- provider OAuth connect entry points where genuinely supported
- secure setup pages for API-key providers
- real provider-backed model calls once a provider is explicitly configured

It does **not** exist to:

- ask for raw passwords
- perform hidden third-party logins
- print API keys or tokens
- store raw provider secrets in Supabase
- fake model output

## Current Providers

- `openai_compatible`
- `gemini`
- `google_vertex_ai`
- `anthropic`
- `future_custom`

## Public MCP Tools

- `provider_list`
- `provider_status`
- `provider_connect_start`
- `provider_connect_callback_status`
- `provider_configure_secret_instructions`
- `provider_verify`
- `provider_disconnect`
- `provider_model_list`
- `provider_call_test`

## Current Routing Surface

Provider Connect now backs real model-call routing for:

- `provider_call_test`
- explicit `lab_agent_run`
- provider-backed `lab_models_debate`
- optional provider-backed `lab_referee_review`

When a provider call runs, Mystic stores only safe call metadata:

- `provider_id`
- `model`
- `tool_name`
- `agent_role`
- `prompt_hash`
- bounded `prompt_excerpt_safe`
- `output_text`
- `status`
- `error_type`
- `latency_ms`
- safe usage metadata

These records are stored in local `mystic_data/model_calls/` or in the Supabase `model_calls` table.

## Route Surface

The Cloudflare Worker now exposes provider pages and callback routes:

- `GET /providers`
- `GET /providers/:provider_id/connect`
- `GET /providers/:provider_id/setup`
- `POST /providers/:provider_id/secret`
- `GET /providers/:provider_id/status`
- `GET /providers/oauth/callback`

These routes show only safe metadata:

- provider status
- required auth method
- required secret names
- configured vs missing secret names
- OAuth callback state

They never show:

- stored secret values
- raw OAuth tokens
- raw API keys
- raw passwords

## OAuth vs API-key Providers

### Gemini

- `gemini` remains the Google AI Studio and Gemini API provider.
- It is intentionally API-key based in Mystic LAB.
- `provider_connect_start` returns `api_key_required` and a secure Mystic setup page URL when the API key is missing.
- Mystic must not treat `gemini` as the Google OAuth or Vertex AI provider.

### Google Vertex AI

- `google_vertex_ai` is the separate Google OAuth-backed provider for Vertex AI Gemini access.
- When real OAuth metadata is configured, `provider_connect_start` returns a real Google `authorization_url`.
- Required configuration is:
  - `MYSTIC_PROVIDER_GOOGLE_VERTEX_OAUTH_ENABLED`
  - `MYSTIC_PROVIDER_GOOGLE_VERTEX_CLIENT_ID`
  - `MYSTIC_PROVIDER_GOOGLE_VERTEX_CLIENT_SECRET`
  - `MYSTIC_PROVIDER_GOOGLE_VERTEX_PROJECT_ID`
  - `MYSTIC_PROVIDER_GOOGLE_VERTEX_LOCATION`
- Optional configuration is:
  - `MYSTIC_PROVIDER_GOOGLE_VERTEX_MODEL`
- Encrypted token storage also requires:
  - `MYSTIC_PROVIDER_TOKEN_ENCRYPTION_KEY`
- Current safe behavior:
  - callback receipt is supported
  - token exchange only runs when the encryption key is configured
  - `provider_verify` reports `connected` only when an encrypted OAuth token record exists
  - `provider_call_test` still fails closed after connection because real Vertex inference routing is intentionally separate
  - if callback storage is unavailable, the safe status is `token_storage_required`

### Gemini App Manual Relay

- `gemini_app_ui_bridge` is displayed as **Gemini App Manual Relay** and has `provider_type=local_human_relay`, `auth_method=user_managed_app_session`, `execution_location=user_machine`, and `automation_mode=manual_send`.
- It is not a provider login, API-key integration, or automated browser bridge. The Worker starts an authenticated queue job, then the user explicitly copies the prompt into the official Gemini UI and explicitly imports the visible response.
- The Chrome extension has only `nativeMessaging` and `storage` permissions. It has no Gemini host permission, no content script, and no cookie, debugger, history, or webRequest access.
- The local runner owns the existing Mystic bearer token and sends it only to authenticated `/local-relay/*` Worker endpoints. The extension and Native Messaging manifest never receive the token.
- ChatGPT remains the controller. It uses `lab_orchestrated_run_start`, `lab_orchestrated_run_wait`, `lab_orchestrated_run_get`, `lab_orchestrated_run_continue`, and `lab_orchestrated_run_cancel` to retrieve complete paginated transcripts, critique imported output, request an optional rebuttal, and synthesize the final answer.

### Anthropic

- Mystic does not pretend Anthropic OAuth exists by default.
- If official OAuth metadata is configured in a future deployment, `provider_connect_start` can return a real `authorization_url`.
- Otherwise Mystic returns `api_key_required` and a secure setup page URL.

### OpenAI-compatible

- Default behavior is API-key setup, not fake OAuth.
- `provider_connect_start` returns `api_key_required` with a secure setup page unless custom OAuth metadata is explicitly configured.

### Future Custom Providers

- `future_custom` supports metadata-driven OAuth.
- When `authorization_endpoint`, `client_id`, `redirect_uri`, and enabled mode are configured, `provider_connect_start` returns a real `authorization_url`.
- PKCE metadata and hashed state are persisted for safe callback tracking.

## Secret Storage Boundary

Provider secrets must remain outside Supabase.

Allowed storage targets:

- Cloudflare Worker secret storage
- approved encrypted server-side secret storage

For ChatGPT remote MCP readiness in Worker mode, the validated manual import artifact may be mirrored into runtime configuration through `MYSTIC_CHATGPT_IMPORT_VERIFICATION_JSON`. That payload must remain sanitized and must not contain raw tokens, secrets, or passwords.

Supabase may store only:

- provider connection metadata
- provider status
- auth flow metadata
- callback timestamps
- failure reasons

Supabase must not store:

- raw API keys
- raw bearer tokens
- raw OAuth tokens
- raw passwords

## Why Passwords Are Never Used

Mystic LAB does not implement provider login by collecting user passwords.

Reasons:

- it would create an unnecessary credential-handling boundary
- it would blur the line between Mystic OAuth and third-party provider auth
- it would increase the blast radius of any logging or storage mistake

Mystic only supports:

- real provider OAuth authorization URLs where the provider actually supports OAuth and Mystic has real client metadata
- API-key setup flows where the provider uses keys instead of OAuth

## Cloudflare Secret Setup

The setup pages and tools expose exact secret names, for example:

- `MYSTIC_PROVIDER_OPENAI_COMPAT_API_KEY`
- `MYSTIC_PROVIDER_OPENAI_COMPAT_BASE_URL`
- `MYSTIC_PROVIDER_OPENAI_COMPAT_MODEL`
- `MYSTIC_PROVIDER_GEMINI_API_KEY`
- `MYSTIC_PROVIDER_GEMINI_MODEL`
- `MYSTIC_PROVIDER_GOOGLE_VERTEX_CLIENT_ID`
- `MYSTIC_PROVIDER_GOOGLE_VERTEX_CLIENT_SECRET`
- `MYSTIC_PROVIDER_GOOGLE_VERTEX_PROJECT_ID`
- `MYSTIC_PROVIDER_GOOGLE_VERTEX_LOCATION`
- `MYSTIC_PROVIDER_GOOGLE_VERTEX_MODEL`
- `MYSTIC_PROVIDER_TOKEN_ENCRYPTION_KEY`
- `MYSTIC_PROVIDER_ANTHROPIC_API_KEY`
- `MYSTIC_PROVIDER_ANTHROPIC_MODEL`

If direct secret writing is not available in the current deployment, Mystic returns manual Cloudflare instructions such as:

```bash
wrangler secret put MYSTIC_PROVIDER_GEMINI_API_KEY --name mystic
```

## Callback Handling

The Worker callback route records safe OAuth callback state:

- `callback_received_at`
- `failure_reason`
- whether an authorization code was received
- hashed state validation result

It does not display or echo raw authorization codes or tokens.

Current behavior:

- raw authorization codes are never displayed back to the user
- if `MYSTIC_PROVIDER_TOKEN_ENCRYPTION_KEY` is missing, callback completion fails closed with `token_storage_required`
- if the encryption key is present, Mystic exchanges the authorization code and stores only encrypted OAuth token records
- provider pages and MCP outputs expose only safe token metadata such as presence flags and sanitized scope data
- `google_vertex_ai` model-call routing is still intentionally deferred after connection, so connected token storage does not yet imply live Vertex inference

## Security Guardrail

Mystic LAB must fail closed:

- unsupported OAuth configuration returns `provider_required` or `api_key_required`
- missing API-key configuration returns `api_key_required`
- missing encrypted token storage returns `token_storage_required`
- invalid provider credentials return `provider_auth_failed`
- provider rate limits return `rate_limited`
- provider downtime returns `provider_unavailable`
- direct secret writes remain unavailable unless explicitly configured through approved infrastructure

Provider Connect must never invent credentials, fake OAuth support, fake model execution, or store raw provider secrets in call records.

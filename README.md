# Mystic LAB

Mystic LAB is an AI Research Lab OS. It combines the existing Raven training loop and research tooling with a lab-session orchestration layer, MCP access, cloud-native Worker deployment, and a staged roadmap toward engine-backed research execution and a 3D virtual lab.

The current repository state includes:

- the legacy/local JSONL Raven loop
- the local-first LAB session backend
- a public Cloudflare Worker + Supabase cloud-native LAB mode
- ChatGPT remote MCP import support with `import_ready=true`
- the original 13 LAB tools preserved in cloud-native mode, plus the 10 new Phase 1 scene/simulation tools
- the 9 Provider Connect foundation tools for safe external provider setup metadata and verification
- 32 public MCP tools visible in the current cloud-native Worker import surface

Reference docs:

- [docs/mystic_lab_os.md](/Users/JYH/Documents/Mystic/docs/mystic_lab_os.md)
- [docs/mystic_lab_roadmap.md](/Users/JYH/Documents/Mystic/docs/mystic_lab_roadmap.md)
- [docs/mystic_lab_3d_virtual_lab.md](/Users/JYH/Documents/Mystic/docs/mystic_lab_3d_virtual_lab.md)
- [docs/mystic_lab_engine_adapter_layer.md](/Users/JYH/Documents/Mystic/docs/mystic_lab_engine_adapter_layer.md)
- [docs/mystic_lab_domains.md](/Users/JYH/Documents/Mystic/docs/mystic_lab_domains.md)
- [docs/mystic_lab_provider_connect.md](/Users/JYH/Documents/Mystic/docs/mystic_lab_provider_connect.md)

The current LAB status is intentionally conservative:

- session orchestration is implemented
- provider routing exists for explicit external model access
- Provider Connect now returns real setup/connect destinations: real OAuth authorization URLs where configured and secure Mystic LAB setup pages where API-key auth is required
- `gemini` remains the API-key Gemini provider, while `google_vertex_ai` is the separate Google OAuth-backed Vertex AI Gemini provider
- real provider-backed routing is now implemented for `provider_call_test`, explicit `lab_agent_run`, provider-backed `lab_models_debate`, and optional provider-backed `lab_referee_review`
- safe `model_calls` records are persisted in local mode and Supabase for provider-backed execution traces
- unsupported heavy paths return structured `deferred`
- missing model providers return structured `provider_required`
- Phase 1 scene tools, deterministic simple physics, and `scene.three_json` export are implemented
- `math.sympy` exposes a deterministic subset in both local mode and the Worker for arithmetic evaluate, numeric substitution, simplify, and simple linear solve

Mystic LAB also reinjects the trained Raven adapter into the live JSONL research loop, adds base-vs-adapter comparison plus promotion logic, and exposes a local Research Table / debate UX through the FastAPI app and MCP server.

It keeps the design intentionally narrow:

- local folders under `mystic_data/` remain the default storage path
- append-only JSONL storage remains the default research/training loop
- resumable processing through `mystic_data/state/processed_ids.jsonl`
- optional Supabase-backed cloud-native LAB mode is available for public MCP
- no separate JS frontend bundle
- no vector DB
- no standalone web dashboard service outside the FastAPI app
- no paid VPS requirement for cloud-native public MCP

## Mystic LAB OS

Mystic LAB includes a local-first AI Research Lab OS backend. It is a computational research orchestration layer, not a wet-lab control system and not a game.

- lab sessions can be stored under `mystic_data/lab_sessions/` or in Supabase
- provider-backed call traces can be stored under `mystic_data/model_calls/` or in Supabase
- each session persists structured `session.json`, `turns.json`, `claims.json`, `experiments.json`, `failures.json`, `memory_edges.json`, `notebook.md`, and `report.md`
- the Research Table acts as the Model Arena and can import discoveries back into a lab session
- MCP `lab_*` tools expose session create/get/advance, role execution, referee review, experiment create/run, memory search/write, model debate, and report generation
- cloud-native Worker mode directly serves the preserved 13-tool LAB baseline plus the 10 new Phase 1 scene/simulation tools from Supabase without a local Mac backend
- Provider Connect adds 9 cloud-native provider management tools plus public setup/connect/status pages without requiring a local backend or storing provider secrets in Supabase

Provider Connect routes exposed by the Worker:

- `GET /providers`
- `GET /providers/:provider_id/connect`
- `GET /providers/:provider_id/setup`
- `POST /providers/:provider_id/secret`
- `GET /providers/:provider_id/status`
- `GET /providers/oauth/callback`

When OAuth metadata is configured, `GET /providers/:provider_id/connect` now starts the Provider Connect flow inside the Worker and returns an immediate `302` redirect to the provider login page instead of showing a manual-start placeholder.

For ChatGPT-facing clients, `provider_connect_start` also returns a short `user_action` object for OAuth-capable login flows. When `user_action.type=open_url`, render the short `connect_url` as a clickable link such as [Sign in with Google Vertex AI](https://mystic.dexproject.workers.dev/providers/google_vertex_ai/connect) instead of asking the user to copy a long `authorization_url`.

The core lab objects are:

- `LabSession`: top-level research workflow state
- `LabTurn`: structured role or tool output inside a session timeline
- `Claim`: hypothesis, lemma, result, observation, or assumption with explicit status
- `Experiment`: linked verification or simulation attempt
- `Failure`: archived fatal error, contradiction, counterexample, or unsupported step
- `MemoryEdge`: relation such as `supports`, `refutes`, `depends_on`, `caused_failure`, or `generated_experiment`

Reality Anchor status rules are intentionally conservative:

- model-only claims default to `HEURISTIC`
- deterministic invalidation becomes `REFUTED` or `FAILED`
- simulation-backed support becomes `TESTED`, not `PROVED`
- incomplete proofs become `NEEDS_MORE_DETAIL`
- only symbolic or strict manual validation should upgrade a claim to `PROVED`

The default backend is still local JSON. When `MYSTIC_STORAGE_BACKEND=supabase`, the Cloudflare Worker can serve the current cloud-native LAB tools directly from Supabase while the full local Python backend remains available for richer local workflows.

## Lab Failure to Raven Dataset

Failure Museum entries can also be exported into Raven-compatible critique rows. This step is GPU-free: it prepares additional training data, but it does not train a model, does not submit Kaggle jobs, and does not prove Raven improved.

The current Raven vNext status may still remain blocked by Kaggle GPU quota. Exporting and preparing lab failures does not change that status on its own.

Export reusable lab failures:

```bash
python scripts/export_lab_failure_datasets.py \
  --root-path /Users/JYH/Documents/Mystic \
  --target raven
```

Prepare a combined Raven dataset from Research Table rows, adversarial seeds, and lab failures:

```bash
python scripts/prepare_research_table_training.py \
  --root-path /Users/JYH/Documents/Mystic \
  --target raven \
  --include-adversarial-seeds \
  --include-lab-failures
```

Package the prepared split for the existing cycle workflow without submitting Kaggle:

```bash
python scripts/run_mystic_cycle.py prepare \
  --cycle-id raven_vnext_adversarial \
  --base-dir /Users/JYH/Documents/Mystic/mystic_data \
  --dataset-source research_table \
  --target raven \
  --include-adversarial-seeds \
  --include-lab-failures
```

Check readiness, optionally requiring exported lab failures to be present in the prepared dataset:

```bash
python scripts/check_raven_training_readiness.py \
  --root-path /Users/JYH/Documents/Mystic
```

## Files

- [scripts/setup_mystic_data.py](/Users/JYH/Documents/Mystic/scripts/setup_mystic_data.py)
- [scripts/download_numina_sample.py](/Users/JYH/Documents/Mystic/scripts/download_numina_sample.py)
- [scripts/mystic_loop.py](/Users/JYH/Documents/Mystic/scripts/mystic_loop.py)
- [scripts/export_raven_lora.py](/Users/JYH/Documents/Mystic/scripts/export_raven_lora.py)
- [scripts/prepare_raven_training_data.py](/Users/JYH/Documents/Mystic/scripts/prepare_raven_training_data.py)
- [scripts/train_raven_lora.py](/Users/JYH/Documents/Mystic/scripts/train_raven_lora.py)
- [scripts/evaluate_raven_lora.py](/Users/JYH/Documents/Mystic/scripts/evaluate_raven_lora.py)
- [scripts/register_model.py](/Users/JYH/Documents/Mystic/scripts/register_model.py)
- [scripts/compare_raven_models.py](/Users/JYH/Documents/Mystic/scripts/compare_raven_models.py)
- [scripts/promote_raven_adapter.py](/Users/JYH/Documents/Mystic/scripts/promote_raven_adapter.py)
- [mystic/llm_client.py](/Users/JYH/Documents/Mystic/mystic/llm_client.py)
- [mystic/prompts.py](/Users/JYH/Documents/Mystic/mystic/prompts.py)
- [mystic/parsers.py](/Users/JYH/Documents/Mystic/mystic/parsers.py)
- [mystic/raven_compare.py](/Users/JYH/Documents/Mystic/mystic/raven_compare.py)
- [mystic/schema.py](/Users/JYH/Documents/Mystic/mystic/schema.py)
- [mystic/raven_training.py](/Users/JYH/Documents/Mystic/mystic/raven_training.py)
- [configs/models.json](/Users/JYH/Documents/Mystic/configs/models.json)
- [configs/training_raven.json](/Users/JYH/Documents/Mystic/configs/training_raven.json)

## Data Layout

Running setup creates:

```text
mystic_data/
├── adapters/
├── eval_holdout/
├── exports/
├── internal/
├── logs/
├── reports/
├── processed/
├── raw/
├── rejected/
├── state/
├── train_ready/
└── verified/
```

Important files written by the loop:

- `mystic_data/raw/numina_math_cot_100.jsonl`
- `mystic_data/processed/mystic_loop_results.jsonl`
- `mystic_data/verified/verified.jsonl`
- `mystic_data/rejected/rejected.jsonl`
- `mystic_data/internal/failed_proofs.jsonl`
- `mystic_data/internal/raven_critiques.jsonl`
- `mystic_data/logs/run_log.jsonl`
- `mystic_data/logs/training_log.jsonl`
- `mystic_data/logs/raven_eval_results.jsonl`
- `mystic_data/logs/adapter_inference_log.jsonl`
- `mystic_data/logs/raven_comparison_results.jsonl`
- `mystic_data/logs/raven_promotion_log.jsonl`
- `mystic_data/reports/execution_history.html`
- `mystic_data/state/processed_ids.jsonl`
- `mystic_data/exports/raven_lora.jsonl`
- `mystic_data/train_ready/raven_lora.jsonl`
- `mystic_data/train_ready/raven_train.jsonl`
- `mystic_data/eval_holdout/raven_eval.jsonl`
- `mystic_data/adapters/raven_lora_tiny_gpt2_smoke/`
- `mystic_data/adapters/raven_lora_v0/training_config.json`
- `mystic_data/internal/failed_adapter_outputs.jsonl`

## Setup

Use the existing Python 3.11 environment in this repo:

```bash
.venv-training/bin/python scripts/setup_mystic_data.py
.venv-training/bin/python scripts/download_numina_sample.py --limit 100
```

## Deployment

Mystic's web UX is deployable on Vercel as a Python FastAPI app.

- Vercel uses the root [main.py](/Users/JYH/Documents/Mystic/main.py) entrypoint, which re-exports `mystic.app.main:app`.
- The repo pins the deployment runtime with [.python-version](/Users/JYH/Documents/Mystic/.python-version).
- `fastapi` is installed as a base dependency; `uvicorn` remains a local dev extra.

For local web serving:

```bash
python -m pip install -e '.[api]'
uvicorn mystic.app.main:app --host 127.0.0.1 --port 8765
```

## Persistent Local Service

For always-on local use without serverless execution limits, run the FastAPI app under `launchd` on macOS:

```bash
python scripts/manage_mystic_web_service.py install --host 127.0.0.1 --port 8765
python scripts/manage_mystic_web_service.py status --host 127.0.0.1 --port 8765
```

This keeps the web app running after terminal exit and reboot. It also exposes:

- `http://127.0.0.1:8765/health` for local health checks
- `http://127.0.0.1:8765/mcp` for persistent HTTP access to Mystic MCP JSON-RPC requests

## Fixed Public Endpoint

For a stable public URL in front of the always-on local service, this repo also supports:

- a Cloudflare Worker on `workers.dev` as the fixed public hostname
- a launchd-managed `cloudflared` quick tunnel that keeps the current tunnel origin published into a GitHub Gist

The quick tunnel path is useful for development, but it is temporary. If that origin expires, the Worker can still have correct OAuth metadata while public runtime MCP calls fail with `530`, `1016`, or generic `502` upstream errors.

Install the public tunnel service with:

```bash
python scripts/manage_mystic_public_tunnel_service.py install \
  --gist-id 778759ccca8f7d9a54c1f98662b6a9ec \
  --public-url https://mystic.dexproject.workers.dev

python scripts/manage_mystic_public_tunnel_service.py status \
  --gist-id 778759ccca8f7d9a54c1f98662b6a9ec \
  --public-url https://mystic.dexproject.workers.dev
```

The fixed public endpoints are expected to be:

- `https://mystic.dexproject.workers.dev/health`
- `https://mystic.dexproject.workers.dev/mcp`

## Free Cloud Deployment

Mystic LAB now supports a free-tier, cloud-native LAB MCP path that removes the dependency on a local Mac backend and quick tunnels for the core lab flow.

Architecture:

- ChatGPT
- Cloudflare Worker MCP/OAuth server
- Supabase Free Postgres for `lab_sessions`, `lab_turns`, `claims`, `failures`, `memory_edges`, and `reports`
- optional object storage later for reports and larger artifacts

Current cloud-native LAB tools exposed directly by the Worker:

- `mystic_status`
- `health_check`
- `lab_session_create`
- `lab_session_advance`
- `lab_agent_run`
- `lab_referee_review`
- `lab_experiment_create`
- `lab_experiment_run`
- `lab_memory_search`
- `lab_memory_write`
- `lab_models_debate`
- `lab_session_get`
- `lab_report_generate`

Cloud support levels:

- fully cloud-backed via Supabase: `mystic_status`, `health_check`, `lab_session_create`, `lab_session_advance`, `lab_experiment_create`, `lab_memory_search`, `lab_memory_write`, `lab_session_get`, `lab_report_generate`
- exposed with structured `deferred` responses until a worker-native executor exists: `lab_experiment_run`, `lab_models_debate` when `use_existing_research_table=false`, and `lab_referee_review` when no deterministic or explicit provider-backed referee path is selected
- exposed with structured `provider_required`, `api_key_required`, `provider_auth_failed`, `rate_limited`, or `provider_unavailable` responses when an external model provider cannot complete the requested call safely

External model providers are never auto-logged-in by the Worker. Cloud-native model actions require explicit provider authorization through Cloudflare secrets or approved provider connection records.

### Supabase setup

Apply the schema in [supabase/mystic_lab_v0_schema.sql](/Users/JYH/Documents/Mystic/supabase/mystic_lab_v0_schema.sql).

Worker environment variables use placeholders only. Do not commit real values:

```text
MYSTIC_STORAGE_BACKEND=supabase
MYSTIC_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
MYSTIC_SUPABASE_SERVICE_ROLE_KEY=YOUR_SERVICE_ROLE_KEY
MYSTIC_SUPABASE_SCHEMA=public
MYSTIC_OAUTH_ENABLED=true
MYSTIC_OAUTH_ISSUER=https://mystic.dexproject.workers.dev
MYSTIC_OAUTH_ALLOWED_REDIRECT_URIS=https://chatgpt.com/connector/oauth/...
MYSTIC_OAUTH_ACCESS_TOKEN_TTL_SECONDS=3600
MYSTIC_OAUTH_SIGNING_SECRET=YOUR_SIGNING_SECRET
MYSTIC_OAUTH_DEV_STATIC_TOKEN=YOUR_TEST_TOKEN
```

In this mode the Worker serves `/health` and `/mcp` directly. `MYSTIC_BACKEND_URL` is not required for the cloud-native LAB tools.

Optional provider configuration uses placeholders only. Do not commit real values:

```text
MYSTIC_PROVIDER_OPENAI_COMPAT_BASE_URL=https://YOUR_OPENAI_COMPAT_HOST
MYSTIC_PROVIDER_OPENAI_COMPAT_MODEL=gpt-4.1-mini
MYSTIC_PROVIDER_OPENAI_COMPAT_API_KEY=YOUR_OPENAI_COMPAT_API_KEY
MYSTIC_PROVIDER_GEMINI_MODEL=gemini-2.5-flash
MYSTIC_PROVIDER_GEMINI_API_KEY=YOUR_GEMINI_API_KEY
MYSTIC_PROVIDER_GOOGLE_VERTEX_OAUTH_ENABLED=true
MYSTIC_PROVIDER_GOOGLE_VERTEX_CLIENT_ID=YOUR_GOOGLE_VERTEX_CLIENT_ID
MYSTIC_PROVIDER_GOOGLE_VERTEX_CLIENT_SECRET=YOUR_GOOGLE_VERTEX_CLIENT_SECRET
MYSTIC_PROVIDER_GOOGLE_VERTEX_PROJECT_ID=YOUR_GOOGLE_VERTEX_PROJECT_ID
MYSTIC_PROVIDER_GOOGLE_VERTEX_LOCATION=YOUR_GOOGLE_VERTEX_LOCATION
MYSTIC_PROVIDER_GOOGLE_VERTEX_MODEL=gemini-2.5-flash
MYSTIC_PROVIDER_TOKEN_ENCRYPTION_KEY=YOUR_PROVIDER_TOKEN_ENCRYPTION_KEY
MYSTIC_PROVIDER_ANTHROPIC_MODEL=claude-3-5-sonnet-latest
MYSTIC_PROVIDER_ANTHROPIC_API_KEY=YOUR_ANTHROPIC_API_KEY
```

If these provider secrets are absent, the Worker still exposes the tool and returns a structured response with:

- `provider_required=true` for missing external model providers
- `status=deferred` for heavy cloud paths that are intentionally exposed but not yet executed in-worker

Current Provider Connect boundary:

- `gemini` does not use OAuth in Mystic LAB and stays API-key based
- `google_vertex_ai` can generate a real Google OAuth authorization URL when metadata is configured
- `google_vertex_ai` now also returns a short `user_action` login link plus top-level `flow_id` from `provider_connect_start`, while still exposing `authorization_url` for tooling/debugging
- `google_vertex_ai` now completes OAuth callback handling only when `MYSTIC_PROVIDER_TOKEN_ENCRYPTION_KEY` is configured
- OAuth access, refresh, and ID tokens are stored only as encrypted server-side records
- `google_vertex_ai` provider status now exposes only safe token-exchange diagnostics such as error code, HTTP status, sanitized description, config booleans, and the exact queryless redirect URI
- `google_vertex_ai` model-call routing is still deferred after connection, so connected token storage does not yet enable real Vertex inference in this issue

### Deploy and verify

Deploy [cloudflare/mystic_public_gateway_worker.js](/Users/JYH/Documents/Mystic/cloudflare/mystic_public_gateway_worker.js) with the Supabase and OAuth variables above, then verify:

```bash
curl -i https://mystic.dexproject.workers.dev/health

python scripts/run_remote_mcp_lab_smoke.py \
  --endpoint https://mystic.dexproject.workers.dev/mcp \
  --auth-mode bearer \
  --bearer-token "$MYSTIC_TEST_BEARER_TOKEN"

python scripts/check_chatgpt_remote_mcp_readiness.py \
  --public-endpoint https://mystic.dexproject.workers.dev \
  --expect-oauth \
  --bearer-token "$MYSTIC_TEST_BEARER_TOKEN"
```

Expected current cloud-native LAB outcome:

- `/health` returns `{"status":"ok"}`
- `tools/list` includes the full LAB cloud-native tool surface
- `lab_session_create` writes to Supabase
- `lab_session_advance` advances the session or returns a structured blocked/provider-required turn instead of crashing
- `lab_memory_write` and `lab_memory_search` round-trip claims and memory objects through Supabase
- `lab_session_get` reads from Supabase
- `lab_report_generate` returns markdown and stores the current report in Supabase
- model-dependent LAB tools return `provider_required` or `deferred` when explicit provider connectivity is unavailable

## Phase 1 Status

Implemented for [Issue #75](https://github.com/Dezire0/Mystic/issues/75) `Mystic LAB OS Phase 1: Math + Simple Physics + 3D Scene API`:

- scene lifecycle MCP tools
- `physics.simple_projectile`
- `physics.simple_collision`
- `scene.three_json`
- scene-linked snapshot/report/archive storage in local JSON mode and Supabase mode

Implemented with limits:

- `math.sympy` executes through a deterministic subset for arithmetic evaluation, numeric substitution, simple simplification, and one-variable linear solve
- unsupported symbolic forms return structured `unsupported_expression` or `engine_required` instead of attempting arbitrary execution

### Roll back to local mode

To return to the existing local Python backend path:

- set `MYSTIC_STORAGE_BACKEND=local` or remove it
- keep the FastAPI backend running on `127.0.0.1:8765`
- set `MYSTIC_BACKEND_URL` in the Worker to the local tunnel or stable backend origin you want to proxy
- redeploy the Worker

This restores the pre-cloud-native behavior, including the richer local LAB execution paths and local provider integrations.

`/mcp` is a JSON-RPC endpoint. Plain browser `GET` requests are not the protocol and may be rejected. Verify the public ingress with MCP `POST` requests instead:

```bash
python scripts/test_mystic_mcp_client.py --base-url http://127.0.0.1:8765 --scenario ping
python scripts/test_mystic_mcp_client.py --base-url http://127.0.0.1:8765 --scenario public-tool-suite
```

The full local/public proxy MCP layer exposes:

- `mystic_status`
- `health_check`
- `mystic_verify_answer`
- `mystic_call_model`
- `mystic_compare_models`
- `mystic_run_research_table`

For the Mystic LAB MCP flow, use protocol-level smoke checks instead of browser `GET` requests:

```bash
python scripts/run_remote_mcp_lab_smoke.py \
  --endpoint http://127.0.0.1:8765/mcp

python scripts/run_remote_mcp_lab_smoke.py \
  --endpoint https://mystic.dexproject.workers.dev/mcp \
  --public-endpoint https://mystic.dexproject.workers.dev
```

This verifies external MCP client behavior end to end:

- `initialize`
- `tools/list`
- `lab_session_create`
- `lab_session_get`
- `lab_report_generate`
- optional `lab_session_advance` when the richer local backend is available
- persisted lab session artifacts under local files or `supabase://...` paths depending on the storage backend

The smoke summary is written to:

- `mystic_data/e2e/remote_mcp_lab_smoke/summary.json`

### Stable Backend for Public MCP

The public Worker depends on `MYSTIC_BACKEND_URL`. If that backend origin is a Cloudflare quick tunnel, public MCP can break even when:

- `/.well-known/oauth-protected-resource` is healthy
- `/oauth/authorize` and `/oauth/token` are healthy
- ChatGPT still discovers the public tools

Recommended path:

- use a Cloudflare named tunnel or another stable backend origin
- point `MYSTIC_BACKEND_URL` at that stable origin
- rerun public MCP health checks after every backend-origin change

Current repo-backed serving model:

- local Mystic backend: `uvicorn mystic.app.main:app --host 127.0.0.1 --port 8765`
- local backend health: `http://127.0.0.1:8765/health`
- local MCP endpoint: `http://127.0.0.1:8765/mcp`
- quick tunnel helper: `scripts/run_mystic_public_tunnel.py`
- launchd helper for the quick tunnel: `scripts/manage_mystic_public_tunnel_service.py`
- Worker origin lookup: `cloudflare/mystic_public_gateway_worker.js`

To check whether the public Worker is healthy and whether the backend origin is likely dead, run:

```bash
python scripts/check_public_backend_origin.py \
  --public-endpoint https://mystic.dexproject.workers.dev
```

Optionally include the direct backend origin and a bearer token:

```bash
python scripts/check_public_backend_origin.py \
  --public-endpoint https://mystic.dexproject.workers.dev \
  --backend-url https://mystic-backend.example.com \
  --expect-oauth \
  --bearer-token "$MYSTIC_TEST_BEARER_TOKEN"
```

The summary is written to:

- `mystic_data/e2e/backend_origin_health/summary.json`

Required post-change checks:

```bash
curl -i https://mystic.dexproject.workers.dev/health

python scripts/run_remote_mcp_lab_smoke.py \
  --endpoint https://mystic.dexproject.workers.dev/mcp \
  --auth-mode bearer \
  --bearer-token "$MYSTIC_TEST_BEARER_TOKEN"

python scripts/run_remote_mcp_lab_smoke.py \
  --endpoint https://mystic.dexproject.workers.dev/mcp \
  --auth-mode expect-auth-required \
  --allow-auth-required
```

For a placeholder-only named tunnel template, see:

- `docs/cloudflare_named_tunnel_template.md`

To check whether the current public endpoint is import-ready for ChatGPT as a remote MCP server:

```bash
python scripts/check_chatgpt_remote_mcp_readiness.py \
  --public-endpoint https://mystic.dexproject.workers.dev
```

This writes:

- `mystic_data/e2e/remote_mcp_lab_smoke/chatgpt_remote_mcp_readiness.json`

If OAuth metadata is not implemented yet, the readiness report intentionally returns:

- `import_ready=false`
- blocker `OAUTH_NOT_CONFIGURED`

### Remote MCP OAuth

Mystic LAB can expose a public MCP-powered research lab without OAuth, but ChatGPT remote MCP import readiness requires OAuth metadata and bearer-token validation.

- `READY_PUBLIC_MCP_LAB` means external MCP clients can reach the public `/mcp` endpoint and run lab tools.
- `import_ready_candidate=true` means the public endpoint appears to have the minimum OAuth metadata and authenticated MCP behavior needed for a manual ChatGPT Developer Mode import attempt.
- `import_ready=true` must only be set after a real manual import verification artifact exists and validates.

Check current readiness:

```bash
python scripts/check_chatgpt_remote_mcp_readiness.py \
  --public-endpoint https://mystic.dexproject.workers.dev
```

Run public MCP smoke without auth:

```bash
python scripts/run_remote_mcp_lab_smoke.py \
  --endpoint https://mystic.dexproject.workers.dev/mcp
```

Run public MCP smoke with a bearer token:

```bash
python scripts/run_remote_mcp_lab_smoke.py \
  --endpoint https://mystic.dexproject.workers.dev/mcp \
  --auth-mode bearer \
  --bearer-token "$MYSTIC_TEST_BEARER_TOKEN"
```

Check OAuth candidate readiness:

```bash
python scripts/check_chatgpt_remote_mcp_readiness.py \
  --public-endpoint https://mystic.dexproject.workers.dev \
  --bearer-token "$MYSTIC_TEST_BEARER_TOKEN" \
  --expect-oauth
```

Inspect the redacted public `tools/list` shape:

```bash
python scripts/debug_mcp_tools_list_shape.py \
  --endpoint https://mystic.dexproject.workers.dev/mcp \
  --bearer-token "$MYSTIC_TEST_BEARER_TOKEN"
```

Check ChatGPT action discovery compatibility:

```bash
python scripts/check_chatgpt_action_discovery_compatibility.py \
  --endpoint https://mystic.dexproject.workers.dev/mcp \
  --bearer-token "$MYSTIC_TEST_BEARER_TOKEN"
```

This writes runtime-only summaries under:

- `mystic_data/e2e/chatgpt_action_discovery/tools_list_shape.json`
- `mystic_data/e2e/chatgpt_action_discovery/summary.json`

Cloudflare Worker environment variables use placeholders only. Do not commit real values:

```bash
MYSTIC_OAUTH_ENABLED=true
MYSTIC_OAUTH_ISSUER=https://mystic.dexproject.workers.dev
MYSTIC_OAUTH_ALLOWED_REDIRECT_URIS=https://example.com/callback,http://localhost:3000/callback
MYSTIC_OAUTH_ACCESS_TOKEN_TTL_SECONDS=3600
MYSTIC_OAUTH_SIGNING_SECRET=replace-me
MYSTIC_OAUTH_DEV_STATIC_TOKEN=replace-me-dev-only
MYSTIC_BACKEND_URL=https://current-origin.example.com
```

Notes:

- OAuth-disabled mode preserves unauthenticated local MCP smoke for development.
- The dev static bearer token is development-only and is not production-ready.
- This OAuth layer does not prove ChatGPT import success by itself. A real Developer Mode import must still be performed manually.

### Manual ChatGPT Developer Mode Import Verification

- `import_ready_candidate=true` means Mystic is technically ready for a real manual ChatGPT Developer Mode import attempt.
- `import_ready=true` requires both the OAuth/MCP candidate checks and a validated runtime manual verification artifact.
- The artifact must not contain secrets, tokens, passwords, or signing material.

Run the candidate readiness check:

```bash
python scripts/check_chatgpt_remote_mcp_readiness.py \
  --public-endpoint https://mystic.dexproject.workers.dev \
  --expect-oauth \
  --bearer-token "$MYSTIC_TEST_BEARER_TOKEN"
```

In ChatGPT Developer Mode, add the remote MCP server:

```text
https://mystic.dexproject.workers.dev
```

Then:

1. Complete the OAuth flow.
2. Confirm these tools are visible:
   `health_check`, `lab_session_create`, `lab_session_get`, `lab_report_generate`
3. Manually call those tools from ChatGPT if possible.
4. Create the runtime verification artifact:

```bash
python scripts/create_chatgpt_import_verification_artifact.py \
  --root-path /Users/JYH/Documents/Mystic \
  --public-endpoint https://mystic.dexproject.workers.dev \
  --confirm-imported \
  --confirm-oauth-flow \
  --confirm-tools-visible \
  --confirm-tool-calls-passed
```

This writes a runtime-only artifact under:

- `mystic_data/e2e/chatgpt_remote_mcp_import/verification.json`

For the Cloudflare Worker runtime, the same sanitized artifact can be mirrored through `MYSTIC_CHATGPT_IMPORT_VERIFICATION_JSON` so `mystic_status` can report the verified `import_ready` state without reading from the local filesystem.

An example committed template lives at:

- `docs/examples/chatgpt_remote_mcp_import_verification.example.json`

Re-run readiness:

```bash
python scripts/check_chatgpt_remote_mcp_readiness.py \
  --public-endpoint https://mystic.dexproject.workers.dev \
  --expect-oauth \
  --bearer-token "$MYSTIC_TEST_BEARER_TOKEN"
```

Expected after a valid manual artifact:

- `import_ready_candidate=true`
- `manual_import_verified=true`
- `import_ready=true`

## Discord Bot

Install the Discord bot dependency:

```bash
/opt/homebrew/Caskroom/miniforge/base/bin/python -m venv .venv-discord
.venv-discord/bin/python -m pip install -r requirements-discord.txt
```

Set environment variables:

```bash
export MYSTIC_DISCORD_TOKEN="your-bot-token"
export MYSTIC_DISCORD_GUILD_ID="optional-guild-id-for-fast-sync"
```

Or put them in `.env` at the project root. `scripts/run_discord_bot.py` now auto-loads `.env` before startup.

Run the bot:

```bash
.venv-discord/bin/python scripts/run_discord_bot.py --base-dir mystic_data
```

Use `/mystic` in Discord. The bot opens a DM and sends:

- 1-3 overview pages with all experts, progress percent, and running/waiting/failure status
- an expert detail page with progress bar, dataset, ETA, and latest failure log
- `/mystic_lab` runs the local research lab for a natural-language math question
- you can also send a plain DM to the bot, or mention the bot in a guild message, and it will answer without a slash command
- DM/mention research replies now send granular worklog-style progress updates as separate short messages before the final answer
- the research lab now uses light router selection, a separate Core planning stage, then selected-specialist method proposals, task redistribution, debate objections, revision, and Core synthesis instead of trusting a single specialist alone
- the research lab also includes CorePlan, Completeness, Counterexample, and Cost/Latency critics, plus an optional remote heavy-reasoning backend split when configured
- worklogs now show whether remote heavy reasoning is enabled and which backend/model each specialist actually used

`/mystic_lab` flow:

- question understanding
- router specialist selection
- Core initial planning
- CorePlan / Completeness / Counterexample / Cost-Latency critic
- selected-specialist method proposal
- Core task redistribution
- specialist task execution
- selected-specialist pairwise objection debate
- specialist revision
- Core synthesis
- conclusion drafting
- Raven critique to reduce unsupported claims

For plain-message replies, enable `MESSAGE CONTENT INTENT` in the Discord Developer Portal for the bot application. The runtime now enables `message_content` in code, but Discord must also allow it in the bot settings.

If the active Raven critic is configured as a local PEFT adapter but the Discord bot runtime does not have `torch`/`peft` installed, the research lab automatically falls back to the configured non-adapter Raven backend instead of failing the whole reply.

Run it persistently with launchd:

```bash
python scripts/manage_discord_bot_service.py install --base-dir mystic_data --guild-id "$MYSTIC_DISCORD_GUILD_ID"
python scripts/manage_discord_bot_service.py status --base-dir mystic_data
```

## Ollama Backend

Pull a local model:

```bash
ollama pull qwen2.5:7b
```

Run the loop with Ollama:

```bash
.venv-training/bin/python scripts/mystic_loop.py --limit 10 --backend ollama
```

Override models explicitly when needed:

```bash
.venv-training/bin/python scripts/mystic_loop.py --limit 20 --backend ollama --generator-model qwen2.5:7b --raven-model qwen2.5:7b
```

## OpenAI-Compatible Backend

Set environment variables:

```bash
export MYSTIC_API_BASE="http://localhost:8000/v1"
export MYSTIC_API_KEY="replace-me-or-leave-blank-for-local-servers"
export MYSTIC_GENERATOR_MODEL="Qwen/Qwen2.5-7B-Instruct"
export MYSTIC_RAVEN_MODEL="Qwen/Qwen2.5-7B-Instruct"
```

Run the loop:

```bash
.venv-training/bin/python scripts/mystic_loop.py --limit 10 --backend openai-compatible
```

`MYSTIC_API_KEY` is not hardcoded. If your local OpenAI-compatible server does not require auth, leave it blank.

## Export Raven LoRA Data

```bash
python scripts/export_raven_lora.py
```

This writes both:

- `mystic_data/exports/raven_lora.jsonl`
- `mystic_data/train_ready/raven_lora.jsonl`

## Execution History Page

Build a single HTML page from the current execution logs:

```bash
.venv-training/bin/python scripts/render_execution_history_page.py
```

Outputs:

- `mystic_data/reports/execution_history.html`
- `mystic_data/reports/execution_history.json`

## Mystic v2 Training

Check the adapter's recorded base model:

```bash
.venv-training/bin/python - <<'PY'
import json
from pathlib import Path
p = Path("mystic_data/adapters/raven_lora_tiny_gpt2_smoke/adapter_config.json")
cfg = json.loads(p.read_text())
print(cfg.get("base_model_name_or_path"))
PY
```

Smoke-test adapter commands:

```bash
.venv-training/bin/python scripts/evaluate_raven_lora.py \
  --base-model sshleifer/tiny-gpt2 \
  --adapter-path mystic_data/adapters/raven_lora_tiny_gpt2_smoke \
  --eval-file mystic_data/eval_holdout/raven_eval.jsonl \
  --limit 20
```

The smoke adapter is only for pipeline validation. The real Raven adapter target remains `mystic_data/adapters/raven_lora_v0`.

Prepare train and eval files:

```bash
.venv-training/bin/python scripts/export_raven_lora.py
.venv-training/bin/python scripts/prepare_raven_training_data.py --limit 500
```

Mac dry-run for data and tokenization only:

```bash
.venv-training/bin/python scripts/train_raven_lora.py \
  --dry-run \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --train-file mystic_data/train_ready/raven_train.jsonl \
  --eval-file mystic_data/eval_holdout/raven_eval.jsonl \
  --output-dir mystic_data/adapters/raven_lora_v0
```

GPU QLoRA training:

```bash
python scripts/train_raven_lora.py \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --train-file mystic_data/train_ready/raven_train.jsonl \
  --eval-file mystic_data/eval_holdout/raven_eval.jsonl \
  --output-dir mystic_data/adapters/raven_lora_v0 \
  --epochs 1 \
  --batch-size 1 \
  --learning-rate 0.0002 \
  --max-length 2048 \
  --qlora
```

Evaluate the adapter:

```bash
.venv-training/bin/python scripts/evaluate_raven_lora.py \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --adapter-path mystic_data/adapters/raven_lora_v0 \
  --eval-file mystic_data/eval_holdout/raven_eval.jsonl \
  --limit 100
```

Register the adapter:

```bash
python scripts/register_model.py \
  --model-id raven_lora_v0 \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --adapter-path mystic_data/adapters/raven_lora_v0
```

## GPU Environments

Real QLoRA should run on a Linux NVIDIA GPU environment. Typical options:

```bash
python scripts/train_raven_lora.py \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --train-file mystic_data/train_ready/raven_train.jsonl \
  --eval-file mystic_data/eval_holdout/raven_eval.jsonl \
  --output-dir mystic_data/adapters/raven_lora_v0 \
  --epochs 1 \
  --batch-size 1 \
  --learning-rate 0.0002 \
  --max-length 2048 \
  --qlora
```

## Cycle Runner

The local cycle can now be run in two stages: `prepare` before GPU training and `finish` after you download the trained adapter tarball.

Prepare a cycle and build the GPU upload package:

```bash
.venv-training/bin/python scripts/run_mystic_cycle.py prepare \
  --cycle-id cycle_1 \
  --run-prepare-data \
  --train-limit 1000 \
  --eval-limit 100 \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --adapter-path mystic_data/adapters/raven_lora_v1 \
  --learning-rate 0.00015
```

This writes a tarball like `mystic_gpu_train_package_cycle_1.tar.gz` at the repo root and stores cycle artifacts under `mystic_data/cycles/cycle_1/`.

Mac dry-run before real GPU training:

```bash
.venv-training/bin/python scripts/train_raven_lora.py \
  --dry-run \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --train-file mystic_data/train_ready/raven_train.jsonl \
  --eval-file mystic_data/eval_holdout/raven_eval.jsonl \
  --output-dir mystic_data/adapters/raven_lora_v0
```

GPU QLoRA training:

```bash
python scripts/train_raven_lora.py \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --train-file mystic_data/train_ready/raven_train.jsonl \
  --eval-file mystic_data/eval_holdout/raven_eval.jsonl \
  --output-dir mystic_data/adapters/raven_lora_v1 \
  --epochs 1 \
  --batch-size 1 \
  --learning-rate 0.00015 \
  --max-length 2048 \
  --qlora
```

Finish a cycle after downloading the adapter tarball:

```bash
.venv-training/bin/python scripts/run_mystic_cycle.py finish \
  --cycle-id cycle_1 \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --adapter-tar ~/Downloads/raven_lora_v1_qwen.tar.gz \
  --adapter-path mystic_data/adapters/raven_lora_v1 \
  --model-id raven_lora_v1_qwen_0_5b \
  --run-limit 20 \
  --compare-limit 10
```

What `finish` does automatically:

- checks that `adapter_config.json` exists
- checks that `adapter_model.safetensors` exists
- checks that `base_model_name_or_path` matches `--base-model`
- backs up and clears `mystic_data/state/processed_ids.jsonl`
- runs adapter reinjection through `scripts/mystic_loop.py`
- runs `scripts/compare_raven_models.py`
- verifies `adapter_better_or_equal_rate` exists in the comparison summary
- runs `scripts/register_model.py`
- appends cycle events and summaries without overwriting older JSONL logs

Evaluate the adapter explicitly:

```bash
.venv-training/bin/python scripts/evaluate_raven_lora.py \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --adapter-path mystic_data/adapters/raven_lora_v1 \
  --eval-file mystic_data/eval_holdout/raven_eval.jsonl \
  --limit 10
```

Reinject the adapter into the live loop directly:

```bash
.venv-training/bin/python scripts/mystic_loop.py \
  --limit 10 \
  --backend adapter \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --adapter-path mystic_data/adapters/raven_lora_v1 \
  --run-id qwen_raven_reinject_v1
```

Show current local cycle state:

```bash
.venv-training/bin/python scripts/run_mystic_cycle.py status \
  --limit 5
```

## Raven vNext from Research Table Data

Raven vNext combines verifier examples exported from Research Table sessions with deterministic adversarial referee cases. The default local path does not require API keys; Gemini CLI and Claude CLI participants are optional.

Run Research Table sessions, then export their Raven rows:

```bash
python scripts/export_research_table_datasets.py \
  --root-path /Users/JYH/Documents/Mystic
```

Generate the curated adversarial seed dataset:

```bash
python scripts/generate_raven_adversarial_seeds.py \
  --root-path /Users/JYH/Documents/Mystic \
  --allow-overwrite
```

Prepare the combined Raven chat-format dataset:

```bash
python scripts/prepare_research_table_training.py \
  --root-path /Users/JYH/Documents/Mystic \
  --target raven \
  --include-adversarial-seeds
```

Package the same combined train/eval data for the existing cycle:

```bash
python scripts/run_mystic_cycle.py prepare \
  --cycle-id raven_vnext \
  --dataset-source research_table \
  --target raven \
  --include-adversarial-seeds
```

Check the resulting dataset, manifest, split files, and package contents:

```bash
python scripts/check_raven_training_readiness.py \
  --root-path /Users/JYH/Documents/Mystic
```

The prepare command creates a Kaggle package and manual command file, but it does not submit or run Kaggle. Upload and run that package manually. After downloading the trained adapter tarball, reinject it and run the fixed before/after evaluation:

```bash
python scripts/run_raven_vnext_eval.py \
  --root-path /Users/JYH/Documents/Mystic \
  --adapter-tar /path/to/raven_lora_vnext.tar.gz
```

Generated datasets, training reports, E2E output, metrics, and Kaggle packages under `mystic_data/` are ignored by git. A low `INVALID` row warning means Raven may over-accept weak or false proofs; regenerate the adversarial seeds and prepare with `--include-adversarial-seeds`.

## Watching Raven vNext Training

After submit, watch the already-submitted Raven vNext cycle without creating a new Kaggle job:

```bash
python scripts/watch_raven_vnext_training.py \
  --root-path /Users/JYH/Documents/Mystic \
  --cycle-id raven_vnext_adversarial \
  --expected-tar-name raven_lora_vnext_adversarial.tar.gz
```

One-shot mode polls once and exits `0` when training is still running:

```bash
python scripts/watch_raven_vnext_training.py \
  --root-path /Users/JYH/Documents/Mystic \
  --cycle-id raven_vnext_adversarial \
  --expected-tar-name raven_lora_vnext_adversarial.tar.gz \
  --once
```

If the adapter tar was downloaded manually, skip download and run eval only:

```bash
python scripts/watch_raven_vnext_training.py \
  --root-path /Users/JYH/Documents/Mystic \
  --cycle-id raven_vnext_adversarial \
  --expected-tar-name raven_lora_vnext_adversarial.tar.gz \
  --adapter-tar /path/to/raven_lora_vnext_adversarial.tar.gz \
  --eval-only
```

This watcher does not submit a new Kaggle job. It only watches, downloads, and evaluates the already-submitted cycle. It never runs Kaggle training automatically from scratch, does not require API keys, and stores runtime artifacts under `mystic_data/`.

If Kaggle fails with package tar not found:

- inspect `mystic_data/cycles/raven_vnext_adversarial/kaggle_poll_summary.json`
- inspect the generated `kaggle_kernel/train_mystic_raven.py`
- ensure the submit summary records the exact `package_filename`
- ensure the generated kernel searches `/kaggle/input` recursively to a safe depth instead of relying on one hardcoded mount path
- after fixing the discovery logic, intentionally rerun `submit`

If submit fails because Kaggle GPU quota is exhausted:

- no new training run started
- do not run the watcher expecting adapter output from a new run
- wait for the weekly Kaggle GPU quota reset or use an environment with available GPU quota
- rerun the same submit command with the existing prepared package
- do not regenerate the package unless the dataset contents changed

Retry the existing prepared package with:

```bash
python /Users/JYH/Documents/Mystic/scripts/run_mystic_cycle.py submit \
  --cycle-id raven_vnext_adversarial \
  --base-dir /Users/JYH/Documents/Mystic/mystic_data \
  --package-path /Users/JYH/Documents/Mystic/mystic_gpu_train_package_raven_vnext_adversarial.tar.gz \
  --kaggle-username dyrakd \
  --adapter-path mystic_data/adapters/raven_lora_vnext_adversarial \
  --output-tar-name raven_lora_vnext_adversarial.tar.gz
```

Then check status without creating a new run:

```bash
python /Users/JYH/Documents/Mystic/scripts/watch_raven_vnext_training.py \
  --root-path /Users/JYH/Documents/Mystic \
  --cycle-id raven_vnext_adversarial \
  --expected-tar-name raven_lora_vnext_adversarial.tar.gz \
  --once
```

## Kaggle Automation

For free GPU automation, Mystic now supports a Kaggle CLI flow inside [scripts/run_mystic_cycle.py](/Users/JYH/Documents/Mystic/scripts/run_mystic_cycle.py).

Before starting a new Raven training run from Research Table data, check whether the local dataset, manifest, split files, and Kaggle package inputs are ready:

```bash
python scripts/check_raven_training_readiness.py --root-path /Users/JYH/Documents/Mystic
```

Install the Kaggle CLI and place credentials at `~/.kaggle/kaggle.json` or set `KAGGLE_USERNAME` and `KAGGLE_KEY`:

```bash
python -m pip install kaggle
chmod 600 ~/.kaggle/kaggle.json
```

Prepare the package and train/eval data:

```bash
python scripts/run_mystic_cycle.py prepare \
  --cycle-id cycle_1 \
  --run-prepare-data \
  --train-limit 1000 \
  --eval-limit 100 \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --adapter-path mystic_data/adapters/raven_lora_v1 \
  --learning-rate 0.00015
```

Submit the prepared package to Kaggle:

```bash
python scripts/run_mystic_cycle.py submit \
  --cycle-id cycle_1 \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --adapter-path mystic_data/adapters/raven_lora_v1 \
  --learning-rate 0.00015
```

Poll the Kaggle kernel until it finishes:

```bash
python scripts/run_mystic_cycle.py poll \
  --cycle-id cycle_1 \
  --poll-seconds 60 \
  --timeout-minutes 240
```

Download the trained adapter artifact:

```bash
python scripts/run_mystic_cycle.py download --cycle-id cycle_1
```

Run the full Kaggle-backed cycle automatically:

```bash
python scripts/run_mystic_cycle.py full \
  --cycle-id cycle_1 \
  --run-prepare-data \
  --train-limit 1000 \
  --eval-limit 100 \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --adapter-path mystic_data/adapters/raven_lora_v1 \
  --model-id raven_lora_v1_qwen_0_5b \
  --learning-rate 0.00015 \
  --run-limit 20 \
  --compare-limit 10
```

The cycle directory stores:

- `prepare_summary.json`
- `kaggle_commands.md`
- `kaggle_submit_summary.json`
- `kaggle_poll_summary.json`
- `kaggle_download_summary.json`
- `summary.json`

Use the same command on:

- Colab with a CUDA runtime
- Kaggle notebooks with an NVIDIA GPU
- RunPod or another Linux GPU host

On macOS, `--qlora` will fail gracefully when `bitsandbytes` or CUDA is unavailable. Dry-run mode is intended for local inspection.

## Manifest Workflow

The repository also includes a checklist-derived workflow runner that follows the existing manifests instead of requiring manual step selection.

Run the full local preparation workflow:

```bash
.venv-training/bin/python scripts/run_manifest_workflow.py run \
  --workflow-id manifest_cycle_1 \
  --seed-internal \
  --max-hf-rows 3 \
  --numina-limit 1100 \
  --raven-prepare-limit 500 \
  --train-limit 1000 \
  --eval-limit 100 \
  --run-cycle-prepare \
  --cycle-id cycle_1 \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --adapter-path mystic_data/adapters/raven_lora_v1 \
  --learning-rate 0.00015
```

What this workflow does:

- initializes local internal Mystic data files
- optionally seeds internal example records
- resolves checklist-linked Hugging Face datasets
- downloads public dataset samples into `mystic_data/raw/`
- grows the local Numina cache
- exports Raven critique data
- prepares Raven train/eval JSONL files
- prepares specialist train-ready JSONL files
- generates training plans for every target in `mystic_data/metadata/manifests/training_manifest.json`
- optionally prepares the Kaggle Raven cycle package

Show the latest workflow summary:

```bash
.venv-training/bin/python scripts/run_manifest_workflow.py status --limit 5
```

The workflow writes its summary to:

- `mystic_data/workflows/<workflow_id>/summary.json`

## Mystic LAB Raven Reinjection

Run the loop with the trained Raven adapter:

```bash
.venv-training/bin/python scripts/mystic_loop.py \
  --limit 10 \
  --backend adapter \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --adapter-path mystic_data/adapters/raven_lora_v0
```

Compare base Raven vs adapter Raven:

```bash
python scripts/compare_raven_models.py \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --adapter-path mystic_data/adapters/raven_lora_v0 \
  --eval-file mystic_data/eval_holdout/raven_eval.jsonl \
  --limit 100
```

Promote the adapter:

```bash
python scripts/promote_raven_adapter.py \
  --model-id raven_lora_v0 \
  --comparison-log mystic_data/logs/raven_comparison_results.jsonl
```

If `raven_lora_v0` is not already present in `mystic_data/metadata/model_versions.json`, run the v2 registration step first.

Generate new data using the promoted Raven adapter:

```bash
python scripts/mystic_loop.py \
  --limit 50 \
  --backend adapter \
  --adapter-path mystic_data/adapters/raven_lora_v0 \
  --run-id raven_reinjection_v0
```

If you want side-by-side loop-time comparison on the same proof attempt:

```bash
python scripts/mystic_loop.py \
  --limit 10 \
  --backend adapter \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --adapter-path mystic_data/adapters/raven_lora_v0 \
  --compare-raven
```

## Self-Improvement Loop

The trained Raven adapter now sits directly inside the live research loop:

- the generator still produces proof attempts using the existing HTTP backend
- Raven can now critique with `base model + PEFT adapter`
- comparison logs measure whether the adapter is improving critique quality against the base Raven model
- promotion marks the adapter active in the model registry
- new adapter-generated critiques are still stored in `mystic_data/internal/raven_critiques.jsonl`
- those critiques can be exported again into `mystic_data/train_ready/` for the next training round

## Resume Behavior

Run the loop again with the same input to skip IDs already recorded in `mystic_data/state/processed_ids.jsonl`:

```bash
python scripts/mystic_loop.py --limit 10 --backend ollama
```

## Power Behavior

Persistent local training and remote cycle services can be installed with the launchd helpers:

```bash
python scripts/manage_continuous_training.py install
python scripts/manage_remote_cycle_service.py install
```

By default these services run under `/usr/bin/caffeinate -i -s` so macOS idle/system sleep does not pause training while the machine stays powered on.

- This helps with screen-off / idle sleep.
- `RunAtLoad` and `KeepAlive` make the services restart after login or reboot.
- A completely powered-off Mac cannot keep running local training jobs; it can only resume after boot.
- If you explicitly want sleep to be allowed, install with `--allow-system-sleep`.

## Troubleshooting

- If `ollama` requests fail, confirm the daemon is running and `http://localhost:11434` is reachable.
- If the OpenAI-compatible backend fails immediately, verify `MYSTIC_API_BASE` is set correctly and includes the right host or `/v1` prefix.
- If Raven returns malformed JSON, the loop will classify that item as `NEEDS_MORE_DETAIL` and keep the raw output in JSONL instead of crashing.
- If `train_raven_lora.py --qlora` fails on macOS, that is expected on non-CUDA setups. Use dry-run locally and move real QLoRA to Linux GPU.
- If `mystic_loop.py --backend adapter` fails, confirm `mystic_data/adapters/raven_lora_v0` exists and contains a valid PEFT adapter.
- If adapter loading stops with an adapter/base-model mismatch error, read `adapter_config.json` and use the exact `base_model_name_or_path` it declares.
- If adapter inference is slow on macOS, that is expected on MPS or CPU. The loop will warn and continue.
- If your local Python is not the project training environment, replace `python` with `.venv-training/bin/python`.

## Verify

```bash
python -m unittest discover -s tests
```

Optional dependency behavior:

- tests that exercise the Discord bot runtime skip when `discord.py` is not installed
- tests that exercise the real Transformers-backed Raven training runtime skip when `transformers` is not installed
- core JSONL, Research Table, MCP, router, and cycle tests still run normally without those optional packages

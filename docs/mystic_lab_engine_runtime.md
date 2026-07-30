# Mystic LAB trusted engine runtime

Phase 2A executes only the built-in, allowlisted scientific engines. The public
Worker never accepts source code, modules, shell commands, or arbitrary imports.

## Public API

Normal Mystic OAuth authentication is required for these JSON endpoints:

- `GET /lab/engines`, `GET /lab/engines/:engineId`, `POST /lab/engines/match`
- `POST /lab/engine-jobs`, `GET /lab/engine-jobs`, `GET /lab/engine-jobs/:jobId`
- `POST /lab/engine-jobs/:jobId/wait`, `POST /lab/engine-jobs/:jobId/cancel`
- `GET /lab/engine-runs`, `GET /lab/engine-runs/:runId`, and `/series`
- `POST /lab/engine-runs/:runId/attach`, `GET /lab/engine-runs/:runId/artifacts`

Result attachments only use run references. A scene attachment requires the
current `expected_scene_revision`; stale revisions return a safe `409`
`scene_revision_conflict`. Repeating a successful attachment is idempotent.

## Runner operation and Phase 2B.1 fleet

The runner key remains only in macOS Keychain under service
`mystic-engine-runner-token` and account `mystic-engine-runner`. Install the
user-scoped persistent service with:

```bash
uv run python scripts/install_mystic_engine_runner_launchd.py --install --repo-root /persistent/path/to/Mystic
```

The installer rejects `/tmp` and `/private/tmp` checkouts. Validate the plist
with `plutil -lint ~/Library/LaunchAgents/com.mystic.engine-runner.plist` and
confirm its program and working-directory paths point to the persistent
checkout before bootstrapping the service. The runner refreshes its presence at
most every five seconds while idle, sends a 20-second heartbeat for active
jobs, and Worker presence expires after 90 seconds.

It starts `scripts/mystic_engine_runner.py --start`, registers its supported
engines, refreshes runner presence, claims jobs, and sends heartbeats while a
job is running. Remove it with `--uninstall`. Internal runner endpoints require
the separate runner bearer token and are not public API.

Issue #112 adds protocol version `2b.1`, safe capacity metadata, draining,
lease renewal, release, immutable attempt/audit records, and a deterministic
candidate order of priority, retry affinity, region preference, load, then
runner ID. `MYSTIC_RUNNER_FLEET_MODE` controls rollout: `legacy_single_runner`
retains the Phase 2A selector, `fleet_shadow` is the default and computes fleet
eligibility without replacing the legacy claim RPC, and `fleet_active` uses the
fleet RPCs only after its additive schema and per-runner credential verifiers
are present.

The legacy `MYSTIC_ENGINE_RUNNER_TOKEN` is a compatibility credential only for
non-active modes. In active mode every runner is bound to a non-revoked
SHA-256 verifier and the raw credential is never persisted or returned.
`MYSTIC_FLEET_ADMIN_TOKEN` is a separate Worker-only Control Center BFF
credential for fleet administration; it is never sent to the browser or
accepted for MCP or runner execution. Control Center `/runners` exposes only
safe runner data and requires an authenticated same-origin session and explicit
confirmation for drain, resume, maintenance, restore, and quarantine actions.

Run `uv run python scripts/check_engine_runtime.py` for local engine smoke
checks and `scripts/run_remote_mcp_lab_smoke.py` for authenticated public MCP
coverage.

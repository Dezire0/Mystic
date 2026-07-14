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

## Runner operation

The runner key remains only in macOS Keychain under service
`mystic-engine-runner-token` and account `mystic-engine-runner`. Install the
user-scoped persistent service with:

```bash
uv run python scripts/install_mystic_engine_runner_launchd.py --install
```

It starts `scripts/mystic_engine_runner.py --start`, registers its supported
engines, refreshes runner presence, claims jobs, and sends heartbeats while a
job is running. Remove it with `--uninstall`. Internal runner endpoints require
the separate runner bearer token and are not public API.

Run `uv run python scripts/check_engine_runtime.py` for local engine smoke
checks and `scripts/run_remote_mcp_lab_smoke.py` for authenticated public MCP
coverage.

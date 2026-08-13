# Trusted Scientific Job Worker Deployment Design

Phase 2C.2B defines deployment designs only. It does not deploy a worker, apply a migration, enable production workers, or grant production credentials.

## Preconditions

1. Apply and validate the Phase 2C.2A migration in the explicitly selected environment.
2. Use a separate worker identity and credential verifier; never reuse MCP OAuth, Control Center, engine-runner, provider, or Supabase service credentials.
3. Provision only the worker's required durable-job backend access and allowlisted engine runtime.
4. Run `--self-test`, then a non-production durable `--once` acceptance job before `--run`.
5. Confirm safe health, bounded metrics, and reconciliation before allowing persistent polling.

## macOS development / trusted workstation

Use a persistent checkout, a dedicated non-login service account where practical, protected credential loading, and `launchd` restart-on-transient-failure. Do not run from `/tmp`, expose credentials in plist arguments, or use a user shell profile as the credential source.

The service command should be the fixed `python -m mystic.lab.worker --run` entrypoint with an explicit persistent worker root. On shutdown, send a normal termination signal so the service drains: it stops accepting work, waits only its bounded graceful period, and leaves uncompleted leases for durable recovery.

## Linux service / container

Use a non-root container or service account with:

- read-only root filesystem and a bounded writable temporary/status area;
- CPU, memory, PID, and execution-time limits;
- no privileged mode, host mounts, or Docker socket;
- no arbitrary inbound listener;
- outbound network limited to required Mystic/Supabase service endpoints;
- dedicated secret injection for the worker credential and backend identity;
- restart-on-failure plus a health/status check;
- graceful drain on termination.

In-process built-in engines are trusted code, not a hardened tenant sandbox. Untrusted third-party engines remain out of scope. Any later subprocess adapter must use explicit argv, a minimal environment, bounded I/O, timeout, process-group kill, and finally cleanup before it can be enabled.

## Operational boundaries

The Control Center can inspect redacted worker health but cannot ask a browser to run, lease, complete, drain, or reconcile work. The public MCP surface is limited to operator job creation/inspection/cancellation/retry/statistics plus read-only worker health. Dedicated worker operations remain private server code and require current lease ownership.

For an incident: drain the worker, inspect durable job/outbox/attachment state, run authenticated reconciliation, and let the durable retry/dead-letter policy determine recovery. Never edit a job state, result, attachment, or lease token directly.

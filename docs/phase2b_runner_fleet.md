# Mystic LAB Phase 2B.1 runner fleet architecture

## Status and scope

This document is a planning contract for [Phase 2B epic #111](https://github.com/Dezire0/Mystic/issues/111) and [Phase 2B.1 #112](https://github.com/Dezire0/Mystic/issues/112). It is rooted at the immutable `phase-2a-production` tag, commit `05648b2a8f6fa6c314c531c796c95a0aeb4a3349`.

Phase 2B.1 replaces the single-host execution assumption with a trusted runner fleet. It preserves the existing macOS runner and adds one Linux CPU runner. It does not implement computer control, Home Assistant, OIDC, dynamic client registration, client-initiated metadata discovery, GPU execution, or Kubernetes.

## Target architecture

```text
ChatGPT Controller
        |
        v
Mystic MCP Worker
        |
        v
Engine Job Queue
        |
        v
Runner Scheduler
        |
        v
Runner Registry
  |- mystic-mac-runner
  |- mystic-linux-cpu-runner
  `- future GPU runners
```

The Worker remains the authority for job validation, state transitions, audit records, and public result retrieval. Runners only execute allowlisted engine jobs assigned through runner-only endpoints. The scheduler is a Worker-side deterministic decision, not a client-controlled selection field.

### Implemented rollout contract

Issue #112 uses `MYSTIC_RUNNER_FLEET_MODE` with three explicit values:

- `legacy_single_runner` keeps the Phase 2A queue selector.
- `fleet_shadow` is the default and computes fleet eligibility/ranking while leaving `mystic_claim_next_engine_job` authoritative.
- `fleet_active` calls the fleet claim, lease renewal, and recovery RPCs only after the additive schema and per-runner credential verifiers are present.

The existing macOS runner is accepted through its legacy credential during the shadow rollout. Active fleet mode binds every request's runner ID to a non-revoked SHA-256 credential verifier. The raw credential is created and installed out of band, never stored in Supabase, returned by the Worker, or rendered by Control Center. Lease TTL is currently 60 seconds, idle heartbeats are five seconds, active-job heartbeats are 20 seconds, presence freshness is 90 seconds, and active-mode jobs default to three attempts. Retry waits use bounded exponential backoff with a small bounded jitter; invalid input, output-validation failures, safety rejections, and scientific/model failures are non-retryable. Region is a soft deterministic preference only.

## Runner registry

### States

| State | Meaning | Eligible for new work |
| --- | --- | --- |
| `registering` | Registration is incomplete or being verified. | No |
| `online` | Fresh heartbeat and ready for compatible work. | Yes |
| `busy` | Has work but may retain free slots. | Yes, if capacity remains |
| `draining` | Finishes active work but accepts no new claims. | No |
| `maintenance` | Administrator-declared maintenance window. | No |
| `stale` | Heartbeat exceeded the configured freshness window. | No |
| `offline` | Released, explicitly unavailable, or stale beyond recovery. | No |
| `quarantined` | Removed from scheduling after a safety or reliability event. | No |

State changes must be auditable, validated against an allowed transition table, and never inferred from untrusted browser input. A fresh authenticated heartbeat may move `registering` to `online`; it must not clear `quarantined` or `maintenance` without an administrative action.

### Safe metadata

Each runner record needs the following safe metadata:

- `runner_id`, `runner_version`, `runtime_version`
- `operating_system`, `architecture`
- `supported_engines`, `resource_classes`
- `max_concurrent_jobs`, `active_jobs`, `cpu_count`, `memory_limit`
- `gpu_type` for future capability matching, `region`, `priority`
- `latest_heartbeat`, `failure_count`, `maintenance_state`

Public and Control Center responses must omit private host paths, usernames, tokens, internal IP addresses, process arguments, environment values, and raw platform inventory. CPU and memory values are capacity declarations, not a host fingerprinting API.

## Scheduler

### Candidate filtering

For a validated engine job, the scheduler filters runner candidates in this fixed order:

1. Runner state is `online` or `busy` and not draining, maintenance, stale, offline, or quarantined.
2. `latest_heartbeat` is within the configured freshness TTL.
3. The runner advertises the exact engine ID and a compatible engine/runtime version.
4. The requested resource class is advertised by the runner.
5. `active_jobs < max_concurrent_jobs`.
6. The runner is not excluded by a prior failed attempt for a non-retryable runner-specific reason.

No caller-provided runner ID can bypass these filters. A job with no candidate remains queued or becomes `retry_wait`; it never receives a fabricated result.

### Deterministic ranking

Eligible candidates are sorted by this tuple:

1. Configured priority, descending.
2. Retry affinity: the previous successful runner for the same deterministic input only when it remains eligible and no runner-specific failure caused retry.
3. Region preference: requested or policy-approved region match before non-match.
4. Current load: lowest `active_jobs / max_concurrent_jobs` ratio.
5. `runner_id`, lexicographically ascending.

The decision stores the normalized candidate set, ranking inputs, selected runner, scheduler version, and policy version in immutable job history. Given the same registry snapshot and job, selection is reproducible.

## Job leases, retry, and history

### Required fields

Jobs need `assigned_runner_id`, `lease_owner`, `lease_started_at`, `lease_expires_at`, `last_job_heartbeat`, `attempt_number`, `maximum_attempts`, `retry_after`, and `terminal_reason` in addition to their existing normalized input and hashes.

### States and transitions

| State | Description |
| --- | --- |
| `queued` | Validated, awaiting an eligible runner. |
| `claimed` | Atomically assigned with a short initial lease. |
| `running` | Runner acknowledged execution and renews the lease. |
| `cancellation_requested` | Cancellation is durable and awaits runner acknowledgement. |
| `completed` | One idempotent, hash-verified completion was accepted. |
| `failed` | Terminal failure with safe reason. |
| `cancelled` | Runner or scheduler acknowledged cancellation. |
| `lease_expired` | Lease elapsed without valid renewal; recovery evaluates retry. |
| `retry_wait` | Backoff before deterministic reassignment. |
| `dead_letter` | Retry limit reached or policy declares the error non-retryable. |

Claims use a single transactional compare-and-set operation. Lease renewal requires the active `lease_owner`, unexpired claim, and matching attempt number. Completion verifies the active lease, input hash, output hash, and idempotency key; the first accepted completion becomes immutable and later duplicate completion attempts are rejected. A stale lease never overwrites a completed run.

Lease recovery moves an expired active attempt to `lease_expired`, appends immutable history, and either schedules `retry_wait` or `dead_letter`. Reassignment increments `attempt_number` and selects a new candidate unless deterministic retry affinity is explicitly safe. Cancellation wins before completion if its durable timestamp precedes completion acceptance.

## Runner protocol

Runner-only endpoints require a separate runner credential and are not MCP tools or browser APIs:

| Operation | Intent |
| --- | --- |
| `register` | Create or refresh a runner registration with safe declared capabilities. |
| `heartbeat` | Refresh runner presence and active-job liveness. |
| `claim` | Atomically claim one scheduler-selected compatible job. |
| `lease renew` | Extend one matching active lease. |
| `complete` | Submit a bounded result with reproducibility and hash evidence. |
| `fail` | Submit a categorized safe failure. |
| `cancellation acknowledge` | Confirm a requested cancellation stopped execution. |
| `enter/exit draining` | Stop or resume new claims while retaining active-job handling. |
| `enter/exit maintenance` | Record an approved maintenance state. |
| `release` | Mark a gracefully stopped runner unavailable. |

Every runner request includes a protocol version, runner ID, monotonic request ID, and time-bounded authentication proof. The Worker validates payload size, schemas, state, assignment, and version compatibility. Runner credentials are rotated independently from user OAuth and never appear in logs, responses, Control Center pages, or job history.

## Linux CPU runner

The Linux runner is a Python process packaged for a container-compatible deployment. It runs non-root with only allowlisted built-in deterministic engines where dependencies are present.

- No arbitrary user code, `eval`, `exec`, `shell=True`, dynamic imports from job input, or dynamic package installation.
- Bounded CPU, memory, wall-clock execution time, job payload size, result size, and artifact count.
- Read-only filesystem where practical, with an isolated temporary writable directory per job that is removed after completion.
- No host network access except the configured Worker endpoint; no inbound listener is required.
- Separate runner-only authentication, periodic heartbeat, draining, graceful shutdown, cancellation acknowledgement, and result input/output hash verification.
- Container image is pinned by digest, includes a software bill of materials, and is built from reviewed dependencies.

The macOS runner stays supported through the same protocol. The scheduler treats operating system as metadata and engine compatibility as the execution authority.

## Control Center fleet UI

Phase 2B.1 adds authenticated route `/runners`. It displays only safe fleet metadata:

- runner ID, state, operating system, architecture, and versions
- supported engines, available slots, active jobs, heartbeat age, and failure count
- maintenance and quarantine state

Administrative actions are drain, resume, enter/exit maintenance, quarantine, restore, and inspect jobs. Every mutation requires an authenticated Control Center session, same-origin CSRF protection, schema validation, explicit confirmation, and an audit record containing actor, target, prior state, requested action, result, and safe reason. Browser clients cannot choose an internal endpoint, Worker authorization header, or runner credential.

## Proposed database changes

No migration is created by this planning branch. The implementation should introduce additive migrations in this order:

1. Extend `lab_engine_runners` or add a versioned runner-registry table for state, runtime/OS metadata, capacity, priority, region, heartbeat, maintenance, quarantine, and safe failure counters.
2. Extend `lab_engine_jobs` with assignment, lease, attempt, retry, dead-letter, and terminal-reason fields.
3. Add immutable `lab_engine_job_attempts` for claims, renewals, reassignment, cancellation, completion acceptance, and safe failure history.
4. Add `lab_engine_runner_audit_events` for administrative fleet actions and policy decisions.
5. Add indexes for eligible-runner lookup, lease expiration recovery, runner-job inspection, and dead-letter operations.

Migrations must backfill current `mystic-mac-runner` state without exposing its host details, preserve existing job/run identifiers, and keep Phase 2A single-runner behavior available behind a compatibility path until fleet rollout is proven.

## Security boundaries

- MCP OAuth authenticates user-facing and ChatGPT requests; it never authorizes a runner endpoint.
- Runner-only credentials authenticate runners; they never authorize Control Center or MCP actions.
- Control Center administrative actions use authenticated sessions, CSRF defenses, allowlisted BFF routes, confirmation, and audit logging.
- Supabase service credentials stay Worker-only. Browser and runner clients do not receive them.
- Job inputs remain schema-validated engine parameters. They cannot select a binary, command, package, path, host, environment variable, or runner bypass.
- Errors are categorized and safe. Authorization headers, tokens, private topology, raw host diagnostics, and full provider responses are not persisted or returned.
- Audit records are immutable to ordinary administrative actions and are retained according to the project retention policy.

## Test plan

1. Registry unit tests: allowed state transitions, stale detection, capacity, maintenance, draining, quarantine, and redaction.
2. Scheduler unit tests: exact candidate filters, deterministic ordering, retry affinity, region preference, capacity, and no-candidate behavior.
3. Lease integration tests: atomic concurrent claims, renewal, expiration recovery, reassignment, cancellation races, idempotent completion, duplicate rejection, retry limits, and dead letter.
4. Runner contract tests: protocol versioning, runner-only authentication, payload bounds, hash mismatch rejection, graceful drain, and release.
5. Linux container tests: non-root execution, allowlist-only engines, read-only filesystem, bounded temporary directory, CPU/memory/time limits, and no dynamic package installation.
6. Control Center tests: authenticated `/runners`, CSRF failures, confirmations, audits, safe display, job inspection, and no credential leakage.
7. Regression tests: all Phase 2A engine, MCP, OAuth, local mode, Supabase, scene, and report behavior remains intact.
8. Live acceptance: two compatible runners complete the prescribed failover sequence with valid hashes, no duplicate runs, accurate fleet UI, `READY_PUBLIC_MCP_LAB`, and `import_ready=true`.

## Deployment plan

1. Ship additive schema migration and Worker support with fleet scheduling disabled by feature flag.
2. Register the existing macOS runner using the new protocol while preserving the Phase 2A compatibility path.
3. Deploy the Linux CPU runner in a non-production environment and run contract, resource-bound, and failure tests.
4. Enable shadow scheduling decisions and compare them with the active single-runner selection without issuing duplicate claims.
5. Deploy `/runners` read-only UI, then gated administrative actions with audit verification.
6. Register one production Linux runner, execute staged real jobs, then perform the live drain, failover, and runner-stop acceptance sequence.
7. Enable fleet scheduling only after metrics, audit logs, smoke, readiness, and duplicate-execution checks are green.

## Rollback plan

- Disable fleet scheduling through the feature flag and return to the Phase 2A compatibility selector.
- Mark a faulty runner draining or quarantined; do not delete its history.
- Stop the Linux runner and retain the macOS runner as the known-good capacity path.
- Preserve attempts, leases, hashes, and audit records for diagnosis. Never rerun a completed job as rollback.
- Roll back Worker and Control Center deployments independently only to the immutable `phase-2a-production` baseline after confirming schema compatibility. Additive migrations are not destructively reverted in production.

## Production acceptance sequence

1. macOS runner is online.
2. Linux CPU runner is online.
3. Both advertise compatible projectile capability.
4. Submit a first projectile job and record the selected runner.
5. Verify the first job completes with valid hashes.
6. Put the selected runner into draining.
7. Submit a second projectile job and verify the other runner completes it.
8. Stop one runner, submit a third job, and verify the remaining runner completes it.
9. Verify no duplicate runs or duplicate completion records exist.
10. Verify ChatGPT MCP execution remains functional and Control Center reflects the true fleet state.

## Issue breakdown

- #111: Phase 2B epic and cross-milestone policy.
- #112: Phase 2B.1 runner registry, scheduler, Linux CPU runner, fleet UI, and live failover.
- Proposed follow-ups: fleet schema/lease migration; runner protocol and macOS compatibility; Linux image and hardening; scheduler/recovery; Control Center fleet controls; production failover acceptance; then separate 2B.2 computer control, 2B.3 Home Assistant/IoT, 2B.4 OAuth/OIDC/DCR/CIMD, and 2B.5 GPU engines.

## Unresolved design decisions

- Whether runner credentials use per-runner opaque tokens, mTLS, workload identity, or a staged combination.
- Exact lease TTL, heartbeat cadence, retry backoff, maximum attempts, and dead-letter retention policy by engine/resource class.
- Whether region preference is user-requested, policy-derived, or deferred until a multi-region fleet exists.
- The minimum Linux isolation technology for production: container runtime alone, sandboxing, or a microVM boundary.
- Whether the registry remains a Supabase-first transaction model or requires a Worker durable coordination primitive under higher concurrency.
- Audit retention, operator roles, and approval requirements for quarantine/restore in regulated deployments.

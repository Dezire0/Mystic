# ALETHEIA A1 contract inventory — Mystic

**Status:** documentation only. No runtime, storage, schema, or admission behavior changes. Baseline: Mystic origin/main 599f5fe1, with the reviewed vNext architecture documentation carried from PR #148. This inventory makes future work additive: Mystic remains usable without THE WHOLE, and a bridge wraps typed public operations rather than reading files.

## 1. Current contracts and call sites

| Contract / public operation | Definition; current callers/tests | Read/mutation, persistence and concurrency | Classification |
| --- | --- | --- | --- |
| ResearchCampaign | mystic/lab/campaign.py; CampaignRuntime; tests/test_campaign_runtime.py | Durable aggregate with revision, hashes, checkpoints and timeline | **KEEP — DO NOT EXPOSE** raw aggregate |
| CampaignRuntime.create_campaign/get/list | mystic/lab/campaign_runtime.py; Lab-facing code and campaign tests | Create idempotent only with key; get/list read CampaignStorage; list limit defaults to 50 | **WRAP** as bounded redacted DTOs |
| transition/pause/resume/cancel/retry/mark_failed | CampaignRuntime; campaign tests | CampaignStorage.save(expected_revision); selected operations record keys | **WRAP** behind authority |
| checkpoint/rollback/graph/timeline/statistics | CampaignRuntime; campaign tests | Checkpoint/rollback mutate; timeline default limit 100; graph supports latest-only | **WRAP** bounded reads/checkpoint command |
| register_scientific_job_intent/attach_scientific_job_result/record_scientific_job_failure | CampaignRuntime; ScientificJobRuntime attachment/reconciliation | Campaign CAS plus attachment key protect logical exactly-once attachment | **KEEP — DO NOT EXPOSE** directly |
| CampaignStorage | mystic/lab/campaign_storage.py; used only by CampaignRuntime | Local lock, atomic/fsync JSON; save requires expected revision | **DO NOT EXPOSE** |
| ScientificJob and request/result/failure/lease/outbox/attachment | mystic/lab/scientific_job.py; job runtime and tests | Input/result hashes, campaign revision observation, lease history, outbox, attachment | **KEEP — DO NOT EXPOSE** raw aggregate |
| ScientificJobRuntime.create_job/get/list | mystic/lab/scientific_job_runtime.py; adapter/worker and job tests | Key validation; bounded limit/status/campaign list | **WRAP** as safe summary/detail and approved intent |
| acquire/start/heartbeat/complete/fail/cancel/retry/reconcile | ScientificJobRuntime; worker/runtime tests | Lease owner/token fences execution; retry/outbox/reconcile retain late results | **KEEP — DO NOT EXPOSE** to sessions |
| ScientificJobStorage | mystic/lab/scientific_job_storage.py | Locked atomic JSON, expected revision, bounded list | **DO NOT EXPOSE** |
| ScientificEngineJobAdapter and ScientificJobWorker.run_once | mystic/lab/scientific_job_adapter.py; worker tests | Leased job to registry engine then terminal report | **KEEP** deterministic worker adapter |
| EngineRegistry.get/list | mystic/lab/engines/registry.py; engine runtime/job adapter tests | In-memory manifests, no authority or admission | **WRAP** allowlisted availability only |
| ScientificEnginePlugin/Manifest/Result | mystic/lab/engines/base.py and manifest.py | Validation, estimate, cancellation, evidence/visualization metadata | **KEEP; EXTEND** external descriptor |
| EngineRuntime.create_job/execute_next | mystic/lab/engines/runtime.py; engine runtime tests | In-memory queue, separate from durable ScientificJob | **DEPRECATE** for bridge use |
| claims and experiments | mystic/lab/claims.py, experiments.py, campaign data | Local scientific validation/state | **COMPOSE**, never remote storage |
| verification helpers | mystic/verification and mystic/agents/verification | Deterministic/local helpers; no permanent referee | **KEEP — DO NOT EXPOSE** |
| MCP server/toolbox | mystic/mcp/server.py, tools.py, schemas.py; MCP tests | JSON-RPC/stdin with tool-specific schemas | **DO NOT REUSE** as generic bridge |

### Current scientific tool fabric

The authoritative local source is mystic/lab/engines/builtin/__init__.py through builtin_registry(). No item is automatically WORLD-admitted.

| ID/version | category | locality/resource | shape/reproducibility | admission |
| --- | --- | --- | --- | --- |
| math.sympy 1.0.0 | deterministic | local CPU | bounded object to EngineResult; bounded grammar/installed SymPy | candidate only |
| physics.simple_projectile 2.0.0 | deterministic | local tiny CPU | kinematic object to trajectory; assumptions included | candidate only |
| physics.simple_collision 2.0.0 | deterministic | local tiny CPU | bounded masses/velocities to result | candidate only |
| physics.n_body 1.0.0 | compute | local small CPU | 2–8 bodies/time step to trajectory; cancellation; educational precision | candidate only |
| chemistry.reaction_kinetics 1.0.0 | compute | local small CPU | mass-action object to time series; deterministic Euler method | candidate only |
| biology.population_dynamics 1.0.0 | compute | local CPU | logistic/Lotka–Volterra to time series | candidate only |
| engineering.dc_circuit 1.0.0 | deterministic | local CPU | low-voltage divider to nodal result | candidate only |
| Lightning/NVIDIA specialists | experimental/external | remote GPU only when dispatched | dispatcher input to evidence candidates; benchmark evidence retained | **not default/admitted** |

No current unrestricted retrieval/literature network-tool contract exists. A future external tool needs explicit locality, authority, budget, bounded result, provenance, resource class, and failure semantics.

## 2. Identity and evidence boundary

| Identity | owner / persistence | scope | crosses bridge | never infer |
| --- | --- | --- | --- | --- |
| project_id | future WORLD ProjectScope | global/stable | query/command required | campaign |
| campaign_id, campaign_revision | Mystic campaign and CampaignStorage | global/stable; monotonic | relevant query/command | project without link |
| management_seat_id | future WORLD seat template | deterministic project scope | metadata | provider/model |
| actor_id, session_id, controller_generation, backend_id | WORLD session domain | actor stable; session/controller ephemeral | command provenance | seat to session/backend |
| provider/model observation | WORLD session provenance | observation only | optional redacted provenance | logical role |
| task_slot_id, scientific_task_profile_id | future contract | bounded/project scoped | relevant reads/commands | job or session |
| scientific_job_id | Mystic job storage | stable/global | job references/queries | WORLD Runtime Job |
| evidence_id, artifact_id | Mystic campaign aggregate | campaign scoped | metadata only | storage path/full content |
| authority_grant_id, budget reference | WORLD | grant/reference scoped | command required | authority from Mystic |
| idempotency/correlation/trace | caller plus campaign/job records | request scoped | command required | changed intent from same key |

Current Evidence in campaign.py includes summary, type, source, support/refute IDs and canonical content hash; Artifact records a campaign-scoped reference. It has no typed external verification lifecycle.

| class | current representation | gap / bridge safety |
| --- | --- | --- |
| working note | timeline or graph payload convention | no lifecycle/retention type; do not cross |
| candidate evidence | Evidence plus artifact/graph reference | needs verification/provenance envelope; metadata only |
| verified evidence | Evidence plus Review/verification convention | needs typed verification link |
| rejected evidence | Failure, Review, timeline/graph convention | needs typed rejected/superseded link |
| historical evidence | supersedes graph edge and timeline | needs immutable lifecycle projection |

MNEME remains a WORLD reference/bridge concern. A future projection uses immutable references, hashes, privacy class and lineage; it does not create a second universal-memory writer.

## 3. ProjectScope, seat, and task-slot gaps

| Target | reusable source | gap / non-duplication rule | owner |
| --- | --- | --- | --- |
| Project identity/kind/module owner | none in Mystic | do not create a second project registry in campaign metadata | WORLD ProjectScope |
| Campaign link/revision observation | job campaign fields and campaign revision | explicit project-to-campaign link missing | WORLD ProjectScope observing Mystic |
| Manager template/current session | none | do not store provider/session on campaign | WORLD ProjectScope/session store |
| Actor/wake/lifecycle/authority/budget refs | CampaignBudget/runtime are local only | must not become WORLD lifecycle or authority | WORLD |
| Checkpoint/provenance observation | checkpoint/timeline/correlation | bounded projection, not storage access | Mystic query port |

The management seat is a WORLD projection, never a Mystic aggregate: aletheia.project.<project-id>.manager. SOPHIA and Research Director are display metadata. Future Mystic commands receive project ID, template version, actor/session trace, controller generation, authority grant, budget reference and correlation ID.

| Existing candidate | result | reason |
| --- | --- | --- |
| ScientificJobRequest | **COMPOSE** | engine/version/input/campaign revision/correlation but no role, allowed tools, evidence/gather/session binding |
| ScientificJob | **COMPOSE** | durable execution/retry/lease/attachment, not research-role intent |
| EngineManifest | **REUSE** | tool schema/version/resource substrate, not policy |
| CampaignBudget | **COMPOSE** | local scientific limit, not WORLD authority/budget |
| campaign hook protocols | **INSUFFICIENT** | local extension points, not task/session contract |
| WORLD work requirements/session | **COMPOSE** | selection/lifecycle pieces, not scientific evidence/result contract |

Minimal future contracts: ScientificTaskProfile (role, allowlisted tools, expected result, evidence/verification requirement, local limits) and TaskSlot (project/campaign/profile, bounded intent, gather policy, job/session binding, terminal reason). They reference rather than duplicate jobs, sessions, authority, budgets and evidence.

## 4. Future Aletheia ports — inventory only

### Query port

| query | source | input to output | bounds/privacy | availability |
| --- | --- | --- | --- | --- |
| campaign_summary | CampaignRuntime.get/statistics | campaign ID to phase/status/revision/counts/checkpoint observation | one redacted item | wrapper required |
| campaign_snapshot | snapshot_state, graph(latest_only) | campaign ID to selected state | allowlist only; no raw snapshot | wrapper required |
| scientific_jobs | ScientificJobRuntime.list | campaign/status/cursor/limit to summaries | current limit; cursor wrapper required | wrapper required |
| scientific_job_detail | get plus safe DTO | job ID to status/hash/attempt/attachment | no raw input/result | wrapper required |
| evidence_metadata | evidence/artifacts/reviews | campaign/cursor/limit to IDs/hashes/lifecycle | no contents/paths | typed lifecycle missing |
| verification_metadata | reviews/job failure/attachment | target to verdict/method/time/ref | safe summary | schema wrapper required |
| tool_availability | EngineRegistry.list | domain/capability to manifest projection | bounded | no admission field |
| checkpoint_progress | checkpoints/timeline/statistics | campaign to latest revision/progress | no path | wrapper required |

All queries are read-only, side-effect free and bounded. They may not create data, scan all history, persist observations, leak paths/secrets, or return document/artifact contents.

### Command port

Every command carries project_id, ProjectScope revision, campaign ID/observed campaign revision as needed, actor/session trace, controller generation for session work, authority grant, budget reference, idempotency key, typed payload, and correlation ID. Unknown fields fail closed.

| command | current delegate | conflict/duplicate/late behavior | adapter gap |
| --- | --- | --- | --- |
| create_or_link_campaign | CampaignRuntime.create_campaign | same key replays; project link is new WORLD state | typed link/redacted response |
| request_scientific_work | future slot then approved job | stale scope/campaign revision rejects | TaskProfile/TaskSlot |
| create_scientific_job | ScientificJobRuntime.create_job | hash/key mismatch rejects | authority/tool allowlist |
| submit_session_result | future slot resolver then completion/attachment | lease/session/controller mismatch or late terminal result rejects and audits | slot/session provenance |
| attach_candidate_evidence | campaign evidence/artifact path | CAS/duplicate attachment conflict explicit | typed lifecycle/provenance |
| request_verification | future coordinator | idempotent request; no permanent referee | verification schema |
| checkpoint_campaign | CampaignRuntime.checkpoint | current idempotency/CAS retained | authority/revision wrapper |
| pause/resume/cancel | campaign/job runtime | transition errors explicit; cancellation cooperative | typed target/scope |

## 5. Call-site risks and frozen fixtures

| Contract | definition | callers/tests | persistence | additive rule / rollback | protected |
| --- | --- | --- | --- | --- | --- |
| campaign aggregate/runtime | campaign.py, campaign_runtime.py | campaign tests; job attachment calls | CampaignStorage CAS/checkpoints | add/remove wrapper only | yes |
| campaign storage | campaign_storage.py | CampaignRuntime | local atomic/fsync/lock | no bridge edit | yes |
| job aggregate/runtime | scientific_job.py, scientific_job_runtime.py | adapter/worker/job/migration/staging tests | JobStorage plus campaign attachment | delegate only; preserve outbox/reconcile | yes |
| engine registry/plugins | engines registry/base/manifest/builtin | engine/runtime/job adapter tests | in-memory/plugin local | descriptor wrapper only | yes |
| engine runtime | engines/runtime.py | engine runtime tests | in-memory queue | never bridge it | yes |
| MCP | mcp server/tools/schemas | MCP tests | tool-specific | no generic reuse | yes |
| verification | verification directories | verification callers/tests | local artifacts/config | dedicated adapter later | yes |
| specialist evidence | dispatcher/approval/benchmark modules | specialist tests | explicit evidence artifacts | experimental only | yes |

A1 specifies fixtures only; B1 owns versioned JSON and its hash. Each fixture has synthetic IDs/metadata only: no credential, token, private research, PDF/document body, or storage path.

| Fixture | assertion |
| --- | --- |
| a1.project-one-campaign | explicit project-to-campaign link and observed revision |
| a1.manager-no-session | deterministic seat with no session |
| a1.manager-session-bound and a1.manager-replacement-session | session observation/replacement never changes seat identity |
| a1.same-backend-two-slots | isolated slots/sessions can share one backend |
| a1.job-deterministic-tool and a1.slot-to-job | manifest/version/input hash; slot references job |
| a1.evidence-candidate, a1.evidence-verified, a1.evidence-rejected | lifecycle metadata explicit |
| a1.stale-campaign-revision and a1.duplicate-idempotency-key | conflict preserved; same intent replay only |
| a1.late-session-result | rejected/audited without replacing accepted evidence |
| a1.campaign-sleeping and a1.campaign-completed | WORLD lifecycle and Mystic observation stay distinct |
| a1.bridge-unavailable | unknown/unavailable state, no synthetic counts |

## NEXT IMPLEMENTATION PACKAGES

### TERRA P1 — ProjectScope + management-seat projection
- **Allowed:** new THE WHOLE project domain/store/service/tests and seat-template fixtures; links here only.
- **Protected:** Mystic campaign/job storage and WORLD session semantics.
- **Consumes:** identity matrix and explicit project-to-campaign link.
- **Prerequisites:** versioned ProjectScope and authority/budget-reference schemas.
- **Acceptance:** CAS/fencing, isolation, no provider/session in seat, replacement attribution.

### SOL B1 — versioned bridge contracts
- **Allowed:** new typed query/command DTOs, adapters and tests in both repos.
- **Protected:** CampaignStorage, ScientificJobStorage, raw MCP, admission state, worker APIs.
- **Consumes:** port tables and A1 fixtures.
- **Prerequisites:** P1 identity/revision and authority grant.
- **Acceptance:** bounded/redacted reads; typed commands; stale/duplicate/late behavior preserved.

### TERRA T1 — ScientificTaskProfile / TaskSlot
- **Allowed:** new Mystic task contracts and focused tests; bindings after B1.
- **Protected:** ScientificJob lifecycle, manifests, campaign CAS/outbox.
- **Consumes:** compose decisions and fixture slot cases.
- **Prerequisites:** P1 link and B1 provenance envelope.
- **Acceptance:** tool/evidence/gather policy; explicit job/session binding; same-backend isolation.

### SPARK C1 — Console projection
- **Allowed:** THE WHOLE Console mappings/DTOs/tests and docs.
- **Protected:** shared Console primitives, admission, live counts.
- **Consumes:** B1 query DTOs and unavailable fixture.
- **Prerequisites:** query-only bridge.
- **Acceptance:** Projects/Pipeline/Jobs/Tools/Evidence with Sessions sidecar; **NO SOURCE = UNKNOWN / OMIT**.

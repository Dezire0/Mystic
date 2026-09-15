# ALETHEIA Architecture vNext

Status: **target architecture; no runtime behavior changes in this document**
Issue: [#147](https://github.com/Dezire0/Mystic/issues/147); review: [PR #148](https://github.com/Dezire0/Mystic/pull/148); initial implementation commit: `587599d8eae9d0d69a67f974170a76da35fee3c6`.
Audit baselines: Mystic `599f5fe1` (2026-09-06), THE WHOLE `d37a529` (`dev`, 2026-09-14)

This is the integration-ready companion to [the canonical Mystic goal](goal.md) and the [Project Session Loop](aletheia-project-session-loop.md). It does not replace either document's strategy status. It makes the ownership boundary and the implementation sequence explicit so a bridge can be built without making ALETHEIA another agent OS.

## 1. Canonical definition

**ALETHEIA is Mystic's independently useful scientific research fabric.** It owns durable scientific domain state, campaigns, scientific execution intent, tool/experiment semantics, hypotheses/questions/claims, evidence, verification records, reproducibility metadata, and workbench projections.

It is not a single agent, a permanent director, a provider/model registry, a generic job runtime, a universal memory system, or a source of authority. Frontier models are temporary reasoning resources assigned by WORLD sessions. Specialist models remain optional scientific tools only when their evidence supports use; they are not scientific personalities.

```text
WORLD ProjectScope / authority / session lifecycle
                 |
        bounded command or query port
                 |
ALETHEIA research campaign + scientific jobs + tools + evidence
                 |
     scientific artifacts, verification, checkpointed state
```

Mystic must continue to load campaigns, execute allowed scientific tools, inspect evidence, and use the workbench without THE WHOLE. WORLD adds orchestration, identity, authority, and session lifecycle; it does not replace scientific-domain semantics.

## 2. Current-state audit

| Current component | Current owner | Current purpose | Keep / modify / deprecate | New owner | Rationale |
| --- | --- | --- | --- | --- | --- |
| [`ResearchCampaign`](../mystic/lab/campaign.py), [`CampaignRuntime`](../mystic/lab/campaign_runtime.py) | Mystic/ALETHEIA | Versioned scientific aggregate, budget, phase, graph, checkpoint and timeline coordination | Keep; add a narrow external decision/application boundary later | ALETHEIA domain state; WORLD owns project reference | CAS, checkpoint and recovery semantics are valuable; a session must not write private campaign state. |
| [`ScientificJob`](../mystic/lab/scientific_job.py), [runtime](../mystic/lab/scientific_job_runtime.py) | Mystic/ALETHEIA | Durable engine intent, lease/outbox/retry, validated result and logically-once campaign attachment | Keep | ALETHEIA execution intent | It is a trusted scientific work unit, not a chat, provider session, or replacement WORLD Runtime job. |
| [`EngineRegistry`](../mystic/lab/engines/registry.py) and scientific engine adapters | Mystic/ALETHEIA | Allowlisted deterministic/scientific capability execution | Keep; normalize external capability catalogue later | ALETHEIA Tool Fabric | Scientific tools are capabilities, not Agent Seats. |
| Campaign `Evidence`, `Artifact`, claims, experiments and reports | Mystic/ALETHEIA | Scientific provenance and research interpretation | Keep; add typed cross-system references | ALETHEIA for domain evidence; WORLD/MNEME for global lineage references | Avoids a second universal MNEME clone and dual writers. |
| Campaign/jobs/evidence Control Center projections | Mystic/ALETHEIA | Scientific workbench and operator views | Keep; later provide query projections to WORLD Console | ALETHEIA projection | UI is a projection, never authority or scientific truth. |
| Mystic MCP and server/BFF interfaces | Mystic/ALETHEIA | Existing bounded scientific operations | Keep; adapt through explicit bridge ports | ALETHEIA public/domain boundary | WORLD must not reach private local/Supabase storage. |
| Specialist benchmark, approval and Lightning dispatcher paths | Mystic/ALETHEIA | Optional tool-backend evidence and bounded retrieval execution | Keep as experimental/tool evidence | ALETHEIA Tool Fabric | They are not permanent scientific agents and do not make a candidate approved. |
| THE WHOLE `AletheiaAdapter` | WORLD | Unavailable zero-capability placeholder | Modify only in a later admitted bridge package | WORLD integration boundary | Current unavailable state is truthful; do not relabel it healthy. |
| THE WHOLE `ProjectRegistry` / target `ProjectScope` | WORLD | Today: declarative project metadata; target: durable project/session coordination boundary | Keep; implement ProjectScope before live bridge | WORLD | Project ownership, identity and lifecycle are WORLD concerns. |
| THE WHOLE `DurableActor`, `InteractiveSession`, `SessionBackend` | WORLD | Durable actor/session identity, fencing and replaceable reasoning backend lifecycle | Keep | WORLD | These must remain distinct from seats, task profiles and models. |
| THE WHOLE WorkSelector | WORLD | Admission-gated selection/reservation only | Keep; use only after ProjectScope decides a session need | WORLD | It does not create sessions or grant effects. |
| MNEME | WORLD external durable realm | Canonical WORLD lineage and bounded semantic persistence | Keep | WORLD/MNEME | It is not a scientific claim graph replacement. |
| WholeBench/Evaluation | WORLD | Deterministic evidence/admission for WORLD components | Keep; consume references only where appropriate | WORLD | It does not verify scientific truth or auto-admit ALETHEIA. |

### Stale assumptions corrected

1. “Director”, “Theorist”, and “Referee” are not permanent model assignments. Existing campaign hooks are deterministic extension points, not proof of live agent roles.
2. An `AgentBindingDescriptor` is a data-only, provider-specific legacy conversation declaration; it is not the project-management seat proposed here.
3. THE WHOLE's `aletheia` project metadata and adapter are placeholders. `existing_partial` does **not** mean an admitted production bridge.
4. A successful Lightning run or specialist benchmark is evidence about a tool/backend, not an admission of ALETHEIA or a model identity for a scientific role.
5. A campaign's `runtime.iteration` currently counts phase transitions. It must not silently be reinterpreted as a frontier research-cycle counter.

## 3. Ownership and identity model

| Concept | Owner | Stable identity | Explicit non-identity |
| --- | --- | --- | --- |
| `ProjectScope` | WORLD | `project_id` | Campaign, model/provider, session backend |
| ResearchCampaign | ALETHEIA | `campaign_id`, revision | WORLD actor/session |
| Project-management seat | ALETHEIA template, projected in WORLD project | `aletheia.project.<project-id>.manager` | Provider/model, `AgentBinding`, active session |
| `DurableActor` | WORLD | `actor_id` | Seat, session, backend |
| `InteractiveSession` | WORLD | `session_id`, fenced controller generation | Actor, seat, provider/model |
| `SessionBackend` | WORLD | admitted backend ID/version | Session and provider/model identity |
| `ScientificTaskProfile` | ALETHEIA vocabulary | versioned profile ID | Persistent agent/model |
| Task slot | Project-scoped decision/projection | decision + slot ID | A durable agent identity |
| `ScientificJob` | ALETHEIA | `job_id` | LLM task/session or generic WORLD job |
| Scientific tool | ALETHEIA capability | tool/capability ID + version | Seat or agent |

### Management seat: projection, not a new persistence silo

Choose a **versioned template projected per ProjectScope**, rather than a new always-persisted seat aggregate. The template contains presentation/config metadata such as `display_name: SOPHIA` and `role: Research Director`; it creates the canonical ID above deterministically from the project ID. The initial ProjectScope record persists only its current `management_session_ref`, seat-template version, and provenance needed for recovery. WORLD's session/event records preserve historical session attribution.

This avoids duplicating WORLD's identity semantics while preserving a stable logical management role. On session loss, WORLD binds a replacement session to the same seat; it never makes the old provider/model the seat identity.

### Temporary scientific task slots

`ScientificTaskProfile` is an ALETHEIA allowlisted vocabulary, initially including literature research, theory exploration, counterexample search, simulation, symbolic computation, formal proof attempt, data analysis, adversarial review, evidence synthesis, and verification. A `TaskSlot` is a bounded project decision with profile, allowed capabilities, input/evidence references, authority/budget constraints, deadline, expected result shape, and gather policy.

It is materialized only when a campaign decision needs work. It binds to one or more WORLD `InteractiveSession`s or to one ALETHEIA `ScientificJob`; it never identifies a permanent person or model. Multiple slots may bind concurrently to sessions using the same backend, each with isolated context and its own controller generation.

## 4. Research lifecycle and ScientificJob relationship

The domain supports branching and cycles, not a rigid DAG:

```text
WAKE -> read ProjectScope + campaign snapshot -> bounded research decision
  -> request TaskSlots / ScientificJobs / tools -> gather results
  -> verify or challenge -> attach evidence -> campaign checkpoint
  -> continue | wait | sleep | escalate | complete
```

The management session proposes work; WORLD validates authority/budget/session capacity; ALETHEIA validates scientific-domain commands. A result never becomes campaign truth merely because a session says so.

| Path | Relationship |
| --- | --- |
| `ResearchCampaign -> ScientificJob -> deterministic tool/compute` | Current durable intent path. The job owns worker-facing lease/retry/outbox/result state and campaign attachment remains logically once. |
| `ResearchCampaign -> TaskSlot -> InteractiveSession` | Future reasoning path. The session returns a bounded proposal, notes, evidence references, or a request for allowed scientific work. |
| `TaskSlot -> ScientificJob` | A session may propose an execution intent; after WORLD authority and ALETHEIA schema validation, ALETHEIA creates the campaign-linked job. |
| `ScientificJob -> evidence -> campaign checkpoint` | A trusted worker returns validated result provenance; the job runtime attaches it exactly once or records a durable rejection. |

The first ProjectScope bridge must carry campaign revision and idempotency identity. A late task/job result stays historical evidence but cannot mutate a newer campaign decision generation. Campaign pause/cancel, job cancellation, revision conflict, budget exhaustion, capacity wait, auth expiry and session loss are explicit outcomes, not hidden retry loops.

## 5. Scientific Tool Fabric

The Tool Fabric is the typed, allowlisted catalogue that maps a task profile to scientific capabilities under both WORLD and ALETHEIA policy. It may include symbolic algebra, formal proof, numerical simulation, code/experiment execution, retrieval, scientific databases, vector retrieval, GPU compute, visualization, validators and artifact readers.

For each capability it records: semantic name/version, ALETHEIA input/output schema, locality/resource class, required evidence and reproducibility fields, authority ceiling, budget class, runner/engine allowlist, and failure semantics. WORLD decides whether a session may request the capability and whether capacity/budget/approval permit it. ALETHEIA rejects a request that violates scientific schema, campaign state, engine allowlist, or reproducibility requirements. Neither side exposes arbitrary shell, database, provider, or storage access.

Existing `ScientificJob` adapters remain the tool/worker boundary for durable computation. A future generic WORLD Capability Proxy authorizes a session request; it must not bypass that job boundary or make WORLD a duplicate scientific engine runtime.

## 6. Evidence and verification

ALETHEIA evidence records preserve, when meaningful: question/claim, supporting or contradicting role, source/artifact references, method/tool/session/job/model identity, bounded input/output hashes, timestamps, engine/model version, verification state, reproducibility metadata and relation to campaign revision/checkpoint.

| Evidence class | Persistence rule |
| --- | --- |
| Working note | Session-local/checkpointed context; not scientific evidence by default. |
| Candidate evidence | Attached to campaign with provenance, pending verification. |
| Verified evidence | Attached only after an applicable verification record. |
| Rejected evidence | Preserved with reason; cannot silently disappear. |
| Historical/superseded evidence | Preserved after rollback or late result; cannot rewrite current campaign state. |

MNEME stores WORLD-owned global references, audit lineage, project/session authority and bridge receipts. Mystic remains the delegated scientific domain writer. Large artifacts cross the boundary by immutable IDs, version/content hash, locality and resolver metadata—not duplicated raw contents. No cross-store dual writer or distributed transaction is introduced; use an outbox, stable event IDs, idempotency, reconciliation and explicit writer fencing.

Verification is a first-class task profile, not a permanent Referee AI. The profile selects an appropriate path: formal proof/checker or counterexample search for mathematics; dimensional/invariant/numerical replication for physics/simulation; statistical/data validation for analysis; source cross-checking for literature claims; and independent tool/session review where deterministic proof is unavailable. `inconclusive` is valid. Agreement among sessions using one model is not independent scientific confirmation.

## 7. WORLD bridge and authority

Implement a narrow pair of versioned ports, not generic RPC:

| Port | Allowed operations | Boundary |
| --- | --- | --- |
| `AletheiaQueryPort` | campaign summary/snapshot, job summary, evidence query/projection, tool availability, progress/checkpoint summary | Read-only, bounded pagination/projections; no private storage access. |
| `AletheiaCommandPort` | create/link campaign for ProjectScope, request validated scientific work, submit bounded task result, attach candidate evidence, request verification, checkpoint/pause/resume/cancel campaign | Requires project/actor/session trace, authority grant/budget refs, expected campaign/project revision, idempotency key and typed payload. |

WORLD owns the principal, ProjectScope, `DurableActor`, session lifecycle/fencing, backend choice, authority grant, budget/capacity, wake records and module admission. ALETHEIA owns campaign state and accepts or rejects a command under its own domain invariants. It cannot grant money, provider use, GPU allocation, publishing, external contact or unrelated WORLD writes. A rejected/unknown bridge state fails closed with a safe code and preserves no fabricated success.

### Wake, sleep and parallelism

No model stays running merely to preserve research continuity. On a wake condition, WORLD restores the management context from ProjectScope references and starts/resumes a fenced management `InteractiveSession`. It receives bounded campaign/evidence summaries, makes one bounded decision, checkpoints through the command port, then sleeps. A sleeping session requires a WORLD checkpoint; replacement reconstruction is explicit when provider continuity is unavailable.

Fan-out first reserves bounded capacity and records expected slots/results/deadline/revision. Same-backend sessions can run concurrently because each is an independent session/slot with isolated context and evidence attribution. Gather rules state required/minimum results, cancellation and deadline behavior. Late results remain evidence only.

## 8. Truthful module projection and WORLD Console

Until an admitted bridge exists, the module card must show axes rather than a green status:

| Field | Current truthful projection |
| --- | --- |
| Implementation | `EXISTING` — Mystic has campaign/job/tool/evidence implementations. |
| WORLD integration | `PLACEHOLDER` — THE WHOLE adapter has zero capabilities. |
| Production bridge/admission | `NOT_ADMITTED`. |
| Runtime health | `UNKNOWN` — no live bridge can be probed. |
| Counts | Omit when no authoritative query exists; never synthesize active projects/sessions/jobs. |

After a query-only bridge, WORLD Console's ALETHEIA workspace has **Projects, Pipeline, Jobs, Tools, Evidence** areas and a right sidecar ordered **Chat, Sessions, Activity**. The pipeline renders a simplified project trigger → management → decision → search/compute/experiment → gather → verification → evidence/checkpoint → continue/wait/sleep topology, labelled as a projection. It must not fabricate an active execution edge or treat a diagram as runtime truth.

## 9. Migration and protected components

1. **Contract inventory:** map current Mystic campaign/job/tool/evidence APIs and current WORLD Session/Capability Proxy/ProjectScope gaps. No model or storage change.
2. **ProjectScope foundation:** WORLD adds project binding and management-seat projection, keeping the current Aletheia adapter unavailable.
3. **Query-only bridge:** an authenticated, bounded read adapter proves project/campaign/job/evidence projections and honest health without command authority.
4. **Command bridge:** add revision/idempotency/authority-gated campaign and work requests; test stale and duplicate behavior.
5. **One human-seeded research cycle:** management session requests one approved scientific tool/job, attaches verified evidence, checkpoints, sleeps.
6. **Wake/gather/concurrency:** prove durable wake recovery, same-backend isolated task sessions, late-result handling and replacement-session reconstruction.
7. **Admitted production bridge:** only after evidence, explicit module admission, rollback and health criteria; never by dashboard relabeling.

Do not change or delete: `ResearchCampaign`, `ScientificJob`, their CAS/lease/outbox/attachment guarantees, current ALETHEIA tools, WORLD session contracts, MNEME semantics, WholeBench/Evaluation, WORLD Runtime, HERMES, OIKOS, or existing data. Legacy fixed-role/model configuration may be retired only after call-site inventory, a replacement path, migration evidence and rollback/deletion gates.

## 10. Implementation packages

| Package | Objective / owned files | Protected files | Dependencies / acceptance | Recommended model |
| --- | --- | --- | --- | --- |
| A1 | Contract inventory and fixture map; docs only in both repositories | Runtime/storage code | Exact call-site matrix and no stale health claims | Spark |
| A2 | WORLD `ProjectScope` domain/store/service with management-seat projection | Mystic campaign/job storage | CAS/fencing, project isolation, no provider/model identity in seat | Terra / Medium |
| A3 | Versioned query-only `AletheiaQueryPort` and unavailable/degraded bridge states | Mystic private storage, module admission | Bounded reads, auth tests, no synthetic counts | Sol / High |
| A4 | `ScientificTaskProfile`/slot command vocabulary and validated command port | `ScientificJob` lifecycle | Authority/revision/idempotency tests; no direct session-to-worker effect | Terra / Medium |
| A5 | Human-seeded management-session pilot and one tool/job/evidence/checkpoint cycle | WORLD global runtime semantics | Real/mock separation, recovery and evidence acceptance | Sol / High |
| A6 | Gather/wake/replacement-session and same-backend concurrency proof | AgentFleet legacy config | Fencing, late-result, restart and capacity tests | Sol / High |
| A7 | WORLD Console ALETHEIA workspace projection | Shared Console primitives | Truthful axes, empty state, no fake counts/live pipeline | Spark |
| A8 | Admission/rollback runbook and final architecture audit | All protected domain contracts | Explicit evidence, fallback and removal conditions | Astra |

## 11. Validation strategy

Documentation validation confirms every linked code path and source state. Implementation packages must add contract tests for identity separation, revision/CAS, authority/budget rejection, session fencing, duplicate/late result handling, evidence reconstruction, sleep/recovery, isolation and truthful module projection. Real provider/T4/tool tests remain opt-in and are reported separately from mocks. No architecture document itself certifies a live bridge.

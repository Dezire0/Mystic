# Research Campaign Runtime (Phase 2C.1)

Mystic's research campaign runtime is the durable coordination layer for autonomous scientific investigations. It is a deterministic workflow runtime, not a chat loop and not an LLM-agent framework. Policy-producing components are extension hooks; the runtime itself only validates commands, persists typed state, enforces budgets, records events, and creates recoverable checkpoints.

## Aggregate and persistence

`ResearchCampaign` is the consistency boundary. It contains campaign metadata, goals, questions, hypotheses, evidence, experiments, scientific models, reviews, failures, decisions, artifacts, graph state, timeline events, checkpoints, budget use, statistics, and runtime versions.

Local mode stores each aggregate at `mystic_data/research_campaigns/<campaign_id>/campaign.json`. Writes use a same-directory temporary file, `fsync`, and atomic replacement. A per-campaign `flock` serializes compare-and-swap writes across processes. Every mutation increments the revision exactly once; a stale expected revision raises a conflict without replacing newer state.

Cloud mode uses the additive `lab_research_campaigns`, `lab_campaign_knowledge_nodes`, `lab_campaign_knowledge_edges`, `lab_campaign_timeline`, and `lab_campaign_checkpoints` tables. Row-level security denies browser roles; only the existing server-side service role can access them. Status changes and checkpoints use row-locking SQL functions.

Campaign data is isolated from Phase 2A/2B LAB sessions, scenes, engines, jobs, and runs. Reverting Phase 2C.1 does not mutate those records.

## Runtime operations

- `create_campaign`: creates a bounded campaign in `PLANNING`, records the goal and optional question, and creates an initial checkpoint.
- `transition`: validates an explicit phase edge, updates counters, records an event, and creates an iteration checkpoint.
- `pause` / `resume`: change operational status without changing scientific phase.
- `cancel`: terminates future runtime work while preserving state and audit history.
- `retry`: reactivates a safely failed campaign in the same scientific phase.
- `checkpoint`: records state, graph, metadata, timing, engine versions, runner versions, and canonical SHA-256 hashes.
- `rollback`: verifies a checkpoint, restores its state and graph, preserves the later audit trail, and checkpoints the restored state.

Commands may carry an idempotency key. Creation derives a stable campaign identifier from that key. Per-campaign mutations persist a bounded key registry; repeating the same operation returns current state without another mutation, while reusing a key for another operation fails safely.

## Budgets and bounds

Campaign budgets bound iterations, experiments, engine seconds, current graph nodes, graph edges, and checkpoints. MCP schemas also bound identifiers, text, tags, list sizes, and pagination. Reaching a budget raises an explicit error without a partial write.

## Extension hooks

The runtime exposes typed hooks for:

- Hypothesis Generator
- Experiment Planner
- Model Selector
- Referee
- Report Writer

No hook is registered by default. A phase that requires a missing hook returns `deferred` and leaves persisted state unchanged. Phase 2C.2 can supply policy implementations without changing the state-machine contract.

## MCP inventory

| Tool | Mutates state | Purpose |
| --- | --- | --- |
| `lab_campaign_create` | yes | Create a bounded durable campaign |
| `lab_campaign_get` | no | Read the safe aggregate projection |
| `lab_campaign_list` | no | List campaign summaries |
| `lab_campaign_pause` | yes | Pause an active campaign |
| `lab_campaign_resume` | yes | Resume a paused campaign |
| `lab_campaign_cancel` | yes | Cancel while preserving audit history |
| `lab_campaign_checkpoint` | yes | Create integrity-hashed snapshots |
| `lab_campaign_graph` | no | Read versioned graph state |
| `lab_campaign_timeline` | no | Read bounded audit events |
| `lab_campaign_statistics` | no | Read counts, phase, status, and budget use |

MCP campaign payloads do not expose idempotency records or checkpoint snapshot bodies. The Control Center uses the same authenticated tools through its BFF.

## Control Center

`/campaigns` provides campaign creation and the Campaign Dashboard. `/campaigns/:campaignId` provides the Campaign Timeline, Knowledge Graph Viewer, Evidence Browser, Experiment Queue, Model Registry, Failure Archive, and Checkpoint Viewer. Empty views explicitly report missing authoritative data instead of fabricating records.

## Recovery procedure

1. Recreate `CampaignRuntime` with the same repository root.
2. Load the campaign by its opaque ID; the latest atomic aggregate is the resume point.
3. If rollback is required, select a checkpoint and call `rollback` from trusted runtime code.
4. The runtime verifies state, graph, and metadata hashes before restoring anything.
5. Continue only from the restored phase and operational status.

The public Phase 2C.1 MCP inventory intentionally does not expose rollback or arbitrary phase advancement. Those are trusted runtime operations until a later authorization and approval design is accepted.

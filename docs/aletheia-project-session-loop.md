# ALETHEIA Project Session Loop

Status: **TARGET / experimental operating hypothesis**  
Canonical strategy: `docs/goal.md`  
Tracking: Issue #145

## Hypothesis

ALETHEIA can operate as one WORLD project without a Global Director or specialist reasoning fleet.

The user starts one project management session. That frontier session communicates with WORLD/Mystic, requests bounded scientific work, sleeps, and is later re-triggered by the server when results/events are available.

The same frontier backend can be opened in multiple isolated task sessions for independent context branches.

## Mapping to existing Mystic resources

```text
WORLD ProjectScope
  |
management InteractiveSession
  |
ResearchCampaign ref
  |
frontier decision request
  |
accepted scientific command
  |
ScientificJob / evidence tool
  |
result attachment
  |
project wake event
  |
management session resume
```

`ResearchCampaign` remains the scientific domain state. `ScientificJob` remains the trusted physical-computation boundary. Neither object becomes a model session.

## Management session

One current fenced management session coordinates ALETHEIA project work. It may propose hypotheses, experiments, task fan-out and result interpretation.

It does not gain direct database/worker/credential authority. Project/domain writes still require current revision, accepted schema and authorization.

If the same provider conversation can resume, preserve it. If not, reconstruct a replacement from bounded project/campaign/evidence state. Scientific continuity must not depend on a tab surviving forever.

## Task sessions

Task sessions are context-isolated branches, not permanent agents.

Example profiles:

- literature/evidence search;
- alternate hypothesis generation;
- counterexample search;
- model/experiment analysis;
- simulation-result interpretation;
- adversarial review;
- report synthesis.

Multiple profiles may use the exact same frontier model/backend.

## Tool rule

Reasoning stays in frontier sessions. Scientific truth claims depend on tools/evidence.

Tools can include:

- search/retrieval/parser/OCR;
- deterministic mathematics;
- simulation;
- parameter fitting/statistics;
- unit/invariant checks;
- counterexample/formal verification;
- CPU/GPU jobs;
- evidence/artifact readers;
- result visualization.

Embedding/reranker models, if used, are retrieval implementation components rather than autonomous scientific agents.

## Server wake loop

### Cycle

1. Management session reads current project/campaign snapshot.
2. It returns a bounded proposal.
3. Server validates and applies allowed domain commands.
4. Task sessions/jobs execute.
5. Results are persisted with evidence refs.
6. Gather policy determines when the project is ready for another decision.
7. A durable wake record targets the current management role/session.
8. The session is triggered/resumed with the new bounded context.
9. It decides next work and sleeps again.

### Never infer completion from text

A worker saying “simulation completed” does not create a ScientificJob result. A management session saying “verified” does not create a verified scientific judgment. The corresponding evidence/tool checks must exist.

## Gather policy

A project batch records parent decision request, task/session IDs, expected results, minimum result threshold, deadline, cancellation and project/campaign revisions.

Possible wake conditions:

- all required results complete;
- N of M independent investigations complete;
- a decisive counterexample arrives;
- deadline expires with partial results;
- one required task fails permanently;
- user/event requests immediate review.

Late results remain provenance but are not silently applied to a newer decision generation.

## PROTEUS experiment

The preferred first visible experiment uses a PROTEUS multi-tab terminal.

- Tab 1: ALETHEIA management session started by user.
- Tabs 2..N: bounded task sessions, possibly same model.
- Server: durable project/campaign/job/evidence state and wake generation.

The critical unknown is not whether multiple tabs can exist. It is whether WORLD can reliably identify and re-trigger/resume the current management session after later server events, repeatedly and safely.

## Proof ladder

### L0 — local/reference contract
Simulate management/task session IDs, gather and wake records without a real frontier provider.

### L1 — one user-started real cycle
User starts management session; one real model decision invokes/requests one real scientific tool; result is persisted.

### L2 — one automatic server wake
A later result event causes the server to trigger/resume the management session once without manual re-prompt.

### L3 — repeated feedback
At least three automatic management wake cycles after initial user start, each reading a newer project/campaign revision.

### L4 — same-model concurrency
Two or more task sessions of the same frontier model execute concurrently under isolated context and are gathered correctly.

### L5 — recovery
Restart server/session transport; recover pending result/wake. Then lose original management tab and verify explicit failure or replacement reconstruction without losing campaign state.

### L6 — bounded autonomy
Run at least two genuine research cycles with budget/capacity/quota/stop policy and no manual next-step prompt.

## Failure and pause conditions

Expected target conditions include:

- `WAITING_FRONTIER`
- `WAITING_RESULT`
- `WAITING_CAPACITY`
- `AUTH_EXPIRED`
- `HUMAN_INTERVENTION_REQUIRED`
- `SESSION_LOST`
- `STALE_PROPOSAL`
- `STALE_RESULT`
- `BUDGET_EXHAUSTED`
- `CANCELLED`

Existing enums/contracts must be inspected before implementation; these labels are not claimed as current API states.

## What would falsify or weaken the hypothesis

- server-originated PROTEUS re-trigger cannot be made reliable;
- tab/session identity cannot be fenced safely;
- provider auth/UI lifecycle requires frequent manual intervention;
- same-session continuity carries too much stale context compared with reconstruction;
- multi-session fan-out costs more than it improves results;
- cross-project isolation cannot be enforced.

If PROTEUS fails, ALETHEIA's Project Session Loop remains valid with another admitted SessionBackend. The backend is replaceable; project/campaign/evidence semantics are not.

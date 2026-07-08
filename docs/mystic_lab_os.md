# Mystic LAB: AI Research Lab OS

Mystic LAB is an AI Research Lab OS.

It is not a chatbot skin, not a game, and not a wet-lab control system. It is a research orchestration system where model agents use MCP tools to manage sessions, debate hypotheses, route work to deterministic engines, collect evidence, and produce reports.

## Core Definition

Mystic LAB = GPT/Claude/Gemini-like model agents that use MCP to solve mathematics, science, and engineering problems; call external engines for calculation and simulation; manipulate a 3D virtual lab state; verify results; and generate evidence-backed reports.

## What Mystic LAB Is Not

- It is not just answer generation in a chat window.
- It does not treat GPT-like models as numerical or simulation engines.
- It does not claim unsupported engine output.
- It does not require a local Mac backend in cloud-native mode.
- It does not currently implement home or IoT control.

## Layered Architecture

```text
User
→ ChatGPT / Claude / Gemini
→ Mystic LAB MCP Server
→ Lab Session System
→ Model Debate / Sub-agent System
→ Simulation Orchestrator
→ Engine Adapter Layer
→ 3D Virtual Lab Interface
→ Evidence / Report / Result Archive
```

## Responsibility Split

### 1. Chatbot answer generation

This is direct text generation. A model produces an answer, but there is no persistent lab state, no claim graph, no experiment registry, and no evidence archive.

Mystic LAB goes beyond this layer.

### 2. Research session orchestration

Mystic LAB persists a structured session with phases, turns, claims, experiments, failures, memory edges, notebook state, and reports. The session is the primary unit of work.

### 3. Model debate

Mystic LAB can route work across multiple roles or multiple providers. Debate is not the same thing as verification. Model disagreement is evidence for review, not proof.

### 4. Simulation engine execution

Simulation engines perform actual deterministic or numerical work. Model agents can request these tools, interpret outputs, and plan next steps, but they are not the engine.

### 5. 3D visualization

The 3D virtual lab is the scene/state layer for inspection and interaction. It visualizes objects, parameters, simulation attachments, and evidence references. It does not replace the simulation engine.

### 6. Evidence and report archive

Mystic LAB stores claims, failures, simulations, reports, and provenance so results can be reviewed, exported, and reused.

## Core Systems

### Mystic LAB MCP Server

Current state:

- Implemented in local Python mode and Cloudflare Worker cloud-native mode.
- Public ChatGPT remote MCP import is verified.
- Cloud-native Supabase mode keeps `import_ready=true`.

### Lab Session System

Current state:

- Implemented.
- Session lifecycle exists in both local JSON storage and Supabase-backed cloud mode.
- Current session objects include:
  - `LabSession`
  - `LabTurn`
  - `Claim`
  - `Experiment`
  - `Failure`
  - `MemoryEdge`
  - `LabReport`

Current phases:

1. Problem Intake
2. Background Scan
3. Hypothesis Generation
4. Experiment Design
5. Simulation / Execution
6. Referee Review
7. Failure Archive
8. Knowledge Update
9. Next Experiment Planning
10. Report Generation

### Model Debate / Sub-agent System

Current state:

- Implemented as a session role system locally.
- Implemented as a cloud-native tool surface with structured `provider_required` and `deferred` behavior.
- Provider registry exists for:
  - `openai_compatible`
  - `gemini`
  - `anthropic`
- Provider Connect foundation is implemented for:
  - provider listing and status inspection
  - safe Cloudflare secret setup instructions
  - verification and disconnect state
  - deferred callback tracking for future OAuth-capable providers
  - safe model listing and deferred provider call tests

Important limit:

- Real provider-backed debate or agent execution only works when provider credentials are explicitly configured and tested.
- Mystic LAB does not claim real Claude/Gemini/OpenAI debate works by default.

Sub-agent definition:

- a lab session can assign different reasoning roles such as Director, Theorist, ExperimentDesigner, Simulator, Referee, and PaperWriter
- each role produces turns inside the same session timeline
- turns can create claims, request tools, trigger experiments, or archive failures
- the LAB orchestrator, not the model alone, decides how these turns are persisted and related

Provider routing definition:

- provider routing chooses which explicitly connected model provider can execute a model-backed LAB action
- current cloud-native provider registry supports `openai_compatible`, `gemini`, and `anthropic`
- if no allowed provider is connected, the action returns `provider_required` instead of inventing output
- provider routing is different from engine routing; model providers generate/critique text, while engine adapters perform deterministic computation

### Simulation Orchestrator

Current state:

- Partially implemented as experiment/session orchestration.
- The orchestration layer exists, but the formal worker-native engine execution layer is still incomplete.
- Cloud-native `lab_experiment_run` is intentionally exposed but currently returns structured `deferred` results for heavy paths.

### Engine Adapter Layer

Current state:

- Implemented for Phase 1.
- Deterministic scene/simulation execution now exists for `physics.simple_projectile`, `physics.simple_collision`, and `scene.three_json`.
- `math.sympy` is exposed through a deterministic subset in both local mode and Cloudflare Worker mode for evaluate, simplify, substitution, and simple linear solve flows.

Important limit:

- The Cloudflare Worker does not ship arbitrary SymPy execution, so richer symbolic requests still return structured `engine_required` or `unsupported_expression`.

### 3D Virtual Lab Interface

Current state:

- Implemented for Phase 1.
- Public cloud-native mode and local mode now persist formal 3D scene state, objects, simulations, snapshots, and scene reports.

### Evidence / Report / Result Archive

Current state:

- Implemented.
- Session claims, experiments, failures, memory edges, notebook state, and report state persist locally or in Supabase.
- Cloud-native report generation is live.

## Lab Session System Definition

Mystic LAB sessions are structured research workflows with:

- a domain
- a goal
- a mode
- phase-aware turns
- conservative claim status rules
- linked experiments
- archived failures
- memory graph edges
- notebook and report outputs

Reality Anchor rules remain conservative:

- model-only claims default to `HEURISTIC`
- deterministic invalidation becomes `REFUTED` or `FAILED`
- simulation-backed support becomes `TESTED`, not `PROVED`
- incomplete proofs become `NEEDS_MORE_DETAIL`

## Current Implemented vs Planned Matrix

| Capability | Status | Notes |
| --- | --- | --- |
| Public MCP server | Implemented | Cloudflare Worker live |
| OAuth import readiness | Implemented | `import_ready=true` |
| Supabase cloud-native LAB storage | Implemented | No local backend required |
| Local JSON LAB storage | Implemented | Local mode preserved |
| `mystic_status`, `health_check` | Implemented | Live in cloud-native mode |
| Session create/get/report | Implemented | Live in cloud-native mode |
| Session advance | Implemented | Live; may block on provider/engine availability |
| Memory write/search | Implemented | Supabase-backed in cloud-native mode |
| Experiment create | Implemented | Supabase-backed |
| Agent run | Partial | Returns real provider output only when explicitly configured; otherwise `provider_required` or `deferred` |
| Model debate | Partial | Cloud-native tool surface exists; provider- and execution-dependent |
| Provider Connect foundation | Implemented | Safe provider metadata, status, verification, disconnect, and deferred callback flows are live |
| Referee review | Partial | Exposed; currently `deferred` in cloud-native mode |
| Experiment execution engines | Partial | Orchestration exists; formal engine adapter layer not complete |
| 3D scene API | Implemented | Scene CRUD, storage, snapshot export, and report generation live |
| Formal simulation orchestrator | Partial | Phase 1 adapters are live; broader execution remains phased |
| Formal engine adapters | Partial | `physics.simple_projectile`, `physics.simple_collision`, and `scene.three_json` are live; worker `math.sympy` returns `engine_required` |
| Full multi-domain research execution | Planned | Phased rollout |

## Supported Product Domains

Mystic LAB must support:

- Mathematics
- Physics
- Chemistry
- Biology
- Earth Science
- Astronomy / Space Science
- Computer Science
- Statistics / Data Science
- Engineering
- Medical Science
- Agricultural / Food Science
- Social Science
- Cognitive Science
- Materials Science
- Environmental / Climate Science
- AI for Science
- Interdisciplinary Research

The full domain map is the product target. The current runtime schemas still use a narrower short-term domain enum and do not yet expose the full taxonomy as executable support.

## Cloud-native Mode vs Local Mode

### Cloud-native mode

- Cloudflare Worker + Supabase
- no local Mac backend required
- no quick tunnel required
- the original 13 LAB tools remain exposed, plus the 10 new Phase 1 scene/simulation tools
- unsupported heavy/model-dependent paths return structured `deferred` or `provider_required`

### Local mode

- local Python backend
- local JSON storage by default
- richer existing local execution paths
- suitable for development and future heavier orchestration

## Product Principle

GPT/Claude/Gemini-like models are:

- research directors
- planners
- interpreters
- critics
- report writers

They are not the numerical engine.

Mystic LAB orchestrates:

- models
- tools
- storage
- engines
- evidence
- reports
- 3D scene state

## Next Step

The next product milestone is Phase 2 domain expansion:

- Chemistry
- Biology
- Statistics / Data Science

See:

- [mystic_lab_roadmap.md](/Users/JYH/Documents/Mystic/docs/mystic_lab_roadmap.md)
- [mystic_lab_engine_adapter_layer.md](/Users/JYH/Documents/Mystic/docs/mystic_lab_engine_adapter_layer.md)
- [mystic_lab_3d_virtual_lab.md](/Users/JYH/Documents/Mystic/docs/mystic_lab_3d_virtual_lab.md)
- [mystic_lab_domains.md](/Users/JYH/Documents/Mystic/docs/mystic_lab_domains.md)

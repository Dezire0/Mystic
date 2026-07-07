# Mystic LAB Roadmap

## Current Baseline

Mystic LAB already has:

- a live public MCP server
- Cloudflare Worker + Supabase cloud-native LAB mode
- `import_ready=true` for ChatGPT remote MCP import
- the original 13 LAB tools preserved in cloud-native mode, expanded by the 10 new Phase 1 scene/simulation tools
- structured `ready`, `deferred`, and `provider_required` behavior
- local mode preserved

What it does not yet have:

- broad domain-specific engine adapters beyond the initial Phase 1 surface
- a full Worker-native symbolic math runtime
- a broader formal simulation orchestrator layer beyond the initial scene/simulation paths
- broad multi-domain execution beyond the current LAB orchestration foundation

## MVP Phase Plan

### Phase 1

Status:

- Implemented for Issue #75 with explicit limits on cloud-native `math.sympy`

Focus:

- Mathematics
- Simple Physics
- 3D Scene API

Primary goals:

- add scene lifecycle MCP tools
- add deterministic math and simple physics adapters
- attach simulation outputs to scene state
- keep cloud-native Worker mode import-ready and stable

Initial engine adapters:

- `math.sympy`
- `physics.simple_projectile`
- `physics.simple_collision`
- `scene.three_json`

### Phase 2

Focus:

- Chemistry
- Biology
- Statistics / Data Science

Primary goals:

- domain-specific experiment templates
- structured scientific parameter handling
- richer evidence linking between claims, simulations, and reports

### Phase 3

Focus:

- Engineering
- Earth Science
- Astronomy / Space Science

Primary goals:

- broader simulation classes
- scenario composition
- scene-linked multi-step workflows

### Phase 4

Focus:

- Medical Science
- Social Science
- Cognitive Science
- AI for Science

Primary goals:

- domain-specific constraints
- higher-risk review gates
- stronger evidence and provenance requirements

## Feature Matrix

| Area | Current State | Phase 1 | Later |
| --- | --- | --- | --- |
| MCP transport | Implemented | keep stable | extend |
| OAuth import | Implemented | keep stable | extend |
| Supabase LAB storage | Implemented | extend schema for scenes/simulations | scale |
| Session orchestration | Implemented | connect to scenes/simulations | deepen |
| Provider registry | Implemented | keep explicit auth gating | add providers |
| Multi-model routing | Partial | connect to scene/simulation workflows | deepen |
| Deterministic verifier | Implemented | reuse as evidence tool | deepen |
| Engine adapters | Partial | math + simple physics | broader science stack |
| 3D scene state | Implemented | API + schema delivered in Phase 1 | richer UI |
| Report archive | Implemented | scene/simulation references added in Phase 1 | richer publishing |

## Current Implemented Features

### Implemented now

- cloud-native `mystic_status`
- cloud-native `health_check`
- cloud-native `lab_session_create`
- cloud-native `lab_session_get`
- cloud-native `lab_session_advance`
- cloud-native `lab_agent_run`
- cloud-native `lab_referee_review`
- cloud-native `lab_experiment_create`
- cloud-native `lab_experiment_run`
- cloud-native `lab_memory_search`
- cloud-native `lab_memory_write`
- cloud-native `lab_models_debate`
- cloud-native `lab_report_generate`
- cloud-native `create_lab_scene`
- cloud-native `get_lab_scene`
- cloud-native `add_lab_object`
- cloud-native `update_lab_object`
- cloud-native `remove_lab_object`
- cloud-native `set_lab_parameters`
- cloud-native `run_lab_simulation`
- cloud-native `attach_simulation_to_scene`
- cloud-native `export_lab_snapshot`
- cloud-native `generate_lab_report`

### Implemented with limits

- `lab_agent_run`: real external provider output only when explicitly configured
- `lab_models_debate`: real external provider output only when explicitly configured
- `lab_referee_review`: deferred in cloud-native mode
- `lab_experiment_run`: deferred for real cloud-native heavy execution
- `math.sympy`: deterministic local/native subset is live; public Worker returns structured `engine_required`

### Delivered in Phase 1

- scene lifecycle MCP tools
- local JSON and Supabase-backed scene/simulation persistence
- deterministic `physics.simple_projectile`
- deterministic `physics.simple_collision`
- `scene.three_json` export
- scene-linked snapshot/report/archive state

## Engineering Milestone

Next milestone issue:

- [Issue #75](https://github.com/Dezire0/Mystic/issues/75): `Mystic LAB OS Phase 1: Math + Simple Physics + 3D Scene API`

## Guardrails

- do not break the existing 13 LAB tools
- do not break `import_ready=true`
- do not require a local backend in cloud-native mode
- do not fake simulation output
- return structured `deferred` or `engine_required` when an execution path is unavailable

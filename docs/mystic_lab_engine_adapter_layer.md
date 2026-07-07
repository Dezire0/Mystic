# Mystic LAB Engine Adapter Layer

## Purpose

The engine adapter layer is where Mystic LAB hands work off to deterministic or numerical execution systems.

This layer exists because GPT-like models are not the simulation engine.

Models in Mystic LAB are responsible for:

- planning
- decomposition
- critique
- interpretation
- report writing

Engine adapters are responsible for:

- actual computation
- normalized structured output
- evidence payloads
- failure signaling

## Current State

Current implemented building blocks:

- local deterministic verifier integration
- local experiment methods such as `python_bruteforce` and `symbolic`
- cloud-native experiment orchestration and persistence
- structured `deferred` and `provider_required` responses in cloud-native Worker mode
- Phase 1 scene/simulation storage and execution for public Worker mode and local mode

Current limitation:
- the public Worker only exposes a restricted cloud-native `math.sympy` subset, not arbitrary SymPy execution.

## Target Adapter Contract

Each engine adapter should define:

- `adapter_id`
- `domain`
- `capabilities`
- `input_schema`
- `output_schema`
- `evidence_schema`
- `timeout_policy`
- `availability_check`
- `execution_mode`

Execution results should normalize to:

- `status`
- `adapter_id`
- `inputs`
- `outputs`
- `evidence`
- `warnings`
- `errors`
- `latency_ms`

## Simulation Orchestrator Responsibilities

The Simulation Orchestrator should:

- receive a simulation request from a LAB tool or experiment
- validate the request against an adapter
- route the request to the correct engine adapter
- store structured inputs and outputs
- attach results to claims, experiments, failures, reports, and scenes
- return `deferred` or `engine_required` when execution is unavailable

## Initial Phase 1 Adapters

### `math.sympy`

Status: Implemented with limits

Purpose:

- symbolic manipulation
- algebraic solving
- simplification
- deterministic math checks

Current behavior:

- local mode exposes a deterministic subset for arithmetic evaluation, numeric substitution, simple simplification, and simple linear solving
- cloud-native Worker mode exposes the same restricted subset without using Python or arbitrary code execution
- unsupported expressions return structured `unsupported_expression`
- richer symbolic requests still return structured `engine_required`

### `physics.simple_projectile`

Status: Implemented

Purpose:

- basic projectile motion
- deterministic time/position/velocity outputs
- parameterized gravity and initial velocity inputs

### `physics.simple_collision`

Status: Implemented

Purpose:

- simple collision scenarios
- elastic/inelastic outcomes
- structured momentum/velocity results

### `scene.three_json`

Status: Implemented

Purpose:

- export a scene into a Three.js-compatible JSON form
- allow future UI rendering without claiming a 3D renderer already exists in the Worker

## Model Providers vs Engine Adapters

These are different layers.

### Provider routing

Provider routing is for model generation:

- `openai_compatible`
- `gemini`
- `anthropic`

Current Provider Connect foundation tools:

- `provider_list`
- `provider_status`
- `provider_connect_start`
- `provider_connect_callback_status`
- `provider_configure_secret_instructions`
- `provider_verify`
- `provider_disconnect`
- `provider_model_list`
- `provider_call_test`

These require explicit credentials and are used for planning, debate, critique, and interpretation.
The foundation layer stores only status and metadata in Supabase. Real provider secrets stay in Cloudflare secrets or other approved server-side secret storage.

### Engine adapters

Engine adapters are for deterministic or numerical execution:

- symbolic math
- simple physics
- future chemistry/biology/data science/engineering engines

Provider connectivity does not replace the engine adapter layer.

## Failure Semantics

### `provider_required`

Use when a model-backed action was requested but the required provider is not explicitly connected.

### `engine_required`

Use when the requested simulation path depends on an engine that is not available or not configured.

### `unsupported_expression`

Use when the requested expression is outside the restricted grammar or symbolic capabilities of the safe cloud-native subset.

### `deferred`

Use when the tool is intentionally exposed but the worker-native execution path is not implemented yet.

### `error`

Use when execution was attempted and failed with a real runtime or adapter error.

## Storage Direction

Simulation requests and results should be stored in a way that can be referenced by:

- lab sessions
- claims
- experiments
- failures
- scene state
- reports

Cloud-native mode should use Supabase-backed persistence without requiring a local backend.

## Current vs Planned Matrix

| Layer | Current State | Notes |
| --- | --- | --- |
| Experiment orchestration | Implemented | Session and experiment state exists |
| Structured deferred responses | Implemented | Cloud-native mode does not crash on unsupported heavy paths |
| Formal engine adapter registry | Partial | Phase 1 execution surface exists; broader registry work remains |
| `math.sympy` adapter | Partial | Deterministic subset is live in local mode and Worker mode; unsupported symbolic forms stay structured |
| `physics.simple_projectile` adapter | Implemented | Deterministic Phase 1 execution is live |
| `physics.simple_collision` adapter | Implemented | Deterministic Phase 1 execution is live |
| `scene.three_json` exporter | Implemented | Three.js-friendly JSON export is live |

## Guardrail

Mystic LAB must not fake simulation output.

If no engine is available, the system must return a structured non-success execution state instead of inventing results.

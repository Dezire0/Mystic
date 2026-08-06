# ScientificModelSpec

`ScientificModelSpec` is Mystic LAB's versioned, renderer-independent contract for a scientific model. Phase 2B.2 uses it as validated provenance attached to Math Engine Pack jobs; it does not execute a model specification directly.

## Required identity

- `schema_version`
- `model_id`
- `title`
- `domain`
- `model_family`

## Declarative fields

- `state_variables`, `parameters`, and `governing_equations`
- `initial_conditions` and `boundary_conditions`
- `assumptions`, `units`, and `observables`
- `solver_requirements`, `calibration_targets`, and `validity_limits`
- `uncertainty_model`, `safety_classification`, and `provenance`
- `linked_claim_ids` and `linked_experiment_ids`

Governing equations are bounded symbolic objects with an allowlisted `kind`: `polynomial`, `linear`, `ode`, `algebraic`, or `conservation`. The contract intentionally rejects executable fields and arbitrary expression strings. It never accepts Python, JavaScript, shell, import, package, URL, or callback data.

## Versioning and provenance

The specification is validated at job submission, retained in safe run evidence, and contributes to the runner's canonical input/output hash record. A result is computed evidence, not a claim of scientific verification. Future model-construction and campaign work must create a new schema version rather than silently reinterpret an existing field.

## Limits in this pack

The Phase 2B.2 Math Engine Pack supports declarative mathematical model families only. Unit dimensions are published and carried as metadata, but dimensional algebra and cross-domain model construction are reserved for later engine packs.

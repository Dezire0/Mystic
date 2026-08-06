# Math Solver SDK

The Math Solver SDK is `mystic.lab.math`. It is a standard-library, trusted-runner package shared by every Phase 2B.2 math engine.

## Core types

- `ScientificModelSpec` and `MathematicalProblem` define validated declarative inputs.
- `Tolerance`, `Units`, `Constraint`, `Variable`, `Parameter`, and `ObjectiveFunction` define solver controls.
- `SolverCapabilities` and `SolverMetadata` publish deterministic behavior, complexity, resource class, limitations, and optional uncertainty/sensitivity support.
- `SolverResult` contains values, convergence, error estimate, warnings, optional sensitivity/uncertainty, and a renderer-independent `VisualizationDescriptor`.

## Solver contract

Every solver is an allowlisted `ScientificEnginePlugin` with a versioned `EngineManifest`. It validates input before execution and returns numerical tolerances, assumptions, convergence status, reproducibility metadata, canonical hashes (from the runner), and visualization descriptors. The Worker creates jobs and reads evidence only; Python code runs in a compatible trusted runner.

## Security contract

The SDK has no dynamic imports, `eval`, `exec`, subprocesses, shell calls, package installation, filesystem inputs, or network access. Function, ODE, and objective inputs are fixed declarative families. Unsupported operations return a structured safe validation error rather than attempting interpretation.

## Descriptor contract

Descriptors are version `1` layers, not Three.js. Supported types include `function_curve`, `convergence_curve`, `matrix_heatmap`, `histogram`, `scatter_plot`, `phase_diagram`, `vector_field`, `confidence_interval`, and `error_curve`. Renderers may consume these descriptors later without changing solver output.

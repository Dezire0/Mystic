# Mystic Autonomous Scientist v1 architecture

## Purpose and baseline

This is the scientific-platform plan for [Phase 2B epic #111](https://github.com/Dezire0/Mystic/issues/111). It starts from immutable `phase-2a-production` commit `05648b2a8f6fa6c314c531c796c95a0aeb4a3349`: 45 MCP tools, seven deterministic engines, persistent LAB resources, production Worker and Control Center, and `import_ready=true`.

Autonomous Scientist v1 is a bounded workflow for mathematics, computation, simulation, synthetic experiments, and safe supplied-dataset analysis. ChatGPT remains the primary controller; Mystic owns durable campaign state, trusted execution, evidence, and safe resume behavior.

Computer control, file/application automation, Home Assistant, IoT, OIDC, DCR, CIMD, and cluster-scale GPU infrastructure remain later roadmap work. This plan adds no runtime code, migration, scheduler, engine, UI route, or deployment.

## Architecture

```text
ChatGPT Controller / Control Center
                |
                v
      Mystic MCP Worker and campaign API
                |
     +----------+-----------+----------------+
     |                      |                |
     v                      v                v
Campaign state        Model registry     Experiment manager
     |                      |                |
     +----------+-----------+----------------+
                |
                v
     Engine matching and runner scheduler
                |
                v
     Trusted engine jobs, runs, artifacts
                |
                v
Evidence grading, hostile referee, report
```

The Worker is authoritative for campaign transitions, budgets, safety gates, job creation, and persistence. Models and equations are declarative data. Runners execute only allowlisted engine jobs; they never execute campaign instructions, model strings, user commands, packages, or arbitrary programs.

## Milestone order

| Milestone | Objective |
| --- | --- |
| [2B.1 #112](https://github.com/Dezire0/Mystic/issues/112) | Resilient runner fleet: macOS compatibility, Linux CPU runner, scheduling, leases, recovery, dead letters, fleet UI. |
| [2B.2 #114](https://github.com/Dezire0/Mystic/issues/114) | Scientific engine expansion and `ScientificModelSpec`. |
| [2B.3 #115](https://github.com/Dezire0/Mystic/issues/115) | Resumable autonomous research orchestration. |
| [2B.4 #116](https://github.com/Dezire0/Mystic/issues/116) | Model construction, fitting, uncertainty, and selection. |
| [2B.5 #117](https://github.com/Dezire0/Mystic/issues/117) | Safe experiment campaign management. |
| [2B.6 #118](https://github.com/Dezire0/Mystic/issues/118) | Reproducibility, adversarial referee, evidence grading, reports. |
| [2B.7 #119](https://github.com/Dezire0/Mystic/issues/119) | Autonomous Scientist v1 production acceptance. |

All behavior is additive and feature-flagged until accepted. Phase 2A MCP, OAuth PKCE, Control Center, scenes, result attachments, reports, runner, and readiness remain compatible.

## Engine expansion

Each pack is independently versioned and accepted. An unavailable engine or dependency returns structured unavailable/deferred output, never a fabricated result.

| Pack | Candidate engines |
| --- | --- |
| Mathematics and numerical analysis | `math.root_finding`, `math.numerical_integration`, `math.ode_solver`, `math.optimization`, `math.linear_algebra`, `math.statistics`, `math.parameter_fit`, `math.monte_carlo`, `math.constraint_solver`, `math.symbolic_verification` |
| Physics | `physics.rigid_body`, `physics.orbital_mechanics`, `physics.harmonic_oscillator`, `physics.electrostatics`, `physics.magnetostatics`, `physics.wave_equation`, `physics.geometric_optics`, `physics.thermodynamics`, `physics.heat_transfer`, `physics.fluid_lumped` |
| Chemistry | `chemistry.equilibrium`, `chemistry.acid_base`, `chemistry.thermodynamics`, `chemistry.speciation`, `chemistry.reaction_network`, `chemistry.diffusion_reaction`, `chemistry.parameter_fit` |
| Biology | `biology.logistic_growth`, `biology.predator_prey`, `biology.epidemiology`, `biology.enzyme_kinetics`, `biology.gene_regulatory_network`, `biology.ecosystem`, `biology.selection_dynamics`, `biology.compartment_model` |
| Engineering | `engineering.ac_circuit`, `engineering.control_system`, `engineering.signal_processing`, `engineering.mechanical_system`, `engineering.thermal_system`, `engineering.structural_beam`, `engineering.power_network`, `engineering.sensor_fusion` |
| Model and data analysis | `model.linear_regression`, `model.nonlinear_regression`, `model.bayesian_fit`, `model.model_selection`, `model.sensitivity_analysis`, `model.uncertainty_propagation`, `model.cross_validation`, `model.residual_analysis`, `model.experimental_design` |

Every pack requires bounded schemas, units and validity limits, deterministic or explicitly seeded fixtures where possible, result hashes, versioned provenance, tests, and documented safe failure behavior.

## `ScientificModelSpec`

`ScientificModelSpec` is a typed, versioned, renderer-independent contract:

```text
ScientificModelSpec {
  schema_version, model_id, title, domain, model_family,
  state_variables, parameters, governing_equations,
  initial_conditions, boundary_conditions, assumptions, units,
  observables, solver_requirements, calibration_targets,
  validity_limits, uncertainty_model, safety_classification,
  provenance, linked_claim_ids, linked_experiment_ids
}
```

All fields are declarative. `governing_equations` is a bounded validated symbolic AST with a fixed operator/function vocabulary, typed variables, unit annotations, and maximum depth/node count. It is not an expression evaluator.

The contract rejects arbitrary Python, JavaScript, shell commands, `eval`, `exec`, dynamic packages/imports, executable expression strings, fetchable URLs, and renderer-specific code. Renderers consume validated values only and cannot mutate or execute the specification.

## `ResearchCampaign` state machine

```text
ResearchCampaign {
  campaign_id, session_id, original_problem, research_goal, domain,
  status, current_phase, iteration, maximum_iterations,
  execution_budget, time_budget, active_claim_ids, candidate_model_ids,
  selected_model_id, experiment_queue, completed_experiments,
  failed_experiments, uncertainty_state, evidence_score, referee_state,
  stop_reason, created_at, updated_at
}
```

Permitted statuses are `planned`, `gathering_evidence`, `generating_hypotheses`, `building_models`, `designing_experiments`, `running_experiments`, `analysing_results`, `calibrating_models`, `referee_review`, `planning_next_iteration`, `paused`, `completed`, `inconclusive`, `failed`, `cancelled`, and `requires_human_review`.

Transitions use versioned compare-and-set mutations and idempotency keys. A completed child action is linked, not repeated, after resume. Transition history stores visible reason, actor/controller, budget delta, policy version, and resource references, never hidden reasoning.

## Autonomous loop

Each bounded iteration:

1. receives the problem and resolves the domain;
2. retrieves knowledge, evidence, and failure memory;
3. identifies uncertainty and validity boundaries;
4. generates hypotheses linked to claims;
5. generates models from trusted families;
6. designs discriminating experiments;
7. matches experiments to trusted engines;
8. validates resources, data, safety, and budget;
9. executes eligible jobs through the runner fleet;
10. validates schemas, hashes, units, warnings, and convergence;
11. calibrates candidate models;
12. compares models and records rationale/limits;
13. requests hostile referee review;
14. archives scientific or infrastructure failures;
15. selects a justified next experiment or requests approval;
16. evaluates stopping criteria before another iteration; and
17. produces an incremental or final evidence-linked report.

Safe independent experiments may run in parallel, but prerequisites and state decisions remain deterministic. Campaign work is server-side and resumable; ChatGPT can inspect, pause, resume, cancel, approve/reject experiments, request referee review, and request reports.

## Budgets and stopping

Every iteration consumes an explicit budget unit. Stop when target confidence is reached, a hypothesis is falsified, models are sufficiently distinguished, expected information gain is low, execution/time/iteration budget is exhausted, equivalent failure repeats, required engine/data is unavailable, model limits are exceeded, a safety boundary is reached, or human judgement is required.

The terminal record carries exact `stop_reason`, evidence state, unresolved uncertainty, and next safe action. `inconclusive` is a valid outcome.

## Calibration, selection, and experiments

Models come from trusted families and are validated for dimensions, units, assumptions, data requirements, and validity limits before fitting. The platform estimates parameters, calculates residuals, propagates uncertainty, evaluates sensitivity and complexity, detects overfitting, compares candidates, and archives rejected models.

Applicable visible metrics include RMSE, MAE, R-squared, likelihood, AIC, BIC, cross-validation score, posterior predictive checks, uncertainty intervals, and conservation-law residuals. Applicability, data splits, solver settings, seeds, and warnings remain evidence. No metric proves scientific truth.

Experiments link claims/models to inputs, expected outputs, assumptions, prerequisites, safety class, cost, budget impact, and expected information gain. The manager ranks safe eligible work, preserves dependencies, parallelizes only independent work, cancels obsolete queued work, retries only infrastructure failures within policy, and requests approval when required.

Initial experiment types are mathematical proof/search, numerical computation, simulation, parameter fitting, synthetic-data work, and safe supplied-dataset analysis. Hazardous physical, chemical, biological, medical, device, or real-world experimentation stops at simulation, risk analysis, or human review.

## Failure, referee, and reporting

Failure categories are `invalid_input`, `data_unavailable`, `engine_unavailable`, `resource_unavailable`, `infrastructure_failure`, `lease_expired`, `timeout`, `non_convergence`, `numerical_instability`, `model_limit_reached`, `hypothesis_falsified`, `insufficient_evidence`, `safety_boundary`, and `requires_human_review`.

The hostile referee returns `verified`, `provisionally_supported`, `disputed`, `falsified`, `invalid_input`, `model_limit_reached`, `insufficient_evidence`, `requires_additional_experiment`, `infrastructure_failure`, or `requires_human_review`.

Checks cover input/output hashes, engine/runtime versions, units, assumptions, warnings, solver tolerances, random seeds where supported, convergence, analytical comparison, independent rerun, cross-engine comparison where possible, invariants/conservation, validity limits, and provenance. Persist only visible evidence, verdict, rationale, limitations, and requested follow-up, never hidden chain-of-thought.

## Persistence and Control Center

No migration is created here. Future additive records include campaign state/transition/budget history, scientific models, calibration/comparison results, experiment plans/dependencies, evidence grades, and audit events. They reference existing sessions, claims, experiments, scenes, engine jobs/runs, artifacts, referee reviews, reports, failure memory, and activity events. Foreign keys, revisions, idempotency keys, and indexes prevent duplicate work.

Future routes are `/campaigns`, `/campaigns/:campaignId`, `/models`, `/models/:modelId`, `/experiments`, and `/evidence`. They show problem, goal, phase, iteration, budget, hypotheses, models, experiments, failures, uncertainty, referee state, stop reason, and next action. Actions are start, pause, resume, cancel, approve/reject experiment, request review, and generate report through the authenticated BFF, CSRF checks, validation, confirmation where required, and audit logging. No credentials, host details, private topology, or hidden reasoning are displayed.

## Safety boundary

Autonomous Scientist v1 is limited to mathematics, computation, simulation, synthetic experiments, bounded scientific models, and safe supplied-dataset analysis. It must not autonomously execute hazardous chemical procedures, biological culturing or modification, medical treatment decisions, high-energy experiments, weapons-related work, environmental release, uncontrolled hardware operation, or security-sensitive device control. Such work stops at simulation, risk analysis, or `requires_human_review`.

## Test, deployment, rollback, and acceptance

Tests cover ModelSpec AST/unit/version/malicious input rejection; engine-pack fixtures and hash/version evidence; campaign transitions, budgets, idempotency and resume; fitting and overfit cases; experiment dependency/parallelism/retry; referee verdict/redaction; authenticated Control Center; Phase 2A regression; MCP smoke; readiness; and runner failover.

Deploy additively behind feature flags: read-only contracts and views, engine packs, shadow/paused campaigns, model/experiment proposals, referee evidence, then one bounded synthetic production campaign type at a time. Every stage requires tests, smoke, readiness, audit, and rollback rehearsal.

Rollback disables the feature, pauses campaigns, drains unsafe queued work, preserves immutable evidence, and leaves Phase 2A execution available. Additive schema is not destructively reverted and completed jobs are never rerun merely to roll back.

Production acceptance covers physics motion selection, population dynamics, safe synthetic reaction kinetics, and mathematical conjecture/counterexample work. Each completes at least two autonomous iterations, preserves hashes/evidence, justifies next experiments, supports interruption/resume, and may conclude `inconclusive` without fabricating a verified conclusion.

## Open decisions

- Exact ModelSpec AST vocabulary, unit system, and safe function set.
- Engine-pack order and which engines require future GPU capacity.
- Evidence-score/confidence semantics by domain.
- Information-gain estimator, cost model, and approval policy for parallelism.
- Model-family registry governance and supplied-data retention policy.
- Boundary between deterministic referee checks and optional configured provider assistance.

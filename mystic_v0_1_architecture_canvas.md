# Mystic v0.1 — Full Multi-Specialist Model Architecture Canvas

## 0. Project Name

**Mystic**

---

## 1. Core Requirement

Mystic must not be implemented as one generic chatbot pretending to play many roles.

Mystic must be implemented as a multi-specialist AI research intelligence where each domain agent is treated as a separate model role with its own prompt, interface, output protocol, archive records, and future LoRA/QLoRA adapter path.

Even if v0.1 uses the same underlying model provider for multiple agents, the system architecture must treat them as separate specialist models.

---

## 2. Main Architecture

Mystic is divided into the following divisions:

```text
Mystic-Core
│
├── Pure Math Division
│   ├── Mystic-Prime
│   ├── Mystic-Algebra
│   ├── Mystic-Geo
│   ├── Mystic-Analysis
│   ├── Mystic-Probability
│   └── Mystic-Logic
│
├── Science Division
│   ├── Mystic-Physics
│   ├── Mystic-Complexity
│   ├── Mystic-BioMath
│   └── Mystic-Chem
│
├── Verification Division
│   ├── Mystic-Lean
│   ├── Mystic-SMT
│   └── Mystic-Raven
│
├── Discovery Division
│   ├── Mystic-Forge
│   ├── Mystic-Conjecture
│   ├── Mystic-Pattern
│   └── Mystic-Simulator
│
├── Memory Division
│   ├── Mystic-Archive
│   ├── Mystic-KnowledgeGraph
│   └── Mystic-Evolution
│
└── Report Division
    └── Mystic-Report
```

---

## 3. Implementation Rule

Do not hard-code a single model for all agents.

Every agent must load its model settings from a config file.

Create:

```text
configs/model_config.yaml
```

Example:

```yaml
default_provider: ollama
agents:
  core:
    provider: ollama
    model: qwen3-14b
    temperature: 0.2
  prime:
    provider: ollama
    model: deepseek-r1-distill-14b
    adapter: prime_lora_v0
    temperature: 0.15
  algebra:
    provider: ollama
    model: qwen3-14b
    adapter: algebra_lora_v0
    temperature: 0.15
  geo:
    provider: ollama
    model: qwen3-14b
    adapter: geo_lora_v0
    temperature: 0.15
  analysis:
    provider: ollama
    model: qwen3-14b
    adapter: analysis_lora_v0
    temperature: 0.15
  probability:
    provider: ollama
    model: qwen3-14b
    adapter: probability_lora_v0
    temperature: 0.15
  logic:
    provider: ollama
    model: qwen3-14b
    adapter: logic_lora_v0
    temperature: 0.1
  physics:
    provider: ollama
    model: qwen3-14b
    adapter: physics_lora_v0
    temperature: 0.2
  complexity:
    provider: ollama
    model: qwen3-14b
    adapter: complexity_lora_v0
    temperature: 0.15
  biomath:
    provider: ollama
    model: qwen3-14b
    adapter: biomath_lora_v0
    temperature: 0.2
  chem:
    provider: ollama
    model: qwen3-14b
    adapter: chem_lora_v0
    temperature: 0.2
  forge:
    provider: ollama
    model: qwen3-coder
    adapter: forge_lora_v0
    temperature: 0.1
  conjecture:
    provider: ollama
    model: qwen3-14b
    adapter: conjecture_lora_v0
    temperature: 0.35
  pattern:
    provider: ollama
    model: qwen3-14b
    adapter: pattern_lora_v0
    temperature: 0.25
  simulator:
    provider: ollama
    model: qwen3-coder
    adapter: simulator_lora_v0
    temperature: 0.1
  lean:
    provider: ollama
    model: qwen3-14b
    adapter: lean_lora_v0
    temperature: 0.05
  smt:
    provider: local_tool
    model: z3
  raven:
    provider: ollama
    model: qwen3-14b
    adapter: raven_lora_v0
    temperature: 0.05
  archive:
    provider: local
    model: database
  knowledge_graph:
    provider: local
    model: graph_db
  evolution:
    provider: local
    model: dataset_builder
  report:
    provider: ollama
    model: qwen3-14b
    temperature: 0.2
```

The config must support future switching to:

- OpenAI-compatible API
- Ollama
- vLLM
- SGLang
- local mock provider
- future LoRA adapters

---

## 4. Required File Structure

Create this full structure.

```text
mystic/
├── README.md
├── pyproject.toml
├── .env.example
├── configs/
│   ├── model_config.yaml
│   └── router_config.yaml
│
├── mystic/
│   ├── __init__.py
│
│   ├── app/
│   │   ├── main.py
│   │   └── api.py
│
│   ├── cli/
│   │   ├── __init__.py
│   │   └── main.py
│
│   ├── core/
│   │   ├── orchestrator.py
│   │   ├── router.py
│   │   ├── protocol.py
│   │   ├── report.py
│   │   ├── session.py
│   │   └── model_registry.py
│
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   │
│   │   ├── core_agent.py
│   │   │
│   │   ├── pure_math/
│   │   │   ├── __init__.py
│   │   │   ├── prime_agent.py
│   │   │   ├── algebra_agent.py
│   │   │   ├── geo_agent.py
│   │   │   ├── analysis_agent.py
│   │   │   ├── probability_agent.py
│   │   │   └── logic_agent.py
│   │   │
│   │   ├── science/
│   │   │   ├── __init__.py
│   │   │   ├── physics_agent.py
│   │   │   ├── complexity_agent.py
│   │   │   ├── biomath_agent.py
│   │   │   └── chem_agent.py
│   │   │
│   │   ├── verification/
│   │   │   ├── __init__.py
│   │   │   ├── lean_agent.py
│   │   │   ├── smt_agent.py
│   │   │   └── raven_agent.py
│   │   │
│   │   ├── discovery/
│   │   │   ├── __init__.py
│   │   │   ├── forge_agent.py
│   │   │   ├── conjecture_agent.py
│   │   │   ├── pattern_agent.py
│   │   │   └── simulator_agent.py
│   │   │
│   │   ├── memory/
│   │   │   ├── __init__.py
│   │   │   ├── archive_agent.py
│   │   │   ├── knowledge_graph_agent.py
│   │   │   └── evolution_agent.py
│   │   │
│   │   └── report_agent.py
│
│   ├── models/
│   │   ├── __init__.py
│   │   ├── provider.py
│   │   ├── openai_compatible.py
│   │   ├── ollama_provider.py
│   │   ├── vllm_provider.py
│   │   ├── mock_provider.py
│   │   └── local_tool_provider.py
│
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── python_runner.py
│   │   ├── sympy_runner.py
│   │   ├── lean_runner.py
│   │   ├── smt_runner.py
│   │   ├── simulator_runner.py
│   │   └── sandbox.py
│
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── db.py
│   │   ├── schema.py
│   │   ├── archive.py
│   │   ├── knowledge_graph.py
│   │   └── dataset_export.py
│
│   ├── prompts/
│   │   ├── core.md
│   │   │
│   │   ├── pure_math/
│   │   │   ├── prime.md
│   │   │   ├── algebra.md
│   │   │   ├── geo.md
│   │   │   ├── analysis.md
│   │   │   ├── probability.md
│   │   │   └── logic.md
│   │   │
│   │   ├── science/
│   │   │   ├── physics.md
│   │   │   ├── complexity.md
│   │   │   ├── biomath.md
│   │   │   └── chem.md
│   │   │
│   │   ├── verification/
│   │   │   ├── lean.md
│   │   │   ├── smt.md
│   │   │   └── raven.md
│   │   │
│   │   ├── discovery/
│   │   │   ├── forge.md
│   │   │   ├── conjecture.md
│   │   │   ├── pattern.md
│   │   │   └── simulator.md
│   │   │
│   │   ├── memory/
│   │   │   ├── archive.md
│   │   │   ├── knowledge_graph.md
│   │   │   └── evolution.md
│   │   │
│   │   └── report.md
│
│   └── evals/
│       ├── __init__.py
│       ├── fake_proof_eval.py
│       ├── router_eval.py
│       ├── tool_eval.py
│       └── sample_cases.py
│
├── data/
│   ├── sessions/
│   ├── datasets/
│   ├── exports/
│   ├── experiments/
│   └── lean_attempts/
│
├── tests/
│   ├── test_protocol.py
│   ├── test_router.py
│   ├── test_model_registry.py
│   ├── test_python_runner.py
│   ├── test_archive.py
│   └── test_agents.py
│
└── scripts/
    ├── run_local.sh
    ├── export_dataset.py
    ├── seed_examples.py
    └── train_lora_placeholder.py
```

---

## 5. Agent Model Division

### 5.1 Mystic-Core

#### Role

Central orchestrator.

#### Responsibilities

- restate the problem;
- classify domains;
- select agents;
- create research plan;
- merge results;
- decide next steps;
- never directly declare final proof validity.

#### Output

```text
PROBLEM_RESTATEMENT:
FORMAL_STATEMENT:
DOMAIN_CLASSIFICATION:
SUBPROBLEMS:
AGENTS_TO_CALL:
INITIAL_STRATEGY:
RISK_FACTORS:
SUCCESS_CRITERIA:
```

---

## 6. Pure Math Division

### 6.1 Mystic-Prime

#### Domain

Number theory and discrete arithmetic.

#### Handles

- divisibility;
- modular arithmetic;
- prime numbers;
- Diophantine equations;
- Egyptian fractions;
- p-adic reasoning;
- integer parameterization.

#### Must check

- integrality;
- positivity;
- denominator-zero conditions;
- reversibility of transformations;
- full residue-class coverage;
- unjustified existence claims.

---

### 6.2 Mystic-Algebra

#### Domain

Algebraic structures.

#### Handles

- groups;
- rings;
- fields;
- modules;
- representation theory;
- category-style abstraction;
- algebraic invariants.

#### Must check

- whether introduced structures are actually defined;
- whether homomorphisms preserve the needed property;
- whether claimed invariants are truly invariant;
- whether abstraction does real mathematical work.

---

### 6.3 Mystic-Geo

#### Domain

Geometry, topology, and algebraic geometry.

#### Handles

- geometric reformulation;
- solution spaces;
- manifolds;
- curves;
- varieties;
- dimension arguments;
- topological obstructions.

#### Must check

- whether geometric translation is equivalent;
- whether singular cases are ignored;
- whether dimension arguments prove existence or only suggest it;
- whether topology is being used rigorously.

---

### 6.4 Mystic-Analysis

#### Domain

Analysis and PDE.

#### Handles

- limits;
- convergence;
- compactness;
- regularity;
- energy estimates;
- functional analysis;
- PDE behavior.

#### Must check

- existence and uniqueness assumptions;
- boundary conditions;
- regularity assumptions;
- convergence type;
- whether formal manipulations are justified.

---

### 6.5 Mystic-Probability

#### Domain

Probability, stochastic processes, random structures.

#### Handles

- probabilistic method;
- random graphs;
- concentration inequalities;
- Markov processes;
- average-case vs worst-case reasoning.

#### Must check

- whether high probability is incorrectly treated as certainty;
- whether independence is assumed without proof;
- whether expectation arguments prove existence;
- whether asymptotic claims cover finite cases.

---

### 6.6 Mystic-Logic

#### Domain

Mathematical logic and foundations.

#### Handles

- formal systems;
- computability;
- model theory;
- set-theoretic assumptions;
- independence possibility;
- proof-theoretic strength.

#### Must check

- whether the statement depends on axioms;
- whether definitions are first-order/formalizable;
- whether a problem may be undecidable in a given system;
- whether proof claims exceed the formal system.

---

## 7. Science Division

### 7.1 Mystic-Physics

#### Domain

Theoretical and mathematical physics.

#### Handles

- symmetry;
- conservation laws;
- field-theoretic intuition;
- energy principles;
- dimensional analysis;
- quantum/classical analogy.

#### Must check

- whether physical analogy is only heuristic;
- whether conservation law is mathematically defined;
- whether units and dimensions are consistent;
- whether physical intuition is being mistaken for proof.

---

### 7.2 Mystic-Complexity

#### Domain

Algorithms and computational complexity.

#### Handles

- reductions;
- complexity classes;
- lower bounds;
- hardness;
- algorithms;
- search space analysis.

#### Must check

- whether reductions are many-one/Turing/etc.;
- whether runtime claims are proven;
- whether lower-bound arguments are valid;
- whether finite brute force is being confused with general proof.

---

### 7.3 Mystic-BioMath

#### Domain

Mathematical biology and complex adaptive systems.

#### Handles

- dynamical systems;
- evolutionary models;
- networks;
- population models;
- emergent behavior.

#### Must check

- model assumptions;
- parameter sensitivity;
- whether simulations generalize;
- whether biological analogy is mathematically meaningful.

---

### 7.4 Mystic-Chem

#### Domain

Chemistry, molecular systems, and materials modeling.

#### Handles

- molecular structure;
- reaction models;
- graph-based chemistry;
- energy landscapes;
- materials hypotheses.

#### Must check

- whether chemical assumptions are justified;
- whether approximations are stated;
- whether simulation claims are overgeneralized.

---

## 8. Verification Division

### 8.1 Mystic-Lean

#### Domain

Lean formal proof.

#### Handles

- Lean statement drafting;
- mathlib dependency search;
- proof skeletons;
- tactic attempts;
- proof state explanation;
- error-log repair.

#### Output

```text
LEAN_STATEMENT_DRAFT:
REQUIRED_IMPORTS:
DEPENDENCIES:
PROOF_SKELETON:
BLOCKERS:
FORMALIZATION_STATUS:
```

---

### 8.2 Mystic-SMT

#### Domain

SAT/SMT and finite constraint verification.

#### Handles

- finite counterexample search;
- satisfiability checking;
- constraint encodings;
- bounded verification.

#### Must check

- whether the encoding matches the original problem;
- whether bounded verification is being overgeneralized;
- whether SAT/UNSAT result is interpreted correctly.

---

### 8.3 Mystic-Raven

#### Domain

Adversarial mathematical refereeing.

#### Role

Raven is hostile. It assumes the proof is invalid until every step is justified.

#### Must check

1. hidden assumptions
2. undefined objects
3. circular reasoning
4. fake equivalence
5. one-way implication treated as equivalence
6. non-invariant invariants
7. insufficient obstruction
8. density argument treated as universal proof
9. missing positivity
10. missing integrality
11. denominator-zero issues
12. unsupported divisibility
13. finite-pattern-to-infinite leap
14. unsupported words like clearly, obviously, must exist
15. whether the new viewpoint actually does mathematical work

#### Verdicts

- `VALID_COMPLETE_PROOF`
- `INVALID`
- `PARTIAL_RESULT_ONLY`
- `INTERESTING_BUT_UNPROVEN_FRAMEWORK`
- `UNCLEAR`
- `NEEDS_MORE_DETAIL`

---

## 9. Discovery Division

### 9.1 Mystic-Forge

#### Domain

Computational experimentation.

#### Handles

- Python experiments;
- SymPy experiments;
- brute-force search;
- counterexample search;
- pattern testing.

#### Output

```text
EXPERIMENT_PURPOSE:
SEARCH_SPACE:
ASSUMPTIONS:
CODE:
EXPECTED_OUTPUT:
FAILURE_MODES:
HOW_TO_INTERPRET_RESULT:
```

---

### 9.2 Mystic-Conjecture

#### Domain

Conjecture generation.

#### Handles

- generating weak conjectures;
- strengthening conjectures;
- recording evidence;
- identifying possible counterexample regions.

#### Must not

- call conjectures proofs;
- generalize beyond evidence;
- ignore Raven objections.

---

### 9.3 Mystic-Pattern

#### Domain

Pattern discovery.

#### Handles

- sequence patterns;
- graph patterns;
- modular patterns;
- invariant candidates;
- hidden parameters.

#### Must check

- whether patterns are stable under larger tests;
- whether pattern is merely numerical coincidence;
- whether proposed invariant is actually invariant.

---

### 9.4 Mystic-Simulator

#### Domain

Scientific simulation.

#### Handles

- numerical simulation;
- dynamical models;
- parameter sweeps;
- model comparison.

#### Must check

- whether simulation assumptions are explicit;
- whether numerical error is controlled;
- whether simulation supports only heuristic status.

---

## 10. Memory Division

### 10.1 Mystic-Archive

Stores all sessions, attempts, experiments, critiques, claims, and reports.

### 10.2 Mystic-KnowledgeGraph

Maintains concept/theorem/problem dependency graph.

For v0.1, this can be a simple SQLite table or JSON graph.

### 10.3 Mystic-Evolution

Builds future training datasets.

Exports:

```text
raven_dataset.jsonl
forge_dataset.jsonl
prime_dataset.jsonl
lean_dataset.jsonl
core_dataset.jsonl
domain_agent_dataset.jsonl
```

---

## 11. Unified Agent Output Protocol

Every domain agent must output:

```text
CLAIM:
STATUS:
DOMAIN:
REASONING:
DEPENDENCIES:
OBSTRUCTION:
EXPERIMENT:
FORMALIZATION:
NEXT_MOVE:
```

Allowed status values:

- `PROVED`
- `FORMALIZED`
- `HEURISTIC`
- `GAP`
- `REFUTED`
- `UNKNOWN`
- `PROMISING`
- `DEAD_END`

Rules:

1. Computational evidence is never proof.
2. A physical analogy is never proof.
3. A pattern is never proof.
4. A Lean-accepted theorem can be marked `FORMALIZED`.
5. A complete natural-language proof can be marked `PROVED` only after Raven review.
6. Anything incomplete must be `GAP`, `HEURISTIC`, `UNKNOWN`, or `PROMISING`.

---

## 12. Router Requirements

Implement a rule-based router for v0.1.

Create:

```text
mystic/core/router.py
configs/router_config.yaml
```

Example router config:

```yaml
routes:
  prime:
    keywords:
      - integer
      - prime
      - divisor
      - congruence
      - modular
      - diophantine
      - fraction
      - rational
  algebra:
    keywords:
      - group
      - ring
      - field
      - module
      - homomorphism
      - representation
      - category
  geo:
    keywords:
      - geometry
      - topology
      - manifold
      - curve
      - variety
      - dimension
      - algebraic geometry
  analysis:
    keywords:
      - limit
      - convergence
      - PDE
      - differential equation
      - compactness
      - regularity
      - functional analysis
  probability:
    keywords:
      - probability
      - random
      - stochastic
      - expectation
      - Markov
      - concentration
  logic:
    keywords:
      - logic
      - axiom
      - undecidable
      - computable
      - model theory
      - set theory
  physics:
    keywords:
      - symmetry
      - conservation
      - quantum
      - relativity
      - field
      - energy
  complexity:
    keywords:
      - algorithm
      - complexity
      - NP
      - reduction
      - lower bound
      - runtime
  forge:
    always_if_computable: true
  raven:
    always: true
  lean:
    always_if_math_claim: true
```

The router must support multiple agents per session.

---

## 13. Orchestration Flow

Default flow:

1. CoreAgent creates research plan.
2. Router selects domain agents.
3. Selected domain agents analyze the problem.
4. ForgeAgent designs computational experiments.
5. PythonRunner executes Forge code if safe.
6. LeanAgent attempts formalization if relevant.
7. RavenAgent critiques all claims and proof attempts.
8. ArchiveAgent stores everything.
9. ReportAgent generates final report.
10. EvolutionAgent exports future training records.

Raven must run after every major claim-producing agent.

---

## 14. CLI Requirements

Implement:

```text
mystic init
mystic run "problem text"
mystic sessions
mystic show SESSION_ID
mystic export raven
mystic export forge
mystic export all
mystic eval fake-proofs
mystic agents
mystic config
```

`mystic agents` should list all available agents and their configured model.

---

## 15. API Requirements

Implement FastAPI endpoints:

```text
POST /sessions
POST /sessions/{session_id}/run
GET /sessions/{session_id}
GET /sessions
GET /agents
GET /config/models
POST /datasets/export
```

---

## 16. Tool Requirements

### Python Runner

Must:

- run generated Python code in temporary directory;
- enforce timeout;
- capture stdout/stderr;
- block shell commands by default;
- return structured result.

### Lean Runner

Must:

- detect whether Lean is installed;
- return `LEAN_NOT_INSTALLED` if unavailable;
- run Lean code if available;
- capture errors.

### SMT Runner

For v0.1 can be stubbed.

If z3 is installed, support simple finite checks.

---

## 17. Archive Requirements

Store:

- `research_sessions`
- `agent_messages`
- `claims`
- `experiments`
- `raven_critiques`
- `lean_attempts`
- `smt_attempts`
- `reports`
- `dataset_exports`

Every agent message must record:

- `session_id`
- `agent_name`
- `division`
- `model_provider`
- `model_name`
- `adapter_name`
- `input_text`
- `output_text`
- `structured_output`
- `created_at`

This is important because later Mystic will train separate models from each agent’s records.

---

## 18. Dataset Export Requirements

Export JSONL per agent type.

Examples:

```text
data/exports/raven_dataset.jsonl
data/exports/forge_dataset.jsonl
data/exports/prime_dataset.jsonl
data/exports/algebra_dataset.jsonl
data/exports/analysis_dataset.jsonl
data/exports/lean_dataset.jsonl
data/exports/core_dataset.jsonl
```

Each row must include:

```json
{
  "agent": "raven",
  "division": "verification",
  "instruction": "...",
  "input": "...",
  "output": "...",
  "status": "...",
  "metadata": {
    "session_id": "...",
    "model": "...",
    "adapter": "..."
  }
}
```

---

## 19. v0.1 Implementation Priority

### Priority 1

Must fully implement:

- CoreAgent
- Router
- RavenAgent
- ForgeAgent
- PythonRunner
- Archive
- ReportAgent
- CLI
- SQLite
- MockProvider
- OllamaProvider
- OpenAICompatibleProvider

### Priority 2

Implement as real prompt-based agents, even if simple:

- PrimeAgent
- AlgebraAgent
- GeoAgent
- AnalysisAgent
- ProbabilityAgent
- LogicAgent
- PhysicsAgent
- ComplexityAgent
- LeanAgent
- ConjectureAgent
- PatternAgent

### Priority 3

Stub acceptable for v0.1:

- BioMathAgent
- ChemAgent
- SMTAgent
- SimulatorAgent
- KnowledgeGraphAgent
- EvolutionAgent

But even stub agents must have:

- class file
- prompt file
- config entry
- archive logging
- dataset export compatibility

---

## 20. Minimum Demo

The first demo command:

```bash
mystic run "Attack the Erdős–Straus conjecture: for every integer n >= 2, prove or refute that 4/n = 1/x + 1/y + 1/z for positive integers x,y,z."
```

Expected behavior:

1. Core restates the problem.
2. Router selects Prime, Forge, Raven, Lean, Pattern, Conjecture.
3. Prime analyzes number-theoretic structure.
4. Forge generates a finite search experiment.
5. PythonRunner executes the experiment.
6. Pattern looks for residue-class behavior.
7. Conjecture proposes only `HEURISTIC` claims.
8. Lean attempts formalization and likely reports blockers.
9. Raven critiques every claim.
10. ReportAgent generates final report.
11. Archive stores all outputs.
12. EvolutionAgent prepares dataset rows.

---

## 21. Final Instruction to Codex

Build Mystic v0.1 as a local-first Python project.

The most important architectural requirement:

Every specialist must be treated as a separate model role.

Even if several agents use the same underlying open-source model in v0.1, the code must preserve:

- separate agent class
- separate prompt
- separate config entry
- separate archive records
- separate dataset export path
- future adapter field

Do not collapse the system into a single generic agent.

Do not build a frontend first.

Make the CLI work first.

The core workflow must be:

```text
Problem
→ Core planning
→ Router
→ Multi-specialist analysis
→ Forge experiment
→ Python execution
→ Lean/SMT formal check attempt
→ Raven critique
→ Archive
→ Report
→ Dataset export
```

The final project must be clean, typed, testable, and prepared for future LoRA/QLoRA specialist training.

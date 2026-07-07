# Mystic LAB Domains

Mystic LAB is intended to support a broad research-domain surface, but support must be stated conservatively.

The table below describes the product target, planned phase, and current status.

| Domain | Intended capability direction | MVP phase | Current status |
| --- | --- | --- | --- |
| Mathematics | symbolic reasoning, proof workflows, brute-force verification, theorem/lemma management | Phase 1 | LAB orchestration implemented; deterministic local/native `math.sympy` subset is live and Worker returns `engine_required` when SymPy is unavailable |
| Physics | simple mechanics, projectiles, collisions, parameterized simulation, scene-linked evidence | Phase 1 | LAB orchestration implemented; deterministic projectile/collision adapters are live |
| Chemistry | reaction/state modeling, parameter sweeps, evidence-linked experiments | Phase 2 | Planned |
| Biology | dynamical systems, population or pathway modeling, hypothesis/assumption tracking | Phase 2 | Planned |
| Earth Science | geophysical/environmental scenario workflows and evidence-linked simulations | Phase 3 | Planned |
| Astronomy / Space Science | orbital/scenario modeling, parameterized simulation, report generation | Phase 3 | Planned |
| Computer Science | algorithmic reasoning, testing, verification, structured design experiments | Cross-cutting | Partially represented through existing coding and experiment workflows |
| Statistics / Data Science | estimation, model comparison, dataset-linked reports, uncertainty handling | Phase 2 | Planned |
| Engineering | design tradeoff studies, simulation-backed evidence, experiment planning | Phase 3 | Planned |
| Medical Science | conservative review, evidence/provenance constraints, domain-specific workflows | Phase 4 | Planned |
| Agricultural / Food Science | applied simulation/reporting workflows for production and experimental analysis | Phase 4 | Planned |
| Social Science | structured evidence collection, debate, critique, and report synthesis | Phase 4 | Planned |
| Cognitive Science | experiment/state modeling, hypothesis critique, evidence archive | Phase 4 | Planned |
| Materials Science | simulation-linked property studies and experiment planning | Phase 4 | Planned |
| Environmental / Climate Science | parameterized scenario studies and reportable evidence chains | Phase 4 | Planned |
| AI for Science | orchestrating model agents plus deterministic tools for scientific workflows | Phase 4 | Planned |
| Interdisciplinary Research | composition of multiple domain adapters in one lab session | Cross-phase | Planned |

## Important Current Limitation

The current runtime schemas still expose a narrower execution enum than the long-term domain map. That means the product vision is broader than today’s tool-level validated domain list.

This is intentional. Mystic LAB already has the orchestration substrate, but not every domain-specific engine and schema extension has been implemented.

## Current Implemented Domain Foundation

What is implemented now:

- general lab session orchestration
- conservative claim status handling
- experiment/failure/report persistence
- public cloud-native MCP access
- explicit provider-gated model actions

What is not yet implemented:

- broad domain-specific engine adapters
- domain-specific scene object libraries
- domain-specific 3D interaction models
- production-grade multi-engine execution paths

## Phase 1 Focus

Phase 1 is intentionally narrow:

- Mathematics
- Simple Physics
- 3D Scene API

This is the first point where Mystic LAB should move from orchestration-only infrastructure into real engine-backed research execution in public cloud-native mode.

That initial shift is now implemented for basic scene storage, simple physics, and export/report flows, while broader domain execution remains phased.

# Issue #2: Training bootstrap from checklist

## Summary
Implement the first training-preparation layer described in `mystic_requirements_checklist.md`, focusing on dataset schemas, internal Mystic data templates, training manifests, and bootstrap scripts.

## Motivation
The checklist is not just reference material. It defines the next concrete build phase needed to prepare specialist training and data collection.

## Current Behavior
- The repository contains the agent scaffold and archive flow.
- `mystic_data/` exists but does not yet contain schema definitions, manifests, or training bootstrap files.
- There is no canonical internal dataset format for `failed_proofs`, `raven_critiques`, `forge_experiments`, `lean_attempts`, or `routing_logs`.

## Expected Behavior
- `mystic_data/metadata/` contains explicit JSON schemas and manifests for the first training datasets.
- The repository can initialize internal Mystic data files and training-ready manifests from scripts.
- The project contains first-pass training configs for specialist adapters named in the checklist.

## Scope
- Add JSON schemas for internal Mystic records and train-ready rows.
- Add dataset catalog and ingestion manifest for priority datasets.
- Add scripts to initialize internal dataset files and export training manifests.
- Add first-pass LoRA training config skeletons for Raven, Forge, Prime, Lean, Core Router, Pattern, Physics, Chem, BioMath, and Report.

## Acceptance Criteria
- `mystic_data/metadata/` includes reusable schema files for internal data and train-ready exports.
- A script can create empty JSONL files for internal Mystic data categories.
- A script can generate per-specialist training manifests from the checklist priorities.
- Training config files exist for the first-pass specialist adapters.

## Verification Plan
- Run unit tests covering schema/manifests/bootstrap helpers.
- Run the bootstrap scripts and verify output files are created in `mystic_data/`.


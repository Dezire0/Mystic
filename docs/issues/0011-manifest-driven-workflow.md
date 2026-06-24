# Issue #11: Add a manifest-driven data collection and training workflow

## Summary
Create a single workflow runner that follows the checklist-derived Mystic manifests for data collection, train-ready preparation, specialist training planning, and Raven cycle packaging.

## Motivation
The repository already contains the dataset checklist, ingestion manifests, specialist training configs, and a Kaggle Raven cycle runner. What is missing is a top-level workflow command that executes those steps in order without requiring manual interpretation each time.

## Current Behavior
- Data collection is spread across multiple scripts.
- Specialist training plans are generated one agent at a time.
- Raven cycle preparation is separate from broader data collection.
- There is no single workflow summary tying together collection, preparation, and training planning.

## Expected Behavior
- A workflow runner reads the existing checklist-derived manifests.
- One command performs local bootstrap, Hugging Face sample collection, Numina collection, Raven export/prepare, specialist train-ready generation, training plan generation, and optional Raven cycle packaging.
- The workflow writes a structured summary under `mystic_data/workflows/<workflow_id>/`.
- A status command shows the latest workflow state and data counts.

## Scope
- Add `scripts/run_manifest_workflow.py`
- Add tests for the workflow helpers and orchestration
- Update README with exact workflow commands
- Ignore generated workflow tarballs

## Acceptance Criteria
- `run_manifest_workflow.py run` completes successfully in dry-run mode using existing scripts.
- The workflow summary contains collection outputs, train-ready outputs, and per-agent training plan outputs.
- `run_manifest_workflow.py status` prints the latest summary plus local data counts.
- Tests cover manifest loading, summary writing, and orchestration behavior.

## Verification Plan
- Run targeted unit tests for the new workflow and existing cycle runner.
- Execute the new workflow locally with small sample limits.
- Confirm the generated summary and status output under `mystic_data/workflows/`.

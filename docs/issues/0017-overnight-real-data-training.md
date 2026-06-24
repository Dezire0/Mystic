# Issue #17: Build an overnight real-data multi-section training workflow

## Summary
Replace bootstrap-only specialist smoke preparation with a real-data overnight workflow that downloads larger public dataset slices, prepares section-aligned train-ready JSONL files from those datasets, and runs repeated specialist training batches across all trainable architecture sections.

## Motivation
The current repository can smoke-train all sections, but most sections still rely on synthetic bootstrap rows or tiny sample files. The user wants overnight training driven by the architecture canvas and the attached checklist datasets, not just placeholder data.

## Current Behavior
- Hugging Face download scripts mainly fetch tiny `sample.jsonl` files.
- `prepare_train_ready.py` only prepares train-ready rows from internal Mystic data.
- Multi-section batch training can run, but many rows are synthetic bootstrap data instead of real public dataset rows.

## Expected Behavior
- The repo can download larger real dataset slices from supported public sources.
- A public-data preparation path creates per-agent train-ready JSONL files aligned with the architecture plan.
- An overnight runner can repeat collection, preparation, and specialist training for hours while updating execution history.

## Scope
- Add real-data download support with configurable row budgets.
- Add public-data train-ready preparation for architecture sections.
- Add an overnight workflow runner and summary logs.
- Keep logs append-only and history page updating.

## Acceptance Criteria
- At least the currently supported HF sources can be downloaded with row limits higher than the sample path.
- Public train-ready rows are written for relevant agents using real raw dataset rows.
- A single command can run repeated overnight-style training batches for all configured trainable sections.
- Execution history reflects those repeated runs.

## Verification Plan
- Run unit tests for new public-data preparation and overnight workflow helpers.
- Run one bounded overnight workflow iteration locally with real raw rows.
- Confirm train-ready row counts increase and batch training completes.

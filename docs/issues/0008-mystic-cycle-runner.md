# Issue #8: Add a local Mystic cycle runner

## Summary
Add a local automation runner that packages the current Raven training cycle into stable `prepare`, `finish`, and `status` commands without changing the append-only JSONL architecture.

## Motivation
The current Mystic workflow already has a repeatable pattern:
data export -> train/eval prep -> GPU package build -> adapter restore -> reinjection -> comparison -> registry update.
That pattern is operationally clear but still manually stitched together. A cycle runner reduces repeated command errors and makes the Qwen Raven adapter loop easier to execute consistently.

## Current Behavior
- Data prep, packaging, reinjection, comparison, and registration are separate commands.
- Processed ID reset and adapter validation are easy to miss.
- There is no single cycle summary log that records what happened across prepare and finish stages.

## Expected Behavior
- `scripts/run_mystic_cycle.py prepare` exports training data, prepares train/eval JSONL, and creates a GPU upload tarball.
- `scripts/run_mystic_cycle.py finish` restores a returned adapter tarball, validates the adapter/base pairing, backs up and clears processed IDs, runs adapter reinjection, runs base-vs-adapter comparison, registers the adapter, and writes a cycle summary.
- `scripts/run_mystic_cycle.py status` reports the latest local cycle state, adapter availability, processed ID count, and registry status.

## Scope
- Add `scripts/run_mystic_cycle.py`
- Add focused tests for prepare/finish/status helpers
- Update README with cycle runner commands
- Keep all logs append-only

## Player Flow
1. Run `prepare` locally.
2. Upload the generated tarball to Kaggle/Colab/RunPod and train the adapter.
3. Download the adapter tarball.
4. Run `finish` locally to validate, reinject, compare, and register.
5. Run `status` to inspect the current cycle state.

## Non-goals
- Kaggle API automation
- Frontend
- PostgreSQL
- Vector database
- Web dashboard
- Multi-agent orchestration

## Acceptance Criteria
- `scripts/run_mystic_cycle.py` supports `prepare`, `finish`, and `status`.
- Prepare mode writes a GPU package tarball and a cycle log entry.
- Finish mode validates adapter files and base model before adapter use.
- Finish mode backs up and clears `mystic_data/state/processed_ids.jsonl`.
- Finish mode runs `mystic_loop.py`, `compare_raven_models.py`, and `register_model.py`.
- Comparison summaries record `adapter_better_or_equal_rate`.
- Status mode reports current adapter, registry, and processed ID counts.

## Verification Plan
- Run targeted unit tests for cycle runner helper behavior.
- Verify prepare creates the expected tarball and logs.
- Verify finish fails clearly on adapter/base mismatch.
- Verify finish appends a cycle summary after mocked loop/compare/register steps.

## Reproduction Steps
1. Export and prepare Raven training data manually.
2. Train an adapter externally.
3. Reinject it manually while remembering to validate files and reset processed IDs.
4. Observe the number of steps and the chance of operator error.

## Actual Result
The cycle is usable but fragile because key checks and summaries are distributed across many separate commands.

## Expected Result
The local cycle can be executed reliably with `prepare`, external GPU training, and `finish`, with `status` available for inspection.

## Environment
- Local macOS workspace
- Python 3.11
- Existing Mystic v3 JSONL loop and Raven training pipeline

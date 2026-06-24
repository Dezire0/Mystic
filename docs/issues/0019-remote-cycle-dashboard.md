# Issue #19: Connect the remote Kaggle training path and make logs readable

## Summary
Attach Mystic's existing Kaggle GPU Raven cycle to the persistent local training flow and replace the current raw execution log page with a more readable dashboard.

## Motivation
The local smoke-training daemon now runs continuously, but the real free-GPU path is still separate from that background workflow. At the same time, the current log page is technically correct but visually noisy and hard to scan during long-running training.

## Current Behavior
- `scripts/run_continuous_training_daemon.py` rotates local datasets and runs smoke specialist training forever.
- `scripts/run_mystic_cycle.py full` can already run a full Kaggle-backed Raven cycle, but only when called directly.
- `mystic_data/reports/execution_history.html` shows append-only records, but the page is mostly a flat table with limited operational context.

## Expected Behavior
- A persistent remote-cycle service can keep launching Kaggle-backed Raven cycles in sequence using the existing `run_mystic_cycle.py full` path.
- The remote service persists its own state, retries safely, and avoids overlapping cycles.
- The main report page clearly shows:
  - local daemon state
  - remote Kaggle cycle state
  - recent successes and failures
  - current dataset / current kernel / current cycle
  - recent execution records in a readable table

## Scope
- Add a background remote-cycle daemon and launchd manager.
- Persist remote-cycle state and render a small status report.
- Enhance the execution history dashboard for faster human scanning.
- Update tests for the new dashboard payloads and state readers.

## Non-goals
- Rebuild the existing Kaggle cycle runner logic from scratch.
- Add a frontend app or database.
- Add non-Kaggle remote providers.

## Acceptance Criteria
- A new daemon can continuously execute `scripts/run_mystic_cycle.py full` for sequential cycle IDs.
- The daemon writes append-only status artifacts and state snapshots under `mystic_data/`.
- The dashboard shows both local and remote pipeline status at a glance.
- The dashboard highlights success/failure and source/type more clearly than the current version.
- Existing append-only JSONL behavior remains intact.

## Verification Plan
- Run unit tests for execution history and cycle-runner helpers.
- Run the remote daemon once in dry operational mode against the existing Kaggle CLI path.
- Confirm the dashboard JSON/HTML includes remote state and readable summary cards.

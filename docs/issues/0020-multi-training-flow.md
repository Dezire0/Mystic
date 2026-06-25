# Issue #20: Stabilize multi-training flow and sectioned dashboard

## Summary
Fix the current Kaggle remote-cycle failures, keep local and remote training running, and make the execution dashboard show section-specific datasets and training status.

## Motivation
Mystic now has local continuous smoke training and a Kaggle-backed Raven adapter cycle, but the remote path is repeatedly failing and the report page does not yet separate training activity by architecture section. The user needs a night-long operating view that shows which section is learning from which dataset and where failures are occurring.

## Current Behavior
- Local continuous training is running.
- Remote Kaggle cycles repeatedly fail during dataset submission or kernel execution.
- The execution history page is readable at the row level, but section-level progress and dataset assignment are not prominent.
- Checklist progress is spread across architecture docs, cycle summaries, and logs.

## Expected Behavior
- Kaggle dataset submission should safely reuse or version existing datasets.
- Remote cycle failures should surface concrete stderr/stdout and not loop blindly through the same broken condition.
- The dashboard should group records by Mystic section and show each section's active/recent dataset.
- The system should keep local training running while remote failures are patched.
- Checklist progress should be reported from current project files and logs.

## Scope
- Patch Kaggle submit behavior and diagnostics.
- Add section/dataset summary data to the execution history renderer.
- Add tests for section grouping and Kaggle submit retry behavior where practical.
- Restart or keep running the relevant training/report services after verification.

## Non-goals
- Add paid GPU providers.
- Replace Kaggle with another platform.
- Train high-quality final adapters locally on Mac.
- Build a frontend app or database.

## Acceptance Criteria
- `scripts/run_mystic_cycle.py submit` handles existing Kaggle dataset slugs by creating a new version where possible.
- Remote cycle details include useful Kaggle stdout/stderr on failure.
- `execution_history.html` has distinct section blocks for active/recent datasets and training records.
- Local continuous training remains active.
- Report refresh remains active.
- Tests covering touched logic pass.

## Verification Plan
- Run focused unit tests for execution history and cycle runner helpers.
- Run `py_compile` on modified scripts.
- Check live state files for local continuous training, remote cycle state, and report refresh state.
- Confirm the HTML contains section cards and Kaggle links.

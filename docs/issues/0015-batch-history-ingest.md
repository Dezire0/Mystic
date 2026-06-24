# Issue #15: Ingest specialist batch training runs into execution history

## Summary
Extend the execution history page so it includes specialist batch training runs recorded in `mystic_data/reports/specialist_training_batch_run.json`.

## Motivation
The new execution history page does not currently show manual specialist training runs launched as a batch, even though those runs are part of the same session and generate adapters plus metrics.

## Current Behavior
- The page reads loop, evaluation, comparison, and cycle logs.
- Batch specialist training runs are missing from the page.

## Expected Behavior
- Batch specialist training runs appear as normal rows in the HTML list.
- The user can see the agent part, model name, success, and duration for those batch runs.

## Scope
- Update execution-history aggregation logic
- Add tests
- Regenerate the HTML report

## Acceptance Criteria
- `specialist_training_batch_run.json` is parsed when present.
- Each batch run appears as one row in the history output.
- Tests pass.

## Verification Plan
- Add a unit test with a fake batch summary file.
- Regenerate the execution history page and confirm the new rows appear.

# Issue #14: Add a simple HTML execution history page

## Summary
Aggregate Mystic execution logs into a single simple HTML page that shows numbered execution records with time, specialist part, model name, success, and duration.

## Motivation
Mystic already writes multiple JSONL logs, but there is no single human-readable page that lets the user quickly inspect what ran and whether it succeeded.

## Current Behavior
- Execution history is scattered across `training_log.jsonl`, `run_log.jsonl`, comparison logs, eval logs, and cycle summaries.
- The user cannot inspect the overall session history from one simple list.

## Expected Behavior
- A script builds one HTML page from the existing logs.
- The page shows one flat list with:
  - number
  - time
  - specialist part
  - LLM model name
  - success
  - duration

## Scope
- Add execution-history aggregation helpers
- Add an HTML renderer script
- Add tests
- Optionally document the output path

## Acceptance Criteria
- Running the renderer creates an HTML page under `mystic_data/reports/`.
- The page contains a single table-like list with numbered rows.
- Existing append-only logs remain unchanged.
- Targeted tests pass.

## Verification Plan
- Run unit tests for the new execution-history helpers.
- Generate the HTML page locally and inspect the output file.

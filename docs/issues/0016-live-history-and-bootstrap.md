# Issue #16: Add live execution-history refresh and bootstrap full specialist training

## Summary
Make the execution history page refresh automatically and add a bootstrap path that can seed train-ready rows plus run specialist smoke training across the remaining architecture sections.

## Motivation
The current page is a static snapshot and many architecture sections remain blocked by missing configs or empty train-ready files. The user wants the system to keep moving without manual step-by-step intervention.

## Current Behavior
- `execution_history.html` is only updated when rendered manually.
- Several architecture sections still have no training config.
- Several configured sections still have zero train-ready rows.

## Expected Behavior
- Execution-history outputs are regenerated automatically after key training and loop scripts run.
- The HTML page refreshes itself while open.
- Missing specialist train-ready files can be bootstrapped from available local data so smoke training can run across more sections.
- A single batch command can run all trainable specialist sections and record results.

## Scope
- Add automatic execution-history output writer
- Add HTML auto-refresh
- Add bootstrap architecture train-ready generator
- Add configs for missing specialist adapters
- Add a batch specialist runner

## Acceptance Criteria
- The page auto-refreshes while open.
- Running specialist scripts updates the history page without a manual render step.
- Missing specialist configs are added for the currently unconfigured trainable sections.
- A batch runner can execute smoke training for all non-tool specialists with available bootstrap rows.

## Verification Plan
- Run unit tests for execution history and bootstrap generation.
- Run the batch specialist runner locally.
- Confirm `execution_history.html` reflects the new runs automatically.

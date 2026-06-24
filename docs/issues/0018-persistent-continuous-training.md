# Issue #18: Add a persistent continuous multi-dataset training daemon

## Summary
Build a persistent continuous-training daemon that keeps Mystic's real-data specialist training running indefinitely, rotates through supported datasets, survives shell exit, and exposes live status in the local reports.

## Motivation
The current overnight runner is still a bounded batch. The user wants training to keep running regardless of other terminal activity and to continue feeding back by moving on to more datasets after each cycle.

## Current Behavior
- `run_overnight_training.py` is finite and stops after a fixed number of iterations.
- Keeping it alive depends on the caller session management.
- The execution history page shows completed rows, but not a durable daemon status.

## Expected Behavior
- A continuous daemon loops indefinitely until explicitly stopped.
- Dataset selection rotates across supported public sources instead of stopping at a fixed budget.
- The daemon survives terminal exit and is automatically restarted if it crashes.
- Local report pages show current daemon status and recent cycle feedback.

## Scope
- Add a continuous training daemon script.
- Add a macOS `launchd` manager for install/start/stop/status.
- Add cycle-state persistence and live feedback files.
- Surface daemon status in the local execution history page.

## Acceptance Criteria
- One command installs and starts the continuous trainer as a background service.
- The trainer keeps running after the initiating shell exits.
- The trainer rotates datasets and continues creating new cycle summaries.
- The execution history page shows current daemon status from local state.

## Verification Plan
- Run unit tests for the new state helpers and page rendering.
- Install the launch agent locally and confirm `launchctl` reports it loaded.
- Confirm the daemon writes cycle summaries and updates the report page while running.

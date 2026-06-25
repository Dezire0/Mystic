# Issue #24: Fix continuous training queue visibility and stalled dataset rotation

## Summary
Fix the specialist dashboard so completed smoke runs do not appear as fully finished when more checklist datasets remain, and harden the continuous training loop so it keeps moving to the next dataset instead of stalling on download timeouts or snapshot-only sources.

## Motivation
The Discord dashboard currently shows some experts at `100%` after a single successful local smoke run, which is misleading because the architecture checklist still has many remaining datasets. The continuous daemon is also stalling on dataset download timeouts and proofnet snapshot-only data, so retraining does not continue reliably.

## Current Behavior
- `mystic/discord_dashboard.py` marks many experts as `100%` if their latest local run succeeded.
- `scripts/run_overnight_training.py` can crash while handling `TimeoutExpired` because timeout output may be bytes.
- The default continuous dataset rotation includes snapshot-only or slow sources that can stall cycles without adding new trainable rows.

## Expected Behavior
- Dashboard progress reflects dataset coverage, not just the last success event.
- Experts with more remaining datasets show as waiting/in progress rather than permanently complete.
- Continuous cycles continue past slow or snapshot-only downloads without wedging the loop.
- The next dataset rotation prefers cached/sample-backed sources that can actually feed `train_ready`.

## Scope
- Update dashboard progress and status inference.
- Harden `run_overnight_training.py` timeout/error logging.
- Filter or reprioritize default rotation slugs for real sample-backed datasets.
- Refresh continuous training and dashboard outputs after the patch.

## Acceptance Criteria
- A single smoke success no longer forces trainable experts to `100%` unless dataset coverage is complete.
- Timeout exceptions in overnight training are logged without secondary crashes.
- Continuous rotation skips snapshot-only stalls and keeps cycling through usable datasets.
- The dashboard reflects the next dataset queue more accurately.

## Verification Plan
- Run focused unit-free smoke checks by importing dashboard helpers and printing snapshot summaries.
- Run `py_compile` on touched scripts/modules.
- Restart the continuous training launchd service and verify updated state.
- Regenerate execution history outputs and inspect resulting status values.

## Reproduction Steps
1. Open the Discord dashboard after one successful specialist smoke run.
2. Observe specialists showing `100%` even though multiple checklist datasets remain.
3. Inspect `mystic_data/logs/continuous_cycle_details/` and find cycles failing on timeout or proofnet snapshot-only data.

## Actual Result
The dashboard overstates completion and the continuous loop can stall before retraining on the next dataset.

## Expected Result
The dashboard should represent remaining work honestly and the continuous loop should keep advancing through usable datasets.

## Environment
- Project root: `/Users/JYH/Documents/Mystic`
- macOS launchd
- Local continuous training daemon

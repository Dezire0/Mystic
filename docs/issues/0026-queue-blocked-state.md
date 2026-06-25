# Issue #26: Fix misleading 100% states and blocked dataset rotation

## Summary
Remove misleading `100%` states for tool-only components, surface when the current training cycle is stuck for too long, and temporarily exclude timeout-prone datasets from the automatic local rotation until they have dedicated ingest paths.

## Motivation
The dashboard can still show `100%` for non-trainable tool components while the actual local cycle is stuck on a single dataset for hours. This makes it look like training should have already moved to the next dataset when it has not.

## Current Behavior
- `tool_only` agents like `smt`, `archive`, `knowledge_graph`, and `evolution` appear fully complete.
- The local continuous daemon processes one dataset cycle at a time and only advances after the whole batch finishes or times out.
- `proofnet` and `leandojo` cycles repeatedly run long or hit cycle timeouts in the current automatic rotation.

## Expected Behavior
- Tool-only components should not display misleading training progress.
- The dashboard should explicitly show when a cycle is delayed and what the next dataset is.
- Automatic rotation should prefer datasets that reliably produce trainable local batches.

## Scope
- Update Discord dashboard status/progress semantics for tool-only agents.
- Add local/remote delayed-state labels in the dashboard status boxes.
- Temporarily narrow the auto-rotation dataset list to stable slugs.
- Reinstall the continuous training service with the updated rotation.

## Acceptance Criteria
- Tool-only agents no longer appear as `100%` trained.
- The dashboard shows the next dataset and whether the current cycle is delayed.
- The local continuous daemon rotates through stable datasets instead of repeatedly stalling on the deferred ones.

## Verification Plan
- Run dashboard-focused tests.
- Rebuild a snapshot from current state and inspect representative rows.
- Reinstall/restart the continuous training launchd service and confirm the new slug rotation in status output.

## Reproduction Steps
1. Open the Discord dashboard.
2. Observe `100%` for tool-only agents.
3. Check `continuous_training_state.json` and see the same dataset cycle running for hours.
4. Inspect recent cycle detail logs and see repeated timeouts on the deferred slugs.

## Actual Result
The dashboard implies forward queue progress that the current local loop has not actually achieved.

## Expected Result
The dashboard should show blocked or delayed states honestly, and the local automatic rotation should continue across stable datasets.

## Environment
- Project root: `/Users/JYH/Documents/Mystic`
- macOS launchd
- Local continuous training daemon

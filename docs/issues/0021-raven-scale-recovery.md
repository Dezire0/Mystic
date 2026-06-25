# Issue #21: Scale Raven data, recover failed training, and chain remote cycles

## Summary
Increase Raven training data automatically, fix the repeat failures in local/remote training flows, and ensure the next remote cycle starts immediately after a successful finish.

## Motivation
Mystic is running, but the current Raven remote cycle is still training on a tiny dataset and several background training paths are wasting time on avoidable failures. The system needs a larger checklist-aligned Raven dataset, safer retry behavior, and uninterrupted cycle chaining.

## Current Behavior
- `export_raven_lora.py` only exports the small set of internal Raven critiques.
- Remote Kaggle cycles fail because the training package is not visible when the kernel starts.
- Continuous local training spends time re-downloading datasets and can fail noisily on timeout handling.
- Successful remote finishes do not yet guarantee immediate progression into the next larger dataset cycle.

## Expected Behavior
- Raven export should automatically build a larger trainable dataset from checklist-aligned local sources when a larger split is requested.
- Continuous training should prefer cached local data and survive timeout/error serialization cleanly.
- Remote Kaggle submission should give the kernel a better chance of seeing its dataset package and should keep moving into the next cycle after success.

## Scope
- Add larger Raven LoRA data synthesis from internal critiques plus local checklist-aligned source rows.
- Patch local continuous-training download behavior and timeout logging.
- Patch remote Kaggle package visibility behavior and daemon defaults for continuous chaining.
- Verify the updated automation and restart the affected services.

## Non-goals
- Build paid GPU automation.
- Introduce a frontend or database.
- Replace Kaggle with another training provider.

## Acceptance Criteria
- Raven export can produce a materially larger dataset than the current 10-row export when asked for a larger target.
- Continuous local training no longer burns cycles on avoidable cached-download timeouts.
- Kaggle remote cycles include the package-visibility fix and restart into the next cycle after success.
- Existing logs remain append-only and existing adapters are preserved.

## Verification Plan
- Run focused unit tests for cycle orchestration and training helpers.
- Generate a larger Raven export and confirm train/eval counts increase.
- Run the relevant local scripts and inspect state/log JSON.
- Restart the background services and confirm new cycles use the updated logic.

## Reproduction Steps
1. Inspect `mystic_data/train_ready/raven_lora.jsonl`, `raven_train.jsonl`, and `raven_eval.jsonl`.
2. Inspect `mystic_data/cycles/remote_cycle_0038` through `remote_cycle_0040`.
3. Inspect `mystic_data/logs/continuous_cycle_details/cycle_000007.json` through `cycle_000009.json`.

## Actual Result
Remote cycles fail with `Package tarball not found`, Raven train/eval data is too small, and continuous local training has repeated download/timeout failures.

## Environment
- Project root: `/Users/JYH/Documents/Mystic`
- Python 3.11
- Local macOS + Kaggle free GPU workflow

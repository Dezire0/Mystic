# Issue #10: Make the Kaggle cycle runner ready for Cycle 1 Raven scaling

## Summary
Adjust the Kaggle-backed Mystic cycle runner so Cycle 1 can run directly with larger data targets, a new adapter slot, and updated 0.5B Raven training settings.

## Motivation
The current automation works, but its defaults still reflect the small v0 loop. Cycle 1 needs direct support for a `1000 train / 100 eval` split, a `raven_lora_v1` output path, and the lower `0.00015` learning rate intended for the scaled 0.5B validation critic.

## Current Behavior
- `prepare` only exposes a generic `--limit`.
- Generated Kaggle commands and Kaggle training scripts still default to `raven_lora_v0`.
- Training defaults inside the automation still assume the older learning-rate example.

## Expected Behavior
- `prepare` and `full` accept explicit `--train-limit` and `--eval-limit`.
- Generated Kaggle commands and notebook scripts can target `raven_lora_v1`.
- Learning rate, epochs, batch size, and max length are configurable from the cycle runner.
- README examples match the Cycle 1 plan directly.

## Scope
- Update `scripts/run_mystic_cycle.py`
- Update tests
- Update README examples

## Acceptance Criteria
- `prepare --train-limit 1000 --eval-limit 100` produces the intended split request.
- `full` can target `mystic_data/adapters/raven_lora_v1`.
- Generated Kaggle docs and scripts use the provided adapter path and learning rate.
- Tests still pass.

## Verification Plan
- Run unit tests for the cycle runner.
- Confirm help output includes the new knobs.
- Confirm generated command text references Cycle 1 settings.

# Issue #7: Align Raven adapter names with their true base models

## Summary
Rename the existing tiny-gpt2 Raven smoke-test adapter, reserve `mystic_data/adapters/raven_lora_v0` for the real Qwen-based Raven adapter, and update validation, registry, and documentation so base-model mismatches are explicit and non-silent.

## Motivation
PEFT adapters are tied to the exact base model they were trained on. The current adapter artifact at `mystic_data/adapters/raven_lora_v0` is actually a tiny-gpt2 smoke-test adapter, but README and loop commands describe it as a Qwen-based real Raven adapter. That is operationally wrong and leads to guaranteed load failures.

## Current Behavior
- `mystic_data/adapters/raven_lora_v0/adapter_config.json` declares `base_model_name_or_path = sshleifer/tiny-gpt2`.
- README commands describe `raven_lora_v0` as a Qwen adapter.
- Registry metadata does not distinguish smoke-test adapters from real target adapters.

## Expected Behavior
- The tiny-gpt2 smoke-test adapter is preserved under a distinct name.
- `mystic_data/adapters/raven_lora_v0` is reserved for the real Qwen-based Raven adapter.
- Adapter/base-model validation stops mismatched loads with a clear error.
- README clearly separates smoke-test commands from real Raven commands.
- Registry metadata marks the smoke adapter as `smoke_test` and `raven_lora_v0` as the real target slot.

## Scope
- Rename the existing adapter directory.
- Update README examples and caveats.
- Update `mystic_data/metadata/model_versions.json`.
- Keep the mismatch validation in `mystic/llm_client.py` explicit.

## Acceptance Criteria
- The existing tiny-gpt2 adapter is preserved as `mystic_data/adapters/raven_lora_tiny_gpt2_smoke`.
- `raven_lora_v0` is no longer used to refer to the tiny-gpt2 smoke adapter.
- README smoke-test commands use `sshleifer/tiny-gpt2` plus `raven_lora_tiny_gpt2_smoke`.
- README real Raven commands use `Qwen/Qwen2.5-0.5B-Instruct` plus `raven_lora_v0`.
- Registry metadata distinguishes smoke adapter vs real target.

## Verification Plan
- Confirm the renamed directory exists and contains the original adapter files.
- Run unit tests, especially adapter/base validation coverage.
- Confirm the mismatch error remains clear when a wrong base model is supplied.

## Reproduction Steps
1. Inspect `mystic_data/adapters/raven_lora_v0/adapter_config.json`.
2. Observe `base_model_name_or_path` is `sshleifer/tiny-gpt2`.
3. Compare that to the documented Qwen load commands.

## Actual Result
The documented base model and the stored adapter artifact do not match.

## Expected Result
Smoke-test and real Raven adapter paths are separated cleanly and documented accurately.

## Environment
- Local macOS workspace
- Python 3.11
- Existing PEFT adapter artifact trained on `sshleifer/tiny-gpt2`

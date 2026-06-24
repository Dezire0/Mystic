# Issue #6: Reinject trained Raven adapter into the Mystic loop

## Summary
Upgrade Mystic v2 so the research loop can use the trained Raven PEFT adapter as the active critic, compare it against the base Raven model, and promote the adapter in the model registry when it performs at least as well on selected metrics.

## Motivation
Mystic v2 can train and evaluate a Raven adapter, but the adapter is not yet part of the live research loop. Mystic needs a closed feedback path where trained Raven adapters generate new critiques, are compared against the base critic, and can be promoted into active use.

## Current Behavior
- `scripts/mystic_loop.py` supports `ollama` and `openai-compatible` backends only.
- The trained Raven adapter exists on disk but is not loaded by the live loop.
- There is no dedicated base-vs-adapter comparison script or promotion script.
- Model registry metadata does not yet track active Raven adapter state.

## Expected Behavior
- The loop supports `--backend adapter` and can run Raven critique with `base model + PEFT adapter`.
- The loop can optionally compare adapter Raven against base Raven on the same proof attempt.
- Comparison logs are appended to JSONL and can be used for promotion decisions.
- A promotion script can mark an adapter active in `mystic_data/metadata/model_versions.json` without deleting prior entries.

## Scope
- Update `mystic/llm_client.py`
- Update `scripts/mystic_loop.py`
- Update `configs/models.json`
- Add `scripts/compare_raven_models.py`
- Add `scripts/promote_raven_adapter.py`
- Update `README.md`
- Add focused tests for adapter comparison and promotion logic

## Player Flow
1. Run the live loop with adapter Raven.
2. Optionally compare base Raven and adapter Raven on the same proof attempt.
3. Run comparison on the held-out eval file.
4. Promote the adapter if comparison metrics are good enough.
5. Continue data generation with the promoted Raven adapter.

## Non-goals
- Frontend
- PostgreSQL
- Vector database
- Web dashboard
- Multi-agent orchestration

## Acceptance Criteria
- `scripts/mystic_loop.py` accepts `--backend adapter`, `--adapter-path`, `--base-model`, and `--compare-raven`.
- `mystic/llm_client.py` includes `AdapterClient`.
- Adapter inference logs are appended and failed adapter outputs are saved separately.
- `scripts/compare_raven_models.py` saves base-vs-adapter metrics to `mystic_data/logs/raven_comparison_results.jsonl`.
- `scripts/promote_raven_adapter.py` updates the registry with `active`, `promoted_at`, `promotion_reason`, and `metrics_snapshot`.
- `configs/models.json` contains active Raven backend/base/adapter fields.

## Verification Plan
- Run unit tests for adapter comparison metrics, promotion logic, and adapter client helper behavior.
- Run the loop with patched clients in tests.
- Run comparison and promotion scripts against local files.
- Verify adapter backend warnings on macOS MPS/CPU.

## Reproduction Steps
1. Train or place a Raven adapter at `mystic_data/adapters/raven_lora_v0`.
2. Attempt to use it in the current live loop.
3. Observe that no adapter backend exists and comparison/promotion paths are missing.

## Actual Result
The trained Raven adapter cannot yet participate in the live self-improvement cycle.

## Expected Result
Mystic v3 uses the trained adapter inside the loop, compares it with the base Raven model, and can promote it in the registry.

## Environment
- Local macOS workspace
- Python 3.11
- `.venv-training` with `torch`, `transformers`, and `peft`
- MPS available, CUDA unavailable on the current machine

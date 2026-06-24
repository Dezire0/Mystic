# Issue #5: Add Mystic v2 Raven LoRA/QLoRA training pipeline

## Summary
Add a simple local-first training pipeline for the Raven critic adapter using `mystic_data/train_ready/raven_lora.jsonl` as the source and Hugging Face Transformers plus PEFT for LoRA/QLoRA training.

## Motivation
Mystic v1 can already collect Raven critique data and export LoRA-ready rows, but there is no concrete training path to turn those rows into a runnable Raven adapter.

## Current Behavior
- Raven critique rows can be exported, but there is no dedicated v2 data-preparation script for train/eval splits.
- There is no Raven-specific `train_raven_lora.py`, evaluation script, or model registration script matching the requested workflow.
- QLoRA capability is not audited explicitly for this machine.

## Expected Behavior
- Raven LoRA rows are validated and converted into instruction-tuning chat examples.
- Train and eval JSONL splits are generated locally.
- A simple LoRA/QLoRA script can train Raven adapters from those files.
- Unsupported QLoRA environments fail clearly instead of crashing obscurely.
- Adapter evaluation and metadata registration are available as separate scripts.

## Scope
- Add `scripts/prepare_raven_training_data.py`
- Add `scripts/train_raven_lora.py`
- Add `scripts/evaluate_raven_lora.py`
- Add `scripts/register_model.py`
- Add `configs/training_raven.json`
- Update `scripts/export_raven_lora.py`
- Update `README.md`
- Add targeted tests for the new Raven v2 pipeline

## Player Flow
1. Export Raven critique rows.
2. Prepare validated train/eval JSONL files.
3. Dry-run locally to validate tokenization and config.
4. Run real LoRA or QLoRA training in an appropriate environment.
5. Evaluate the adapter.
6. Register adapter metadata in `model_versions.json`.

## Non-goals
- Frontend
- PostgreSQL
- Vector database
- Web dashboard
- Multi-agent orchestration
- Automatic model uploads

## Acceptance Criteria
- `prepare_raven_training_data.py` writes `raven_train.jsonl` and `raven_eval.jsonl`.
- `train_raven_lora.py` supports the requested CLI flags and writes append-only training logs plus a config snapshot.
- `evaluate_raven_lora.py` computes verdict match, JSON validity rates, average output length, and failure counts.
- `register_model.py` appends adapter metadata to `mystic_data/metadata/model_versions.json`.
- `--qlora` fails gracefully on unsupported local Mac environments and explains that NVIDIA Linux GPU environments are the practical target.

## Verification Plan
- Run unit tests for preparation, registration, evaluation parsing, and dry-run planning.
- Run `export_raven_lora.py` and confirm `mystic_data/train_ready/raven_lora.jsonl` is produced.
- Run `prepare_raven_training_data.py` on a small sample.
- Run `train_raven_lora.py --dry-run` and confirm tokenization/config validation succeeds.
- Audit local training capabilities for CUDA, MPS, and bitsandbytes availability.

## Actual Result
Mystic lacks a concrete, inspectable Raven adapter training path.

## Expected Result
Mystic v2 includes a complete local-first Raven LoRA/QLoRA preparation, training, evaluation, and registration workflow.

## Environment
- Local macOS workspace
- Python 3.11
- `.venv-training` with `torch`, `transformers`, `datasets`, and `peft`
- `bitsandbytes` not currently available on this machine

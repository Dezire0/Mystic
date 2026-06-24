# mystic_data

This directory is reserved for dataset and training artifacts that should stay structurally separate from application source code.

## Layout

- `raw/`: downloaded or scraped source files
- `processed/`: normalized intermediate artifacts
- `verified/`: human or programmatically verified records
- `rejected/`: excluded or low-quality artifacts
- `needs_review/`: uncertain records pending review
- `train_ready/`: finalized JSONL shards ready for training
- `eval_holdout/`: holdout evaluation sets
- `exports/`: packaged dataset exports
- `models/`: base-model artifacts or local checkpoints
- `adapters/`: LoRA or QLoRA specialist adapters
- `logs/`: ingestion and training logs
- `metadata/`: schemas, manifests, and dataset bookkeeping


# Issue #3: Build Mystic v0 JSONL automatic research loop

## Summary
Build a Python 3.11 local JSONL-based automatic research loop for Mystic v0 with Numina sample download, mock proof generation, mock Raven critique, resumable processing, append-only logs, and LoRA export.

## Motivation
The current repository has broader training scaffolding, but the requested deliverable is a smaller and more direct `Mystic v0` loop that operates entirely on local JSONL files with no frontend and no database.

## Current Behavior
- The repository contains training and metadata scaffolds.
- There is no dedicated end-to-end JSONL-only research loop that downloads 100 Numina samples, processes them, classifies outcomes, and exports Raven LoRA data.

## Expected Behavior
- Local data folders are created automatically.
- `AI-MO/NuminaMath-CoT` samples are downloaded into JSONL.
- A resumable loop skips already processed IDs.
- Mock proof generation and Raven critique run for each sample.
- Results are classified as `VALID`, `INVALID`, `GAP`, or `NEEDS_MORE_DETAIL`.
- Append-only logs are written.
- `failed_proofs.jsonl`, `raven_critiques.jsonl`, and `raven_lora.jsonl` are produced.

## Scope
- Add `scripts/setup_mystic_data.py`
- Add `scripts/download_numina_sample.py`
- Add `scripts/mystic_loop.py`
- Add `scripts/export_raven_lora.py`
- Update `README.md` and `.gitignore`

## Acceptance Criteria
- Running the scripts in order creates a working local JSONL research loop.
- The loop is resumable and skips processed IDs.
- Logs are append-only.
- Raven LoRA export is generated from processed critique records.

## Verification Plan
- Run setup.
- Download 100 Numina samples.
- Run the loop twice and verify the second run skips previously processed IDs.
- Export `raven_lora.jsonl`.

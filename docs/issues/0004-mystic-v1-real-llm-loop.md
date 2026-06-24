# Issue #4: Connect Mystic v0 JSONL loop to real LLM backends

## Summary
Upgrade the existing Mystic v0 JSONL research loop so it uses real LLM backends for proof generation and Raven critique while staying local-first, append-only, resumable, and JSONL-only.

## Motivation
Mystic v0 proves out the append-only loop shape, but it still depends on mock generator and critic functions. The next practical step is to connect the loop to usable local and OpenAI-compatible inference backends without introducing extra infrastructure.

## Current Behavior
- `scripts/mystic_loop.py` uses mock proof generation and mock Raven classification.
- There is no dedicated v1 client layer for Ollama or OpenAI-compatible chat APIs.
- There is no robust Raven JSON parser for malformed model output.
- The loop does not yet persist raw model outputs, verified/rejected streams, or a per-item run log in the requested format.

## Expected Behavior
- Mystic can call a real local Ollama backend at `http://localhost:11434`.
- Mystic can call a real OpenAI-compatible backend configured entirely by environment variables.
- The loop remains resumable by skipping already processed IDs.
- Every processed item appends JSONL outputs and logs without overwriting prior runs.
- Bad model output never crashes the loop; it is captured and downgraded safely.

## Scope
- Add `mystic/llm_client.py`
- Add `mystic/prompts.py`
- Add `mystic/parsers.py`
- Add `mystic/schema.py`
- Add `configs/models.json`
- Refactor `scripts/mystic_loop.py`
- Update setup helpers, README, and tests as needed for v1 storage and verification

## Player Flow
1. Initialize `mystic_data/`.
2. Download Numina JSONL samples.
3. Run the loop against `ollama` or an OpenAI-compatible backend.
4. Save generator output, Raven critique, verdict, raw outputs, and append-only run logs.
5. Export Raven critique rows for future LoRA training.

## Non-goals
- Frontend
- PostgreSQL
- Vector database
- Web dashboard
- Training pipeline implementation

## Acceptance Criteria
- `scripts/mystic_loop.py` supports `--limit`, `--input`, `--run-id`, `--backend`, `--generator-model`, and `--raven-model`.
- `ollama` and `openai-compatible` backends both resolve model names from config and/or explicit arguments.
- Raven is prompted to return JSON only and malformed output is handled safely.
- `VALID` records append to `mystic_data/verified/`.
- `INVALID`, `GAP`, and `NEEDS_MORE_DETAIL` records append to `mystic_data/rejected/` and `mystic_data/internal/failed_proofs.jsonl`.
- Every processed item appends to `mystic_data/logs/run_log.jsonl`.
- The loop is resumable and skips already processed IDs.

## Verification Plan
- Run unit tests for parser behavior, loop resumability, and export shape.
- Run setup script and confirm required directories/files are created.
- Run the loop against a small sample with an injected/mock client in tests.
- Verify README commands for setup, Ollama run, and export are accurate.

## Reproduction Steps
1. Run the current v0 loop on a sample JSONL input.
2. Observe that proof generation and critique come from mock functions rather than a real backend.

## Actual Result
The pipeline shape exists, but no real model backend is used.

## Expected Result
The same append-only loop works with real Ollama and OpenAI-compatible models.

## Environment
- Local macOS workspace
- Python 3.11
- Existing `.venv-training` environment with `requests`, `httpx`, and `datasets`

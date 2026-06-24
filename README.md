# Mystic v3

Mystic v3 reinjects the trained Raven adapter into the live JSONL research loop and adds base-vs-adapter comparison plus promotion logic.

It keeps the design intentionally narrow:

- local folders under `mystic_data/`
- append-only JSONL storage
- resumable processing through `mystic_data/state/processed_ids.jsonl`
- no frontend
- no PostgreSQL
- no vector DB
- no web dashboard
- no multi-agent orchestration yet

## Files

- [scripts/setup_mystic_data.py](/Users/JYH/Documents/Mystic/scripts/setup_mystic_data.py)
- [scripts/download_numina_sample.py](/Users/JYH/Documents/Mystic/scripts/download_numina_sample.py)
- [scripts/mystic_loop.py](/Users/JYH/Documents/Mystic/scripts/mystic_loop.py)
- [scripts/export_raven_lora.py](/Users/JYH/Documents/Mystic/scripts/export_raven_lora.py)
- [scripts/prepare_raven_training_data.py](/Users/JYH/Documents/Mystic/scripts/prepare_raven_training_data.py)
- [scripts/train_raven_lora.py](/Users/JYH/Documents/Mystic/scripts/train_raven_lora.py)
- [scripts/evaluate_raven_lora.py](/Users/JYH/Documents/Mystic/scripts/evaluate_raven_lora.py)
- [scripts/register_model.py](/Users/JYH/Documents/Mystic/scripts/register_model.py)
- [scripts/compare_raven_models.py](/Users/JYH/Documents/Mystic/scripts/compare_raven_models.py)
- [scripts/promote_raven_adapter.py](/Users/JYH/Documents/Mystic/scripts/promote_raven_adapter.py)
- [mystic/llm_client.py](/Users/JYH/Documents/Mystic/mystic/llm_client.py)
- [mystic/prompts.py](/Users/JYH/Documents/Mystic/mystic/prompts.py)
- [mystic/parsers.py](/Users/JYH/Documents/Mystic/mystic/parsers.py)
- [mystic/raven_compare.py](/Users/JYH/Documents/Mystic/mystic/raven_compare.py)
- [mystic/schema.py](/Users/JYH/Documents/Mystic/mystic/schema.py)
- [mystic/raven_training.py](/Users/JYH/Documents/Mystic/mystic/raven_training.py)
- [configs/models.json](/Users/JYH/Documents/Mystic/configs/models.json)
- [configs/training_raven.json](/Users/JYH/Documents/Mystic/configs/training_raven.json)

## Data Layout

Running setup creates:

```text
mystic_data/
├── adapters/
├── eval_holdout/
├── exports/
├── internal/
├── logs/
├── processed/
├── raw/
├── rejected/
├── state/
├── train_ready/
└── verified/
```

Important files written by the loop:

- `mystic_data/raw/numina_math_cot_100.jsonl`
- `mystic_data/processed/mystic_loop_results.jsonl`
- `mystic_data/verified/verified.jsonl`
- `mystic_data/rejected/rejected.jsonl`
- `mystic_data/internal/failed_proofs.jsonl`
- `mystic_data/internal/raven_critiques.jsonl`
- `mystic_data/logs/run_log.jsonl`
- `mystic_data/logs/training_log.jsonl`
- `mystic_data/logs/raven_eval_results.jsonl`
- `mystic_data/logs/adapter_inference_log.jsonl`
- `mystic_data/logs/raven_comparison_results.jsonl`
- `mystic_data/logs/raven_promotion_log.jsonl`
- `mystic_data/state/processed_ids.jsonl`
- `mystic_data/exports/raven_lora.jsonl`
- `mystic_data/train_ready/raven_lora.jsonl`
- `mystic_data/train_ready/raven_train.jsonl`
- `mystic_data/eval_holdout/raven_eval.jsonl`
- `mystic_data/adapters/raven_lora_tiny_gpt2_smoke/`
- `mystic_data/adapters/raven_lora_v0/training_config.json`
- `mystic_data/internal/failed_adapter_outputs.jsonl`

## Setup

Use the existing Python 3.11 environment in this repo:

```bash
.venv-training/bin/python scripts/setup_mystic_data.py
.venv-training/bin/python scripts/download_numina_sample.py --limit 100
```

## Ollama Backend

Pull a local model:

```bash
ollama pull qwen2.5:7b
```

Run the loop with Ollama:

```bash
.venv-training/bin/python scripts/mystic_loop.py --limit 10 --backend ollama
```

Override models explicitly when needed:

```bash
.venv-training/bin/python scripts/mystic_loop.py --limit 20 --backend ollama --generator-model qwen2.5:7b --raven-model qwen2.5:7b
```

## OpenAI-Compatible Backend

Set environment variables:

```bash
export MYSTIC_API_BASE="http://localhost:8000/v1"
export MYSTIC_API_KEY="replace-me-or-leave-blank-for-local-servers"
export MYSTIC_GENERATOR_MODEL="Qwen/Qwen2.5-7B-Instruct"
export MYSTIC_RAVEN_MODEL="Qwen/Qwen2.5-7B-Instruct"
```

Run the loop:

```bash
.venv-training/bin/python scripts/mystic_loop.py --limit 10 --backend openai-compatible
```

`MYSTIC_API_KEY` is not hardcoded. If your local OpenAI-compatible server does not require auth, leave it blank.

## Export Raven LoRA Data

```bash
python scripts/export_raven_lora.py
```

This writes both:

- `mystic_data/exports/raven_lora.jsonl`
- `mystic_data/train_ready/raven_lora.jsonl`

## Mystic v2 Training

Check the adapter's recorded base model:

```bash
.venv-training/bin/python - <<'PY'
import json
from pathlib import Path
p = Path("mystic_data/adapters/raven_lora_tiny_gpt2_smoke/adapter_config.json")
cfg = json.loads(p.read_text())
print(cfg.get("base_model_name_or_path"))
PY
```

Smoke-test adapter commands:

```bash
.venv-training/bin/python scripts/evaluate_raven_lora.py \
  --base-model sshleifer/tiny-gpt2 \
  --adapter-path mystic_data/adapters/raven_lora_tiny_gpt2_smoke \
  --eval-file mystic_data/eval_holdout/raven_eval.jsonl \
  --limit 20
```

The smoke adapter is only for pipeline validation. The real Raven adapter target remains `mystic_data/adapters/raven_lora_v0`.

Prepare train and eval files:

```bash
.venv-training/bin/python scripts/export_raven_lora.py
.venv-training/bin/python scripts/prepare_raven_training_data.py --limit 500
```

Mac dry-run for data and tokenization only:

```bash
.venv-training/bin/python scripts/train_raven_lora.py \
  --dry-run \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --train-file mystic_data/train_ready/raven_train.jsonl \
  --eval-file mystic_data/eval_holdout/raven_eval.jsonl \
  --output-dir mystic_data/adapters/raven_lora_v0
```

GPU QLoRA training:

```bash
python scripts/train_raven_lora.py \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --train-file mystic_data/train_ready/raven_train.jsonl \
  --eval-file mystic_data/eval_holdout/raven_eval.jsonl \
  --output-dir mystic_data/adapters/raven_lora_v0 \
  --epochs 1 \
  --batch-size 1 \
  --learning-rate 0.0002 \
  --max-length 2048 \
  --qlora
```

Evaluate the adapter:

```bash
.venv-training/bin/python scripts/evaluate_raven_lora.py \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --adapter-path mystic_data/adapters/raven_lora_v0 \
  --eval-file mystic_data/eval_holdout/raven_eval.jsonl \
  --limit 100
```

Register the adapter:

```bash
python scripts/register_model.py \
  --model-id raven_lora_v0 \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --adapter-path mystic_data/adapters/raven_lora_v0
```

## GPU Environments

Real QLoRA should run on a Linux NVIDIA GPU environment. Typical options:

```bash
python scripts/train_raven_lora.py \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --train-file mystic_data/train_ready/raven_train.jsonl \
  --eval-file mystic_data/eval_holdout/raven_eval.jsonl \
  --output-dir mystic_data/adapters/raven_lora_v0 \
  --epochs 1 \
  --batch-size 1 \
  --learning-rate 0.0002 \
  --max-length 2048 \
  --qlora
```

Use the same command on:

- Colab with a CUDA runtime
- Kaggle notebooks with an NVIDIA GPU
- RunPod or another Linux GPU host

On macOS, `--qlora` will fail gracefully when `bitsandbytes` or CUDA is unavailable. Dry-run mode is intended for local inspection.

## Mystic v3 Reinjection

Run the loop with the trained Raven adapter:

```bash
.venv-training/bin/python scripts/mystic_loop.py \
  --limit 10 \
  --backend adapter \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --adapter-path mystic_data/adapters/raven_lora_v0
```

Compare base Raven vs adapter Raven:

```bash
python scripts/compare_raven_models.py \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --adapter-path mystic_data/adapters/raven_lora_v0 \
  --eval-file mystic_data/eval_holdout/raven_eval.jsonl \
  --limit 100
```

Promote the adapter:

```bash
python scripts/promote_raven_adapter.py \
  --model-id raven_lora_v0 \
  --comparison-log mystic_data/logs/raven_comparison_results.jsonl
```

If `raven_lora_v0` is not already present in `mystic_data/metadata/model_versions.json`, run the v2 registration step first.

Generate new data using the promoted Raven adapter:

```bash
python scripts/mystic_loop.py \
  --limit 50 \
  --backend adapter \
  --adapter-path mystic_data/adapters/raven_lora_v0 \
  --run-id raven_reinjection_v0
```

If you want side-by-side loop-time comparison on the same proof attempt:

```bash
python scripts/mystic_loop.py \
  --limit 10 \
  --backend adapter \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --adapter-path mystic_data/adapters/raven_lora_v0 \
  --compare-raven
```

## Self-Improvement Loop

The trained Raven adapter now sits directly inside the live research loop:

- the generator still produces proof attempts using the existing HTTP backend
- Raven can now critique with `base model + PEFT adapter`
- comparison logs measure whether the adapter is improving critique quality against the base Raven model
- promotion marks the adapter active in the model registry
- new adapter-generated critiques are still stored in `mystic_data/internal/raven_critiques.jsonl`
- those critiques can be exported again into `mystic_data/train_ready/` for the next training round

## Resume Behavior

Run the loop again with the same input to skip IDs already recorded in `mystic_data/state/processed_ids.jsonl`:

```bash
python scripts/mystic_loop.py --limit 10 --backend ollama
```

## Troubleshooting

- If `ollama` requests fail, confirm the daemon is running and `http://localhost:11434` is reachable.
- If the OpenAI-compatible backend fails immediately, verify `MYSTIC_API_BASE` is set correctly and includes the right host or `/v1` prefix.
- If Raven returns malformed JSON, the loop will classify that item as `NEEDS_MORE_DETAIL` and keep the raw output in JSONL instead of crashing.
- If `train_raven_lora.py --qlora` fails on macOS, that is expected on non-CUDA setups. Use dry-run locally and move real QLoRA to Linux GPU.
- If `mystic_loop.py --backend adapter` fails, confirm `mystic_data/adapters/raven_lora_v0` exists and contains a valid PEFT adapter.
- If adapter loading stops with an adapter/base-model mismatch error, read `adapter_config.json` and use the exact `base_model_name_or_path` it declares.
- If adapter inference is slow on macOS, that is expected on MPS or CPU. The loop will warn and continue.
- If your local Python is not the project training environment, replace `python` with `.venv-training/bin/python`.

## Verify

```bash
python -m unittest discover -s tests
```

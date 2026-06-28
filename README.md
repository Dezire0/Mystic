# Mystic v3

Mystic v3 reinjects the trained Raven adapter into the live JSONL research loop, adds base-vs-adapter comparison plus promotion logic, and now exposes a local Research Table / debate UX through the FastAPI app and MCP server.

It keeps the design intentionally narrow:

- local folders under `mystic_data/`
- append-only JSONL storage
- resumable processing through `mystic_data/state/processed_ids.jsonl`
- no separate JS frontend bundle
- no PostgreSQL
- no vector DB
- no standalone web dashboard service outside the FastAPI app
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
├── reports/
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
- `mystic_data/reports/execution_history.html`
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

## Deployment

Mystic's web UX is deployable on Vercel as a Python FastAPI app.

- Vercel uses the root [main.py](/Users/JYH/Documents/Mystic/main.py) entrypoint, which re-exports `mystic.app.main:app`.
- The repo pins the deployment runtime with [.python-version](/Users/JYH/Documents/Mystic/.python-version).
- `fastapi` is installed as a base dependency; `uvicorn` remains a local dev extra.

For local web serving:

```bash
python -m pip install -e '.[api]'
uvicorn mystic.app.main:app --host 127.0.0.1 --port 8765
```

## Discord Bot

Install the Discord bot dependency:

```bash
/opt/homebrew/Caskroom/miniforge/base/bin/python -m venv .venv-discord
.venv-discord/bin/python -m pip install -r requirements-discord.txt
```

Set environment variables:

```bash
export MYSTIC_DISCORD_TOKEN="your-bot-token"
export MYSTIC_DISCORD_GUILD_ID="optional-guild-id-for-fast-sync"
```

Or put them in `.env` at the project root. `scripts/run_discord_bot.py` now auto-loads `.env` before startup.

Run the bot:

```bash
.venv-discord/bin/python scripts/run_discord_bot.py --base-dir mystic_data
```

Use `/mystic` in Discord. The bot opens a DM and sends:

- 1-3 overview pages with all experts, progress percent, and running/waiting/failure status
- an expert detail page with progress bar, dataset, ETA, and latest failure log
- `/mystic_lab` runs the local research lab for a natural-language math question
- you can also send a plain DM to the bot, or mention the bot in a guild message, and it will answer without a slash command
- DM/mention research replies now send granular worklog-style progress updates as separate short messages before the final answer
- the research lab now uses light router selection, a separate Core planning stage, then selected-specialist method proposals, task redistribution, debate objections, revision, and Core synthesis instead of trusting a single specialist alone
- the research lab also includes CorePlan, Completeness, Counterexample, and Cost/Latency critics, plus an optional remote heavy-reasoning backend split when configured
- worklogs now show whether remote heavy reasoning is enabled and which backend/model each specialist actually used

`/mystic_lab` flow:

- question understanding
- router specialist selection
- Core initial planning
- CorePlan / Completeness / Counterexample / Cost-Latency critic
- selected-specialist method proposal
- Core task redistribution
- specialist task execution
- selected-specialist pairwise objection debate
- specialist revision
- Core synthesis
- conclusion drafting
- Raven critique to reduce unsupported claims

For plain-message replies, enable `MESSAGE CONTENT INTENT` in the Discord Developer Portal for the bot application. The runtime now enables `message_content` in code, but Discord must also allow it in the bot settings.

If the active Raven critic is configured as a local PEFT adapter but the Discord bot runtime does not have `torch`/`peft` installed, the research lab automatically falls back to the configured non-adapter Raven backend instead of failing the whole reply.

Run it persistently with launchd:

```bash
python scripts/manage_discord_bot_service.py install --base-dir mystic_data --guild-id "$MYSTIC_DISCORD_GUILD_ID"
python scripts/manage_discord_bot_service.py status --base-dir mystic_data
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

## Execution History Page

Build a single HTML page from the current execution logs:

```bash
.venv-training/bin/python scripts/render_execution_history_page.py
```

Outputs:

- `mystic_data/reports/execution_history.html`
- `mystic_data/reports/execution_history.json`

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

## Cycle Runner

The local cycle can now be run in two stages: `prepare` before GPU training and `finish` after you download the trained adapter tarball.

Prepare a cycle and build the GPU upload package:

```bash
.venv-training/bin/python scripts/run_mystic_cycle.py prepare \
  --cycle-id cycle_1 \
  --run-prepare-data \
  --train-limit 1000 \
  --eval-limit 100 \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --adapter-path mystic_data/adapters/raven_lora_v1 \
  --learning-rate 0.00015
```

This writes a tarball like `mystic_gpu_train_package_cycle_1.tar.gz` at the repo root and stores cycle artifacts under `mystic_data/cycles/cycle_1/`.

Mac dry-run before real GPU training:

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
  --output-dir mystic_data/adapters/raven_lora_v1 \
  --epochs 1 \
  --batch-size 1 \
  --learning-rate 0.00015 \
  --max-length 2048 \
  --qlora
```

Finish a cycle after downloading the adapter tarball:

```bash
.venv-training/bin/python scripts/run_mystic_cycle.py finish \
  --cycle-id cycle_1 \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --adapter-tar ~/Downloads/raven_lora_v1_qwen.tar.gz \
  --adapter-path mystic_data/adapters/raven_lora_v1 \
  --model-id raven_lora_v1_qwen_0_5b \
  --run-limit 20 \
  --compare-limit 10
```

What `finish` does automatically:

- checks that `adapter_config.json` exists
- checks that `adapter_model.safetensors` exists
- checks that `base_model_name_or_path` matches `--base-model`
- backs up and clears `mystic_data/state/processed_ids.jsonl`
- runs adapter reinjection through `scripts/mystic_loop.py`
- runs `scripts/compare_raven_models.py`
- verifies `adapter_better_or_equal_rate` exists in the comparison summary
- runs `scripts/register_model.py`
- appends cycle events and summaries without overwriting older JSONL logs

Evaluate the adapter explicitly:

```bash
.venv-training/bin/python scripts/evaluate_raven_lora.py \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --adapter-path mystic_data/adapters/raven_lora_v1 \
  --eval-file mystic_data/eval_holdout/raven_eval.jsonl \
  --limit 10
```

Reinject the adapter into the live loop directly:

```bash
.venv-training/bin/python scripts/mystic_loop.py \
  --limit 10 \
  --backend adapter \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --adapter-path mystic_data/adapters/raven_lora_v1 \
  --run-id qwen_raven_reinject_v1
```

Show current local cycle state:

```bash
.venv-training/bin/python scripts/run_mystic_cycle.py status \
  --limit 5
```

## Kaggle Automation

For free GPU automation, Mystic now supports a Kaggle CLI flow inside [scripts/run_mystic_cycle.py](/Users/JYH/Documents/Mystic/scripts/run_mystic_cycle.py).

Install the Kaggle CLI and place credentials at `~/.kaggle/kaggle.json` or set `KAGGLE_USERNAME` and `KAGGLE_KEY`:

```bash
python -m pip install kaggle
chmod 600 ~/.kaggle/kaggle.json
```

Prepare the package and train/eval data:

```bash
python scripts/run_mystic_cycle.py prepare \
  --cycle-id cycle_1 \
  --run-prepare-data \
  --train-limit 1000 \
  --eval-limit 100 \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --adapter-path mystic_data/adapters/raven_lora_v1 \
  --learning-rate 0.00015
```

Submit the prepared package to Kaggle:

```bash
python scripts/run_mystic_cycle.py submit \
  --cycle-id cycle_1 \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --adapter-path mystic_data/adapters/raven_lora_v1 \
  --learning-rate 0.00015
```

Poll the Kaggle kernel until it finishes:

```bash
python scripts/run_mystic_cycle.py poll \
  --cycle-id cycle_1 \
  --poll-seconds 60 \
  --timeout-minutes 240
```

Download the trained adapter artifact:

```bash
python scripts/run_mystic_cycle.py download --cycle-id cycle_1
```

Run the full Kaggle-backed cycle automatically:

```bash
python scripts/run_mystic_cycle.py full \
  --cycle-id cycle_1 \
  --run-prepare-data \
  --train-limit 1000 \
  --eval-limit 100 \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --adapter-path mystic_data/adapters/raven_lora_v1 \
  --model-id raven_lora_v1_qwen_0_5b \
  --learning-rate 0.00015 \
  --run-limit 20 \
  --compare-limit 10
```

The cycle directory stores:

- `prepare_summary.json`
- `kaggle_commands.md`
- `kaggle_submit_summary.json`
- `kaggle_poll_summary.json`
- `kaggle_download_summary.json`
- `summary.json`

Use the same command on:

- Colab with a CUDA runtime
- Kaggle notebooks with an NVIDIA GPU
- RunPod or another Linux GPU host

On macOS, `--qlora` will fail gracefully when `bitsandbytes` or CUDA is unavailable. Dry-run mode is intended for local inspection.

## Manifest Workflow

The repository also includes a checklist-derived workflow runner that follows the existing manifests instead of requiring manual step selection.

Run the full local preparation workflow:

```bash
.venv-training/bin/python scripts/run_manifest_workflow.py run \
  --workflow-id manifest_cycle_1 \
  --seed-internal \
  --max-hf-rows 3 \
  --numina-limit 1100 \
  --raven-prepare-limit 500 \
  --train-limit 1000 \
  --eval-limit 100 \
  --run-cycle-prepare \
  --cycle-id cycle_1 \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --adapter-path mystic_data/adapters/raven_lora_v1 \
  --learning-rate 0.00015
```

What this workflow does:

- initializes local internal Mystic data files
- optionally seeds internal example records
- resolves checklist-linked Hugging Face datasets
- downloads public dataset samples into `mystic_data/raw/`
- grows the local Numina cache
- exports Raven critique data
- prepares Raven train/eval JSONL files
- prepares specialist train-ready JSONL files
- generates training plans for every target in `mystic_data/metadata/manifests/training_manifest.json`
- optionally prepares the Kaggle Raven cycle package

Show the latest workflow summary:

```bash
.venv-training/bin/python scripts/run_manifest_workflow.py status --limit 5
```

The workflow writes its summary to:

- `mystic_data/workflows/<workflow_id>/summary.json`

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

## Power Behavior

Persistent local training and remote cycle services can be installed with the launchd helpers:

```bash
python scripts/manage_continuous_training.py install
python scripts/manage_remote_cycle_service.py install
```

By default these services run under `/usr/bin/caffeinate -i -s` so macOS idle/system sleep does not pause training while the machine stays powered on.

- This helps with screen-off / idle sleep.
- `RunAtLoad` and `KeepAlive` make the services restart after login or reboot.
- A completely powered-off Mac cannot keep running local training jobs; it can only resume after boot.
- If you explicitly want sleep to be allowed, install with `--allow-system-sleep`.

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

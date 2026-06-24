# Training Setup

Use this document when moving from dataset bootstrap to actual specialist adapter training.

## 1. Install dependencies

Base stack:

```bash
PYTHON_BIN=python3.11 bash scripts/install_training_deps.sh base
```

If `python3.11` cannot create a virtualenv on the machine, fall back to:

```bash
PYTHON_BIN=python3 bash scripts/install_training_deps.sh base
```

Unsloth path:

```bash
PYTHON_BIN=python3.11 bash scripts/install_training_deps.sh unsloth
```

Axolotl path:

```bash
PYTHON_BIN=python3.11 bash scripts/install_training_deps.sh axolotl
```

This creates `.venv-training/` by default. To change the virtualenv path:

```bash
PYTHON_BIN=python3.11 VENV_DIR=.venv-raven bash scripts/install_training_deps.sh base
```

## 2. Verify environment

```bash
python3 scripts/check_training_env.py
```

Inside the virtualenv, prefer:

```bash
source .venv-training/bin/activate
python scripts/check_training_env.py
```

`recommended_backends.unsloth` or `recommended_backends.axolotl` must be `true` before attempting that backend.

## 3. Prepare data

```bash
python3 scripts/bootstrap_training_workspace.py
python3 scripts/seed_internal_examples.py
python3 scripts/prepare_train_ready.py
```

## 4. Plan a training job

```bash
python3 scripts/plan_training_run.py --agent raven
```

## 5. Run a dry-run job manifest

```bash
python3 scripts/run_specialist_training.py --agent raven
```

## 6. Execute a backend job

Manual placeholder:

```bash
python3 scripts/run_specialist_training.py --agent raven --backend manual --execute
```

When the environment satisfies a real backend:

```bash
python3 scripts/run_specialist_training.py --agent raven --backend unsloth --execute
```

or

```bash
python3 scripts/run_specialist_training.py --agent raven --backend axolotl --execute
```

The current repository records each job under `mystic_data/logs/training_jobs/`.

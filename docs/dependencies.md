# Dependencies and requirements files

`pyproject.toml` (with `uv.lock`) is the canonical definition of the application
and its dev tooling. The `requirements-*.txt` files are **not** redundant: scripts
and tests refer to them by name, so do not delete or rename them without updating
the callers listed below.

| File | Used by | Purpose |
| --- | --- | --- |
| `pyproject.toml` / `uv.lock` | CI, local dev | Core deps (`fastapi`, `requests`) and extras: `api`, `dev`, `discord`, `lightning` |
| `requirements.txt` | (no in-repo caller found) | Mirrors the core runtime deps. Note it lacks the `fastapi<0.116` upper bound that `pyproject.toml` has |
| `requirements-training.txt` | `scripts/install_training_deps.sh`, `scripts/run_mystic_cycle.py`, `tests/test_run_mystic_cycle.py` | Base training stack (torch, transformers, peft, trl, ...) |
| `requirements-unsloth.txt` | `scripts/install_training_deps.sh`, `scripts/run_mystic_cycle.py` | Unsloth training variant |
| `requirements-axolotl.txt` | `scripts/install_training_deps.sh`, `scripts/run_mystic_cycle.py` | Axolotl training variant |
| `requirements-discord.txt` | `scripts/run_discord_bot.py` (error message) | Discord bot dependency |

## Running the tests

```bash
python -m pip install -e ".[dev,api]"
python -m pytest -q
```

## Known CI gaps

CI (`.github/workflows/ci.yml`) deselects two tests that only pass on the original
author's machine. Making them portable is a follow-up, not part of this change:

- `tests/test_run_manifest_workflow.py::...::test_load_training_targets_returns_priority_order`
  reads a committed manifest containing absolute `/Users/JYH/Documents/Mystic/...`
  paths (also present in several files under `mystic_data/metadata/`).
- `tests/test_engine_runner_launchd.py::...::test_service_definition_uses_validated_persistent_root`
  is macOS launchd specific.

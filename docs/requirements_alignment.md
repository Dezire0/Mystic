# Requirements Alignment

This note tracks how the current scaffold maps to `mystic_requirements_checklist.md`.

## Already aligned

- Repository skeleton under `mystic/`, `configs/`, `scripts/`, `tests/`, `data/`
- Separate specialist agent classes, prompts, config entries, archive records, and dataset export paths
- Local-first archive with SQLite
- CLI-first execution path
- Basic FastAPI surface
- Initial dataset export mechanism
- `mystic_data/` workspace directories

## Intentionally partial in v0.1 scaffold

- Dataset collection pipelines are not implemented yet
- Real provider integration is scaffolded but defaults to `mock`
- `Typer`, `SQLAlchemy`, `Pydantic`, `SymPy`, `Z3`, `Lean`, `DVC`, and training stack are not wired yet
- Remote GPU burst automation is not implemented yet
- Knowledge graph and simulator remain explicit stubs

## Next build priorities

1. Replace the custom YAML subset loader with a standard parser once dependency policy is fixed.
2. Add `Pydantic` request and archive schemas.
3. Add `Typer` CLI and `SQLAlchemy` archive layer if the project standardizes on those tools.
4. Build `mystic_data/metadata` schemas for `failed_proofs`, `raven_critiques`, `forge_experiments`, `lean_attempts`, and `routing_logs`.
5. Add first-pass dataset ingestion scripts for Internal Mystic Data and top-priority open math corpora.


from __future__ import annotations

import hashlib
import json
import platform
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def payload_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def record(*, engine_id: str, engine_version: str, normalized_input: dict[str, Any], output: dict[str, Any], deterministic: bool, seed: int | None, backend: str, started_at: str, completed_at: str, duration_ms: int, resource_limits: dict[str, Any], links: dict[str, str], warnings: list[str], assumptions: list[str]) -> dict[str, Any]:
    level = "exact" if deterministic else ("seeded" if seed is not None else "environment_dependent")
    return {
        "level": level,
        "engine_id": engine_id,
        "engine_version": engine_version,
        "plugin_source_classification": "built_in_allowlist",
        "normalized_input": normalized_input,
        "input_hash": payload_hash(normalized_input),
        "output_hash": payload_hash(output),
        "seed": seed,
        "deterministic": deterministic,
        "execution_backend": backend,
        "python_version": platform.python_version(),
        "dependency_fingerprint": "stdlib-and-locked-mystic-runtime",
        "started_at": started_at,
        "completed_at": completed_at,
        "duration_ms": duration_ms,
        "resource_limits": resource_limits,
        "runner_version": "phase2a-1",
        "warnings": warnings,
        "assumptions": assumptions,
        **links,
    }

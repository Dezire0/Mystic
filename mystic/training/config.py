"""Training config helpers."""

from __future__ import annotations

import json
from pathlib import Path


def load_training_config(root_path: str | Path, agent: str) -> dict:
    root = Path(root_path)
    config_path = root / "configs" / "training" / f"{_config_name(agent)}.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload["config_path"] = str(config_path)
    return payload


def load_runtime_defaults(root_path: str | Path) -> dict:
    root = Path(root_path)
    path = root / "configs" / "training" / "runtime_defaults.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _config_name(agent: str) -> str:
    if agent == "core":
        return "core_router_lora_v0"
    return f"{agent}_lora_v0"


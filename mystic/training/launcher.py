"""Training launcher planning helpers."""

from __future__ import annotations

import json
from pathlib import Path
import sys

from mystic.training.config import load_training_config

def build_training_plan(root_path: str | Path, agent: str) -> dict[str, object]:
    root = Path(root_path)
    config = load_training_config(root, agent)
    train_ready_path = root / config["train_ready_path"]
    source_manifest = root / config["source_manifest"]

    return {
        "agent": config["agent"],
        "adapter_name": config["adapter_name"],
        "base_model": config["base_model"],
        "method": config["method"],
        "train_ready_path": str(train_ready_path),
        "source_manifest": str(source_manifest),
        "output_dir": str(root / config["output_dir"]),
        "command_preview": _command_preview(config, sys.executable),
        "python_executable": sys.executable,
        "smoke_model": config.get("smoke_model"),
        "config_path": config["config_path"],
        "ready": train_ready_path.exists() and source_manifest.exists(),
    }


def _command_preview(config: dict, python_executable: str) -> list[str]:
    return [
        python_executable,
        "-m",
        "mystic.training.run",
        "--agent",
        config["agent"],
        "--config",
        f"configs/training/{Path(config['output_dir']).name}.json",
    ]

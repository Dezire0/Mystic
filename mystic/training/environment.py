"""Environment audit helpers for specialist training."""

from __future__ import annotations

import importlib.util
import shutil


PYTHON_PACKAGES = [
    "torch",
    "transformers",
    "peft",
    "trl",
    "datasets",
]

OPTIONAL_PACKAGES = [
    "unsloth",
    "axolotl",
    "wandb",
    "mlflow",
]

SYSTEM_BINARIES = [
    "git",
    "docker",
    "ollama",
    "lean",
    "z3",
]


def audit_training_environment() -> dict[str, object]:
    packages = {name: _has_module(name) for name in PYTHON_PACKAGES}
    optional = {name: _has_module(name) for name in OPTIONAL_PACKAGES}
    binaries = {name: shutil.which(name) is not None for name in SYSTEM_BINARIES}

    recommended_backends = {
        "unsloth": packages["torch"] and packages["transformers"] and packages["peft"] and optional["unsloth"],
        "axolotl": packages["torch"] and packages["transformers"] and packages["peft"] and optional["axolotl"],
        "manual": True,
    }
    return {
        "packages": packages,
        "optional_packages": optional,
        "binaries": binaries,
        "recommended_backends": recommended_backends,
    }


def _has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


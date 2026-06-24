"""Training job planning and execution helpers."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import subprocess
import sys

from mystic.training.environment import audit_training_environment
from mystic.training.launcher import build_training_plan


def execute_training_job(
    root_path: str | Path,
    agent: str,
    backend: str = "manual",
    dry_run: bool = True,
) -> dict[str, object]:
    root = Path(root_path)
    plan = build_training_plan(root, agent)
    env = audit_training_environment()
    command = build_backend_command(plan, backend, dry_run=dry_run)
    job_manifest = record_training_job(root, plan, backend, command, dry_run)

    if dry_run:
        return {
            "plan": plan,
            "environment": env,
            "backend": backend,
            "command": command,
            "job_manifest": str(job_manifest),
            "executed": False,
        }

    if backend != "manual" and not env["recommended_backends"].get(backend, False):
        raise RuntimeError(f"Backend '{backend}' is not available in the current environment")

    completed = subprocess.run(
        command,
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "plan": plan,
        "environment": env,
        "backend": backend,
        "command": command,
        "job_manifest": str(job_manifest),
        "executed": True,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def build_backend_command(plan: dict[str, object], backend: str, dry_run: bool = True) -> list[str]:
    python_executable = str(plan.get("python_executable", sys.executable))
    if backend == "manual":
        return [
            python_executable,
            "-m",
            "mystic.training.run",
            "--agent",
            str(plan["agent"]),
            *(["--dry-run"] if dry_run else ["--execute"]),
        ]
    if backend == "unsloth":
        return [
            python_executable,
            "scripts/train_lora_placeholder.py",
            "--agent",
            str(plan["agent"]),
            "--backend",
            "unsloth",
        ]
    if backend == "axolotl":
        return [
            python_executable,
            "scripts/train_lora_placeholder.py",
            "--agent",
            str(plan["agent"]),
            "--backend",
            "axolotl",
        ]
    raise KeyError(f"Unsupported backend: {backend}")


def record_training_job(
    root_path: str | Path,
    plan: dict[str, object],
    backend: str,
    command: list[str],
    dry_run: bool,
) -> Path:
    root = Path(root_path)
    logs_root = root / "mystic_data" / "logs" / "training_jobs"
    logs_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = logs_root / f"{plan['agent']}-{backend}-{timestamp}.json"
    payload = {
        "created_at": timestamp,
        "agent": plan["agent"],
        "adapter_name": plan["adapter_name"],
        "backend": backend,
        "dry_run": dry_run,
        "base_model": plan["base_model"],
        "train_ready_path": plan["train_ready_path"],
        "source_manifest": plan["source_manifest"],
        "output_dir": plan["output_dir"],
        "command": command,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return path

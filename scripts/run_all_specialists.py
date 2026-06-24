from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.execution_history import write_execution_history_outputs
from mystic.training.architecture_bootstrap import bootstrap_architecture_train_ready
from mystic.training.blueprints import AGENT_DIVISIONS

EXCLUDED_AGENTS = {"archive", "knowledge_graph", "evolution", "smt"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run local smoke specialist training across all configured Mystic specialist adapters."
    )
    parser.add_argument(
        "--agents",
        nargs="*",
        default=[],
        help="Optional subset of agents to run. Defaults to every configured trainable specialist.",
    )
    parser.add_argument(
        "--backend",
        default="manual",
        choices=["manual", "unsloth", "axolotl"],
        help="Training backend passed to scripts/run_specialist_training.py",
    )
    parser.add_argument(
        "--rows-per-agent",
        type=int,
        default=3,
        help="Bootstrap rows per missing architecture specialist.",
    )
    parser.add_argument(
        "--skip-bootstrap",
        action="store_true",
        help="Skip generating missing architecture train_ready files before the batch run.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop after the first training failure.",
    )
    parser.add_argument("--epochs", type=int, default=0)
    parser.add_argument("--max-steps", type=int, default=0)
    parser.add_argument("--learning-rate", type=float, default=0.0)
    parser.add_argument("--sequence-length", type=int, default=0)
    return parser


def discover_configured_agents(root: Path) -> list[str]:
    config_root = root / "configs" / "training"
    agents: list[str] = []
    for path in sorted(config_root.glob("*.json")):
        if path.name == "runtime_defaults.json":
            continue
        if path.name == "core_router_lora_v0.json":
            agents.append("core")
            continue
        if not path.name.endswith("_lora_v0.json"):
            continue
        agents.append(path.stem.removesuffix("_lora_v0"))
    return [agent for agent in agents if agent not in EXCLUDED_AGENTS]


def timestamp_now() -> str:
    return datetime.now(UTC).isoformat()


def batch_summary_path(root: Path) -> Path:
    reports_dir = root / "mystic_data" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    return reports_dir / "specialist_training_batch_run.json"


def write_batch_summary(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def run_agent(
    root: Path,
    agent: str,
    backend: str,
    *,
    epochs: int,
    max_steps: int,
    learning_rate: float,
    sequence_length: int,
) -> dict[str, Any]:
    command = [
        sys.executable,
        "scripts/run_specialist_training.py",
        "--agent",
        agent,
        "--backend",
        backend,
        "--execute",
    ]
    if epochs:
        command.extend(["--epochs", str(epochs)])
    if max_steps:
        command.extend(["--max-steps", str(max_steps)])
    if learning_rate:
        command.extend(["--learning-rate", str(learning_rate)])
    if sequence_length:
        command.extend(["--sequence-length", str(sequence_length)])
    started = datetime.now(UTC)
    completed = subprocess.run(
        command,
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    finished = datetime.now(UTC)
    return {
        "agent": agent,
        "division": AGENT_DIVISIONS.get(agent, "unknown"),
        "backend": backend,
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_seconds": max((finished - started).total_seconds(), 0.0),
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    agents = args.agents or discover_configured_agents(ROOT)
    summary_file = batch_summary_path(ROOT)
    results: list[dict[str, Any]] = []

    bootstrap_payload: dict[str, Any] | None = None
    if not args.skip_bootstrap:
        bootstrap_payload = bootstrap_architecture_train_ready(
            ROOT / "mystic_data",
            rows_per_agent=args.rows_per_agent,
        )

    write_batch_summary(summary_file, results)
    write_execution_history_outputs(ROOT / "mystic_data")

    for agent in agents:
        result = run_agent(
            ROOT,
            agent,
            args.backend,
            epochs=args.epochs,
            max_steps=args.max_steps,
            learning_rate=args.learning_rate,
            sequence_length=args.sequence_length,
        )
        results.append(result)
        write_batch_summary(summary_file, results)
        write_execution_history_outputs(ROOT / "mystic_data")
        if args.fail_fast and result["returncode"] != 0:
            break

    payload = {
        "timestamp": timestamp_now(),
        "backend": args.backend,
        "agents": agents,
        "bootstrap": bootstrap_payload,
        "summary_file": str(summary_file),
        "result_count": len(results),
        "success_count": sum(1 for row in results if int(row["returncode"]) == 0),
        "failure_count": sum(1 for row in results if int(row["returncode"]) != 0),
        "history_outputs": write_execution_history_outputs(ROOT / "mystic_data"),
        "results": results,
    }
    print(json.dumps(payload, indent=2))
    return 0 if payload["failure_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

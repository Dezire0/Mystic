from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.execution_history import write_execution_history_outputs


DEFAULT_SLUGS = [
    "openmathinstruct_1",
    "openmathinstruct_2",
    "openr1_mixture_of_thoughts",
    "openthoughts",
    "proofnet",
]


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run repeated overnight real-data specialist training batches.")
    parser.add_argument("--run-id", default=f"overnight_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}")
    parser.add_argument("--base-dir", default=str(ROOT / "mystic_data"))
    parser.add_argument("--iterations", type=int, default=4)
    parser.add_argument("--sleep-seconds", type=int, default=30)
    parser.add_argument("--hf-max-rows", type=int, default=200)
    parser.add_argument("--hf-slugs", nargs="*", default=DEFAULT_SLUGS)
    parser.add_argument("--numina-limit", type=int, default=3000)
    parser.add_argument("--public-max-rows-per-agent", type=int, default=300)
    parser.add_argument("--backend", choices=["manual", "unsloth", "axolotl"], default="manual")
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--max-steps", type=int, default=20)
    parser.add_argument("--learning-rate", type=float, default=0.00015)
    parser.add_argument("--sequence-length", type=int, default=512)
    parser.add_argument("--step-timeout-seconds", type=int, default=1800)
    parser.add_argument("--continue-on-error", action="store_true")
    return parser


def run_json_command(command: list[str], *, timeout: int) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return {
        "command": command,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def extract_last_json_object(stdout: str) -> dict[str, Any]:
    lines = [line.rstrip() for line in stdout.splitlines() if line.strip()]
    for index in range(len(lines)):
        candidate = "\n".join(lines[index:])
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    base_dir = Path(args.base_dir)
    run_dir = base_dir / "overnight_runs" / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "run_id": args.run_id,
        "started_at": now_iso(),
        "options": {
            "iterations": args.iterations,
            "sleep_seconds": args.sleep_seconds,
            "hf_max_rows": args.hf_max_rows,
            "hf_slugs": args.hf_slugs,
            "numina_limit": args.numina_limit,
            "public_max_rows_per_agent": args.public_max_rows_per_agent,
            "backend": args.backend,
            "epochs": args.epochs,
            "max_steps": args.max_steps,
            "learning_rate": args.learning_rate,
            "sequence_length": args.sequence_length,
            "step_timeout_seconds": args.step_timeout_seconds,
            "continue_on_error": args.continue_on_error,
        },
        "iterations": [],
    }

    for iteration in range(1, args.iterations + 1):
        started_at = now_iso()
        effective_numina_limit = args.numina_limit * iteration
        effective_hf_rows = args.hf_max_rows * iteration
        effective_public_rows = args.public_max_rows_per_agent * iteration
        iteration_payload: dict[str, Any] = {
            "iteration": iteration,
            "started_at": started_at,
            "effective_numina_limit": effective_numina_limit,
            "effective_hf_rows": effective_hf_rows,
            "effective_public_max_rows_per_agent": effective_public_rows,
            "steps": [],
        }

        commands = [
            [
                sys.executable,
                "scripts/download_numina_sample.py",
                "--limit",
                str(effective_numina_limit),
            ],
            [
                sys.executable,
                "scripts/prepare_public_train_ready.py",
                "--max-rows-per-agent",
                str(effective_public_rows),
                "--overwrite",
            ],
            [
                sys.executable,
                "scripts/run_all_specialists.py",
                "--backend",
                args.backend,
                "--skip-bootstrap",
                "--epochs",
                str(args.epochs),
                "--max-steps",
                str(args.max_steps),
                "--learning-rate",
                str(args.learning_rate),
                "--sequence-length",
                str(args.sequence_length),
            ],
        ]
        for slug in args.hf_slugs:
            commands.insert(
                1,
                [
                    sys.executable,
                    "scripts/download_hf_samples.py",
                    "--max-rows",
                    str(effective_hf_rows),
                    "--slugs",
                    slug,
                ],
            )

        for step_index, command in enumerate(commands, start=1):
            stdout_log = run_dir / "logs" / f"iteration_{iteration:03d}_step_{step_index:02d}.stdout.log"
            stderr_log = run_dir / "logs" / f"iteration_{iteration:03d}_step_{step_index:02d}.stderr.log"
            try:
                result = run_json_command(command, timeout=args.step_timeout_seconds)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                stdout = getattr(exc, "stdout", "") or ""
                stderr = getattr(exc, "stderr", "") or ""
                write_text(stdout_log, stdout)
                write_text(stderr_log, stderr)
                step_payload = {
                    "command": command,
                    "ok": False,
                    "error": repr(exc),
                    "stdout_log": str(stdout_log),
                    "stderr_log": str(stderr_log),
                    "parsed": extract_last_json_object(stdout),
                }
                iteration_payload["steps"].append(step_payload)
                write_json(run_dir / f"iteration_{iteration:03d}.json", iteration_payload)
                if not args.continue_on_error:
                    summary["iterations"].append(iteration_payload)
                    summary["aborted_at"] = now_iso()
                    summary["history_outputs"] = write_execution_history_outputs(base_dir)
                    write_json(run_dir / "summary.json", summary)
                    print(json.dumps(summary, indent=2))
                    return 1
                continue

            write_text(stdout_log, result["stdout"])
            write_text(stderr_log, result["stderr"])
            step_payload = {
                "command": command,
                "ok": True,
                "stdout_log": str(stdout_log),
                "stderr_log": str(stderr_log),
                "parsed": extract_last_json_object(result["stdout"]),
            }
            iteration_payload["steps"].append(step_payload)
            write_json(run_dir / f"iteration_{iteration:03d}.json", iteration_payload)

        iteration_payload["finished_at"] = now_iso()
        summary["iterations"].append(iteration_payload)
        summary["history_outputs"] = write_execution_history_outputs(base_dir)
        write_json(run_dir / "summary.json", summary)

        if iteration < args.iterations and args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)

    summary["finished_at"] = now_iso()
    summary["history_outputs"] = write_execution_history_outputs(base_dir)
    write_json(run_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

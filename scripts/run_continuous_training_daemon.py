from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.execution_history import write_execution_history_outputs
from mystic.training.continuous import (
    LAUNCHD_LABEL,
    append_jsonl,
    continuous_cycle_details_dir,
    continuous_cycle_log_path,
    continuous_state_path,
    default_rotation_slugs,
    normalize_rotation_slugs,
    now_iso,
    read_json,
    write_continuous_status_outputs,
    write_json,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Mystic continuous multi-dataset training forever.")
    parser.add_argument("--base-dir", default=str(ROOT / "mystic_data"))
    parser.add_argument("--backend", choices=["manual", "unsloth", "axolotl"], default="manual")
    parser.add_argument("--cycle-sleep-seconds", type=int, default=0)
    parser.add_argument("--error-sleep-seconds", type=int, default=60)
    parser.add_argument("--hf-base-rows", type=int, default=25)
    parser.add_argument("--numina-base-limit", type=int, default=1500)
    parser.add_argument("--public-base-rows-per-agent", type=int, default=50)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--max-steps", type=int, default=20)
    parser.add_argument("--learning-rate", type=float, default=0.00015)
    parser.add_argument("--sequence-length", type=int, default=512)
    parser.add_argument("--step-timeout-seconds", type=int, default=600)
    parser.add_argument("--cycle-timeout-seconds", type=int, default=7200)
    parser.add_argument("--hf-slugs", nargs="*", default=default_rotation_slugs())
    parser.add_argument("--once", action="store_true")
    return parser


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


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_state(base_dir: Path, slugs: list[str]) -> dict[str, Any]:
    normalized_slugs = normalize_rotation_slugs(base_dir, slugs)
    path = continuous_state_path(base_dir)
    if path.exists():
        state = read_json(path)
        state["rotation_slugs"] = normalized_slugs
        return state
    return {
        "status": "idle",
        "service_label": LAUNCHD_LABEL,
        "started_at": now_iso(),
        "last_heartbeat": now_iso(),
        "rotation_slugs": normalized_slugs,
        "current_cycle": 0,
        "completed_cycles": 0,
        "next_dataset_index": 0,
        "active_slug": "",
        "next_slug": normalized_slugs[0] if normalized_slugs else "",
        "last_error": "",
    }


def persist_state(base_dir: Path, state: dict[str, Any]) -> None:
    state["last_heartbeat"] = now_iso()
    write_json(continuous_state_path(base_dir), state)
    write_continuous_status_outputs(base_dir, state)
    write_execution_history_outputs(base_dir)


def tier_for_cycle(cycle_number: int, rotation_size: int) -> int:
    if rotation_size <= 0:
        return 1
    return 1 + ((cycle_number - 1) // rotation_size)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    base_dir = Path(args.base_dir)
    slugs = normalize_rotation_slugs(base_dir, args.hf_slugs or default_rotation_slugs())
    details_dir = continuous_cycle_details_dir(base_dir)
    details_dir.mkdir(parents=True, exist_ok=True)
    cycle_log = continuous_cycle_log_path(base_dir)

    stop_requested = {"value": False}

    def handle_stop(_signum: int, _frame: Any) -> None:
        stop_requested["value"] = True

    signal.signal(signal.SIGTERM, handle_stop)
    signal.signal(signal.SIGINT, handle_stop)

    state = load_state(base_dir, slugs)
    state["status"] = "running"
    state["pid"] = os.getpid()
    persist_state(base_dir, state)

    while not stop_requested["value"]:
        cycle_number = int(state.get("completed_cycles", 0) or 0) + 1
        queue_index = int(state.get("next_dataset_index", 0) or 0)
        active_slug = slugs[queue_index % len(slugs)] if slugs else ""
        next_slug = slugs[(queue_index + 1) % len(slugs)] if slugs else ""
        tier = tier_for_cycle(cycle_number, len(slugs))
        effective_hf_rows = max(int(args.hf_base_rows) * tier, int(args.hf_base_rows))
        effective_numina_limit = max(int(args.numina_base_limit) * tier, int(args.numina_base_limit))
        effective_public_rows = max(int(args.public_base_rows_per_agent) * tier, int(args.public_base_rows_per_agent))
        run_id = f"continuous_cycle_{cycle_number:06d}_{active_slug or 'none'}"

        state.update(
            {
                "status": "running",
                "current_cycle": cycle_number,
                "active_slug": active_slug,
                "next_slug": next_slug,
                "current_run_id": run_id,
                "last_error": "",
                "cycle_started_at": now_iso(),
            }
        )
        persist_state(base_dir, state)

        command = [
            sys.executable,
            "scripts/run_overnight_training.py",
            "--run-id",
            run_id,
            "--iterations",
            "1",
            "--sleep-seconds",
            "0",
            "--hf-max-rows",
            str(effective_hf_rows),
            "--hf-slugs",
            active_slug,
            "--numina-limit",
            str(effective_numina_limit),
            "--public-max-rows-per-agent",
            str(effective_public_rows),
            "--backend",
            args.backend,
            "--epochs",
            str(args.epochs),
            "--max-steps",
            str(args.max_steps),
            "--learning-rate",
            str(args.learning_rate),
            "--sequence-length",
            str(args.sequence_length),
            "--step-timeout-seconds",
            str(args.step_timeout_seconds),
            "--continue-on-error",
            "--run-label",
            run_id,
        ]

        started_at = now_iso()
        cycle_detail_path = details_dir / f"cycle_{cycle_number:06d}.json"
        stdout_log = details_dir / f"cycle_{cycle_number:06d}.stdout.log"
        stderr_log = details_dir / f"cycle_{cycle_number:06d}.stderr.log"
        success = False
        returncode: int | None = None
        parsed_summary: dict[str, Any] = {}
        error_message = ""
        try:
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            launched_at = time.monotonic()
            while True:
                polled = process.poll()
                if polled is not None:
                    stdout_text, stderr_text = process.communicate()
                    returncode = int(polled)
                    write_text(stdout_log, stdout_text)
                    write_text(stderr_log, stderr_text)
                    parsed_summary = extract_last_json_object(stdout_text)
                    success = returncode == 0
                    if not success:
                        error_message = stderr_text.strip() or f"child_returncode={returncode}"
                    break

                if stop_requested["value"]:
                    process.terminate()
                    stdout_text, stderr_text = process.communicate(timeout=30)
                    process_returncode = process.returncode
                    returncode = 1 if process_returncode is None else int(process_returncode)
                    write_text(stdout_log, stdout_text)
                    write_text(stderr_log, stderr_text)
                    parsed_summary = extract_last_json_object(stdout_text)
                    success = False
                    error_message = "stop_requested"
                    break

                if time.monotonic() - launched_at > args.cycle_timeout_seconds:
                    process.kill()
                    stdout_text, stderr_text = process.communicate()
                    write_text(stdout_log, stdout_text)
                    write_text(stderr_log, stderr_text)
                    error_message = f"cycle_timeout_after_{args.cycle_timeout_seconds}s"
                    success = False
                    returncode = None
                    break

                state["status"] = "running"
                persist_state(base_dir, state)
                time.sleep(10)
        except Exception as exc:  # pragma: no cover
            error_message = repr(exc)
            success = False

        finished_at = now_iso()
        cycle_detail = {
            "timestamp": finished_at,
            "cycle_number": cycle_number,
            "started_at": started_at,
            "finished_at": finished_at,
            "active_slug": active_slug,
            "next_slug": next_slug,
            "tier": tier,
            "effective_hf_rows": effective_hf_rows,
            "effective_numina_limit": effective_numina_limit,
            "effective_public_rows": effective_public_rows,
            "command": command,
            "returncode": returncode,
            "success": success,
            "status": "CYCLE_OK" if success else "CYCLE_ERROR",
            "error": error_message,
            "stdout_log": str(stdout_log),
            "stderr_log": str(stderr_log),
            "parsed_summary": parsed_summary,
        }
        write_json(cycle_detail_path, cycle_detail)
        append_jsonl(cycle_log, cycle_detail)

        state.update(
            {
                "completed_cycles": cycle_number,
                "next_dataset_index": queue_index + 1,
                "last_completed_cycle": cycle_number,
                "last_finished_at": finished_at,
                "last_cycle_detail": str(cycle_detail_path),
                "last_successful_cycle": cycle_number if success else state.get("last_successful_cycle"),
                "last_successful_slug": active_slug if success else state.get("last_successful_slug", ""),
                "last_error": error_message,
                "status": "sleeping" if success else "error",
                "active_slug": "",
                "next_slug": slugs[(queue_index + 1) % len(slugs)] if slugs else "",
            }
        )
        persist_state(base_dir, state)

        if args.once or stop_requested["value"]:
            break

        sleep_seconds = args.cycle_sleep_seconds if success else args.error_sleep_seconds
        for _ in range(max(sleep_seconds, 0)):
            if stop_requested["value"]:
                break
            time.sleep(1)
            state["status"] = "sleeping" if success else "error"
            persist_state(base_dir, state)

    state["status"] = "stopped"
    state["stopped_at"] = now_iso()
    persist_state(base_dir, state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

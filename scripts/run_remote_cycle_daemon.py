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
from mystic.training.remote_cycle import (
    REMOTE_LAUNCHD_LABEL,
    append_jsonl,
    now_iso,
    read_json,
    remote_cycle_details_dir,
    remote_cycle_log_path,
    remote_cycle_state_path,
    write_json,
    write_remote_status_outputs,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the persistent Kaggle-backed Mystic Raven cycle forever.")
    parser.add_argument("--base-dir", default=str(ROOT / "mystic_data"))
    parser.add_argument("--base-model", default="Qwen/Qwen2.5-0.5B-Instruct")
    parser.add_argument("--cycle-prefix", default="remote_cycle")
    parser.add_argument("--adapter-prefix", default="raven_lora_remote")
    parser.add_argument("--model-suffix", default="qwen_0_5b")
    parser.add_argument("--sleep-seconds", type=int, default=0)
    parser.add_argument("--error-sleep-seconds", type=int, default=180)
    parser.add_argument("--poll-seconds", type=int, default=60)
    parser.add_argument("--timeout-minutes", type=int, default=240)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--train-limit", type=int, default=1000)
    parser.add_argument("--eval-limit", type=int, default=100)
    parser.add_argument("--learning-rate", type=float, default=0.00015)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--max-length", type=int, default=2048)
    parser.add_argument("--run-limit", type=int, default=20)
    parser.add_argument("--compare-limit", type=int, default=100)
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


def load_state(base_dir: Path) -> dict[str, Any]:
    path = remote_cycle_state_path(base_dir)
    if path.exists():
        state = read_json(path)
        state.setdefault("service_label", REMOTE_LAUNCHD_LABEL)
        return state
    return {
        "status": "idle",
        "service_label": REMOTE_LAUNCHD_LABEL,
        "started_at": now_iso(),
        "last_heartbeat": now_iso(),
        "current_cycle": 0,
        "completed_cycles": 0,
        "active_cycle_id": "",
        "active_adapter_path": "",
        "active_model_id": "",
        "current_phase": "idle",
        "current_kernel_ref": "",
        "current_dataset_ref": "",
        "last_error": "",
    }


def persist_state(base_dir: Path, state: dict[str, Any]) -> None:
    state["last_heartbeat"] = now_iso()
    write_json(remote_cycle_state_path(base_dir), state)
    write_remote_status_outputs(base_dir, state)
    write_execution_history_outputs(base_dir)


def cycle_artifact_paths(base_dir: Path, cycle_id: str) -> dict[str, Path]:
    cycle_root = base_dir / "cycles" / cycle_id
    return {
        "prepare": cycle_root / "prepare_summary.json",
        "submit": cycle_root / "kaggle_submit_summary.json",
        "poll": cycle_root / "kaggle_poll_summary.json",
        "download": cycle_root / "kaggle_download_summary.json",
        "finish": cycle_root / "summary.json",
    }


def infer_cycle_phase(base_dir: Path, cycle_id: str) -> tuple[str, dict[str, Any]]:
    paths = cycle_artifact_paths(base_dir, cycle_id)
    payloads: dict[str, Any] = {}
    for key, path in paths.items():
        if path.exists():
            payloads[key] = read_json(path)

    if "finish" in payloads:
        return "finish_complete", payloads
    if "download" in payloads:
        return "download_complete", payloads
    if "poll" in payloads:
        poll_payload = payloads["poll"]
        if str(poll_payload.get("final_status", "")).lower() == "complete":
            return "poll_complete", payloads
        return "polling", payloads
    if "submit" in payloads:
        return "submitted", payloads
    if "prepare" in payloads:
        return "prepared", payloads
    return "starting", payloads


def next_cycle_spec(args: argparse.Namespace, cycle_number: int) -> dict[str, str]:
    cycle_id = f"{args.cycle_prefix}_{cycle_number:04d}"
    adapter_name = f"{args.adapter_prefix}_{cycle_number:04d}"
    model_id = f"{adapter_name}_{args.model_suffix}"
    adapter_rel = Path("mystic_data") / "adapters" / adapter_name
    return {
        "cycle_id": cycle_id,
        "adapter_name": adapter_name,
        "adapter_path": str(adapter_rel),
        "model_id": model_id,
    }


def build_cycle_command(args: argparse.Namespace, spec: dict[str, str], base_dir: Path) -> list[str]:
    command = [
        sys.executable,
        "scripts/run_mystic_cycle.py",
        "full",
        "--cycle-id",
        spec["cycle_id"],
        "--base-dir",
        str(base_dir),
        "--run-prepare-data",
        "--base-model",
        args.base_model,
        "--adapter-path",
        spec["adapter_path"],
        "--model-id",
        spec["model_id"],
        "--poll-seconds",
        str(args.poll_seconds),
        "--timeout-minutes",
        str(args.timeout_minutes),
        "--learning-rate",
        str(args.learning_rate),
        "--epochs",
        str(args.epochs),
        "--batch-size",
        str(args.batch_size),
        "--max-length",
        str(args.max_length),
        "--run-limit",
        str(args.run_limit),
        "--compare-limit",
        str(args.compare_limit),
        "--notes",
        f"remote cycle daemon {spec['cycle_id']}",
    ]
    if int(args.limit) > 0:
        command.extend(["--limit", str(args.limit)])
    if int(args.train_limit) > 0:
        command.extend(["--train-limit", str(args.train_limit)])
    if int(args.eval_limit) > 0:
        command.extend(["--eval-limit", str(args.eval_limit)])
    return command


def is_blocking_remote_error(error_message: str) -> bool:
    text = error_message.lower()
    blockers = [
        "kaggle authentication failed",
        "authentication required",
        "could not find service",
        "kaggle cli not found",
    ]
    return any(blocker in text for blocker in blockers)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    base_dir = Path(args.base_dir)
    details_dir = remote_cycle_details_dir(base_dir)
    details_dir.mkdir(parents=True, exist_ok=True)
    cycle_log_path = remote_cycle_log_path(base_dir)

    stop_requested = {"value": False}

    def handle_stop(_signum: int, _frame: Any) -> None:
        stop_requested["value"] = True

    signal.signal(signal.SIGTERM, handle_stop)
    signal.signal(signal.SIGINT, handle_stop)

    state = load_state(base_dir)
    state["status"] = "running"
    state["pid"] = os.getpid()
    persist_state(base_dir, state)

    while not stop_requested["value"]:
        cycle_number = int(state.get("completed_cycles", 0) or 0) + 1
        spec = next_cycle_spec(args, cycle_number)
        cycle_id = spec["cycle_id"]
        command = build_cycle_command(args, spec, base_dir)

        state.update(
            {
                "status": "running",
                "current_cycle": cycle_number,
                "active_cycle_id": cycle_id,
                "active_adapter_path": spec["adapter_path"],
                "active_model_id": spec["model_id"],
                "current_phase": "starting",
                "current_kernel_ref": "",
                "current_dataset_ref": "",
                "last_error": "",
                "cycle_started_at": now_iso(),
            }
        )
        persist_state(base_dir, state)

        stdout_log = details_dir / f"{cycle_id}.stdout.log"
        stderr_log = details_dir / f"{cycle_id}.stderr.log"
        detail_path = details_dir / f"{cycle_id}.json"
        started_at = now_iso()
        success = False
        returncode: int | None = None
        error_message = ""
        parsed_summary: dict[str, Any] = {}
        child = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            while True:
                polled = child.poll()
                phase, payloads = infer_cycle_phase(base_dir, cycle_id)
                submit_payload = payloads.get("submit", {})
                state.update(
                    {
                        "current_phase": phase,
                        "current_kernel_ref": str(submit_payload.get("kernel_ref", "") or ""),
                        "current_dataset_ref": str(submit_payload.get("dataset_ref", "") or ""),
                    }
                )
                persist_state(base_dir, state)

                if polled is not None:
                    stdout_text, stderr_text = child.communicate()
                    returncode = int(polled)
                    write_text(stdout_log, stdout_text)
                    write_text(stderr_log, stderr_text)
                    parsed_summary = extract_last_json_object(stdout_text)
                    success = returncode == 0
                    if not success:
                        error_message = stderr_text.strip() or f"child_returncode={returncode}"
                    break

                if stop_requested["value"]:
                    child.terminate()
                    stdout_text, stderr_text = child.communicate(timeout=30)
                    process_returncode = child.returncode
                    returncode = 1 if process_returncode is None else int(process_returncode)
                    write_text(stdout_log, stdout_text)
                    write_text(stderr_log, stderr_text)
                    parsed_summary = extract_last_json_object(stdout_text)
                    success = False
                    error_message = "stop_requested"
                    break

                time.sleep(15)
        except Exception as exc:  # pragma: no cover
            error_message = repr(exc)
            success = False
            if child.poll() is None:
                child.kill()
                stdout_text, stderr_text = child.communicate()
                write_text(stdout_log, stdout_text)
                write_text(stderr_log, stderr_text)

        finished_at = now_iso()
        phase, payloads = infer_cycle_phase(base_dir, cycle_id)
        finish_payload = payloads.get("finish", {})
        compare_payload = finish_payload.get("compare_payload", {})
        metrics = compare_payload.get("metrics", {}) if isinstance(compare_payload, dict) else {}
        blocking_error = (not success) and is_blocking_remote_error(error_message)
        cycle_record = {
            "timestamp": finished_at,
            "cycle_number": cycle_number,
            "cycle_id": cycle_id,
            "started_at": started_at,
            "finished_at": finished_at,
            "status": "REMOTE_CYCLE_OK" if success else ("REMOTE_CYCLE_BLOCKED" if blocking_error else "REMOTE_CYCLE_ERROR"),
            "success": success,
            "blocked": blocking_error,
            "returncode": returncode,
            "error": error_message,
            "base_model": args.base_model,
            "adapter_path": spec["adapter_path"],
            "model_id": spec["model_id"],
            "current_phase": phase,
            "dataset_ref": str(payloads.get("submit", {}).get("dataset_ref", "") or ""),
            "kernel_ref": str(payloads.get("submit", {}).get("kernel_ref", "") or ""),
            "processed_count": finish_payload.get("processed_count"),
            "adapter_better_or_equal_rate": finish_payload.get("adapter_better_or_equal_rate")
            or metrics.get("adapter_better_or_equal_rate"),
            "stdout_log": str(stdout_log),
            "stderr_log": str(stderr_log),
            "cycle_summary_path": str((base_dir / "cycles" / cycle_id / "summary.json").resolve()),
            "parsed_summary": parsed_summary,
        }
        write_json(detail_path, cycle_record)
        append_jsonl(cycle_log_path, cycle_record)

        state.update(
            {
                "completed_cycles": cycle_number,
                "last_cycle_id": cycle_id,
                "last_finished_at": finished_at,
                "last_cycle_detail": str(detail_path),
                "last_successful_cycle_id": cycle_id if success else state.get("last_successful_cycle_id", ""),
                "last_adapter_path": spec["adapter_path"],
                "last_model_id": spec["model_id"],
                "last_error": error_message,
                "status": "sleeping" if success else ("blocked" if blocking_error else "error"),
                "active_cycle_id": "",
                "active_adapter_path": "",
                "active_model_id": "",
                "current_phase": "idle" if success else ("blocked" if blocking_error else "error"),
                "current_kernel_ref": "",
                "current_dataset_ref": "",
            }
        )
        persist_state(base_dir, state)

        if args.once or stop_requested["value"] or blocking_error:
            break

        sleep_seconds = args.sleep_seconds if success else args.error_sleep_seconds
        wake_at = time.monotonic() + max(sleep_seconds, 0)
        while time.monotonic() < wake_at and not stop_requested["value"]:
            persist_state(base_dir, state)
            time.sleep(min(15, max(wake_at - time.monotonic(), 0)))

    if state.get("status") != "blocked":
        state["status"] = "stopped"
        state["stopped_at"] = now_iso()
    persist_state(base_dir, state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

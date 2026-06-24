from __future__ import annotations

import argparse
import os
from pathlib import Path
import signal
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.execution_history import write_execution_history_outputs
from mystic.training.continuous import now_iso, read_json, write_json
from mystic.training.remote_cycle import remote_cycle_state_path, write_remote_status_outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Refresh Mystic report pages from append-only logs and state files.")
    parser.add_argument("--base-dir", default=str(ROOT / "mystic_data"))
    parser.add_argument("--interval-seconds", type=int, default=5)
    parser.add_argument("--once", action="store_true")
    return parser


def report_refresh_state_path(base_dir: str | Path) -> Path:
    return Path(base_dir) / "state" / "report_refresh_state.json"


def load_state(base_dir: Path) -> dict[str, Any]:
    path = report_refresh_state_path(base_dir)
    if path.exists():
        return read_json(path)
    return {
        "status": "idle",
        "started_at": now_iso(),
        "last_heartbeat": now_iso(),
        "last_rendered_at": "",
        "last_error": "",
    }


def persist_state(base_dir: Path, state: dict[str, Any]) -> None:
    state["last_heartbeat"] = now_iso()
    write_json(report_refresh_state_path(base_dir), state)


def refresh_reports(base_dir: Path) -> dict[str, str]:
    payload = write_execution_history_outputs(base_dir)
    remote_state_file = remote_cycle_state_path(base_dir)
    if remote_state_file.exists():
        write_remote_status_outputs(base_dir, read_json(remote_state_file))
    return {key: str(value) for key, value in payload.items()}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    base_dir = Path(args.base_dir)
    interval_seconds = max(int(args.interval_seconds), 1)
    stop_requested = {"value": False}

    def handle_stop(_signum: int, _frame: Any) -> None:
        stop_requested["value"] = True

    signal.signal(signal.SIGTERM, handle_stop)
    signal.signal(signal.SIGINT, handle_stop)

    state = load_state(base_dir)
    state.update(
        {
            "status": "running",
            "started_at": now_iso(),
            "pid": os.getpid(),
            "interval_seconds": interval_seconds,
            "last_error": "",
            "stopped_at": "",
        }
    )
    persist_state(base_dir, state)

    while not stop_requested["value"]:
        try:
            outputs = refresh_reports(base_dir)
            state.update(
                {
                    "status": "running",
                    "last_rendered_at": now_iso(),
                    "output_html": outputs.get("output_html", ""),
                    "output_json": outputs.get("output_json", ""),
                    "last_error": "",
                }
            )
        except Exception as exc:  # pragma: no cover
            state.update(
                {
                    "status": "error",
                    "last_error": repr(exc),
                }
            )
        persist_state(base_dir, state)
        if args.once:
            break
        wake_at = time.monotonic() + interval_seconds
        while time.monotonic() < wake_at and not stop_requested["value"]:
            persist_state(base_dir, state)
            time.sleep(min(1.0, max(wake_at - time.monotonic(), 0.0)))

    state["status"] = "stopped"
    state["stopped_at"] = now_iso()
    persist_state(base_dir, state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

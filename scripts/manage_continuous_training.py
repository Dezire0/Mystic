from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.training.continuous import LAUNCHD_LABEL, continuous_state_path, read_json


PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCHD_LABEL}.plist"


def xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def plist_value(value: Any, indent: int = 0) -> str:
    prefix = " " * indent
    if isinstance(value, bool):
        return f"{prefix}<{str(value).lower()}/>"
    if isinstance(value, str):
        return f"{prefix}<string>{xml_escape(value)}</string>"
    if isinstance(value, list):
        items = "\n".join(plist_value(item, indent + 2) for item in value)
        return f"{prefix}<array>\n{items}\n{prefix}</array>"
    if isinstance(value, dict):
        rows = []
        for key, item in value.items():
            rows.append(f"{prefix}  <key>{xml_escape(str(key))}</key>")
            rows.append(plist_value(item, indent + 2))
        inner = "\n".join(rows)
        return f"{prefix}<dict>\n{inner}\n{prefix}</dict>"
    return f"{prefix}<string>{xml_escape(str(value))}</string>"


def plist_document(payload: dict[str, Any]) -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" "
        "\"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">\n"
        "<plist version=\"1.0\">\n"
        f"{plist_value(payload, 0)}\n"
        "</plist>\n"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install and manage the Mystic continuous training launchd agent.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--base-dir", default=str(ROOT / "mystic_data"))
    common.add_argument("--backend", choices=["manual", "unsloth", "axolotl"], default="manual")
    common.add_argument("--cycle-sleep-seconds", type=int, default=0)
    common.add_argument("--error-sleep-seconds", type=int, default=60)
    common.add_argument("--hf-base-rows", type=int, default=25)
    common.add_argument("--numina-base-limit", type=int, default=1500)
    common.add_argument("--public-base-rows-per-agent", type=int, default=50)
    common.add_argument("--epochs", type=int, default=1)
    common.add_argument("--max-steps", type=int, default=20)
    common.add_argument("--learning-rate", type=float, default=0.00015)
    common.add_argument("--sequence-length", type=int, default=512)
    common.add_argument("--step-timeout-seconds", type=int, default=600)
    common.add_argument("--cycle-timeout-seconds", type=int, default=7200)
    common.add_argument("--hf-slugs", nargs="*", default=[])
    common.add_argument(
        "--allow-system-sleep",
        action="store_true",
        help="Do not wrap the daemon in caffeinate. Default behavior prevents idle/system sleep while the service runs.",
    )

    install_parser = subparsers.add_parser("install", parents=[common], help="Write plist and start the launchd service.")
    install_parser.set_defaults(func=install_agent)

    start_parser = subparsers.add_parser("start", help="Start or restart the installed launchd service.")
    start_parser.set_defaults(func=start_agent)

    stop_parser = subparsers.add_parser("stop", help="Stop the launchd service.")
    stop_parser.set_defaults(func=stop_agent)

    restart_parser = subparsers.add_parser("restart", help="Restart the launchd service.")
    restart_parser.set_defaults(func=restart_agent)

    status_parser = subparsers.add_parser("status", help="Show service and state status.")
    status_parser.add_argument("--base-dir", default=str(ROOT / "mystic_data"))
    status_parser.set_defaults(func=status_agent)

    uninstall_parser = subparsers.add_parser("uninstall", help="Stop the service and remove the plist.")
    uninstall_parser.set_defaults(func=uninstall_agent)
    return parser


def launchd_domain() -> str:
    return f"gui/{os.getuid()}"


def daemon_command(args: argparse.Namespace) -> list[str]:
    command = [
        str(ROOT / ".venv-training" / "bin" / "python"),
        str(ROOT / "scripts" / "run_continuous_training_daemon.py"),
        "--base-dir",
        str(Path(args.base_dir).resolve()),
        "--backend",
        args.backend,
        "--cycle-sleep-seconds",
        str(args.cycle_sleep_seconds),
        "--error-sleep-seconds",
        str(args.error_sleep_seconds),
        "--hf-base-rows",
        str(args.hf_base_rows),
        "--numina-base-limit",
        str(args.numina_base_limit),
        "--public-base-rows-per-agent",
        str(args.public_base_rows_per_agent),
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
        "--cycle-timeout-seconds",
        str(args.cycle_timeout_seconds),
    ]
    if args.hf_slugs:
        command.extend(["--hf-slugs", *args.hf_slugs])
    return command


def service_program_arguments(args: argparse.Namespace) -> list[str]:
    command = daemon_command(args)
    if getattr(args, "allow_system_sleep", False):
        return command
    return ["/usr/bin/caffeinate", "-i", "-s", *command]


def installed_sleep_prevention_mode() -> str:
    if not PLIST_PATH.exists():
        return "unknown"
    text = PLIST_PATH.read_text(encoding="utf-8")
    return "caffeinate" if "/usr/bin/caffeinate" in text else "disabled"


def plist_payload(args: argparse.Namespace) -> dict[str, Any]:
    base_dir = Path(args.base_dir).resolve()
    logs_dir = base_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return {
        "Label": LAUNCHD_LABEL,
        "ProgramArguments": service_program_arguments(args),
        "WorkingDirectory": str(ROOT),
        "EnvironmentVariables": {
            "PYTHONUNBUFFERED": "1",
        },
        "RunAtLoad": True,
        "KeepAlive": True,
        "ProcessType": "Background",
        "StandardOutPath": str(logs_dir / "continuous_training.launchd.stdout.log"),
        "StandardErrorPath": str(logs_dir / "continuous_training.launchd.stderr.log"),
    }


def run_launchctl(*args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["launchctl", *args],
        text=True,
        capture_output=True,
        check=check,
    )


def install_agent(args: argparse.Namespace) -> int:
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.write_text(plist_document(plist_payload(args)), encoding="utf-8")
    stop_agent(args)
    start_agent(args)
    return status_agent(args)


def start_agent(_args: argparse.Namespace) -> int:
    if not PLIST_PATH.exists():
        raise FileNotFoundError(f"Missing plist: {PLIST_PATH}")
    run_launchctl("bootstrap", launchd_domain(), str(PLIST_PATH), check=False)
    run_launchctl("kickstart", "-k", f"{launchd_domain()}/{LAUNCHD_LABEL}", check=False)
    return 0


def stop_agent(_args: argparse.Namespace) -> int:
    if PLIST_PATH.exists():
        run_launchctl("bootout", launchd_domain(), str(PLIST_PATH), check=False)
    return 0


def restart_agent(args: argparse.Namespace) -> int:
    stop_agent(args)
    start_agent(args)
    return status_agent(args)


def status_agent(args: argparse.Namespace) -> int:
    base_dir = Path(getattr(args, "base_dir", str(ROOT / "mystic_data"))).resolve()
    state_path = continuous_state_path(base_dir)
    launchctl_status = run_launchctl("print", f"{launchd_domain()}/{LAUNCHD_LABEL}", check=False)
    payload: dict[str, Any] = {
        "label": LAUNCHD_LABEL,
        "plist_path": str(PLIST_PATH),
        "plist_exists": PLIST_PATH.exists(),
        "sleep_prevention": installed_sleep_prevention_mode(),
        "launchctl_returncode": launchctl_status.returncode,
        "launchctl_stdout": launchctl_status.stdout,
        "launchctl_stderr": launchctl_status.stderr,
        "state_path": str(state_path),
        "state": read_json(state_path) if state_path.exists() else {},
    }
    print(json.dumps(payload, indent=2, ensure_ascii=True))
    return 0


def uninstall_agent(args: argparse.Namespace) -> int:
    stop_agent(args)
    if PLIST_PATH.exists():
        PLIST_PATH.unlink()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

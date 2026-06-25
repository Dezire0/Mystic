from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LABEL = "com.mystic.report-refresh"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
PYTHON_BIN = ROOT / ".venv-training" / "bin" / "python"
DEFAULT_BASE_DIR = ROOT / "mystic_data"


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
        return f"{prefix}<dict>\n" + "\n".join(rows) + f"\n{prefix}</dict>"
    return f"{prefix}<string>{xml_escape(str(value))}</string>"


def plist_document(payload: dict[str, Any]) -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" "
        "\"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">\n"
        "<plist version=\"1.0\">\n"
        f"{plist_value(payload)}\n"
        "</plist>\n"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install and manage the Mystic report refresh launchd agent.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--base-dir", default=str(DEFAULT_BASE_DIR))
    common.add_argument("--interval-seconds", type=int, default=5)
    for command in ["install", "start", "stop", "restart", "status", "uninstall"]:
        child = subparsers.add_parser(command, parents=[common])
        child.set_defaults(func=globals()[f"{command}_agent"])
    return parser


def launchd_domain() -> str:
    return f"gui/{os.getuid()}"


def service_target() -> str:
    return f"{launchd_domain()}/{LABEL}"


def run_launchctl(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["launchctl", *args], capture_output=True, text=True, check=False)


def plist_payload(base_dir: Path, interval_seconds: int) -> dict[str, Any]:
    logs_dir = base_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return {
        "Label": LABEL,
        "ProgramArguments": [
            str(PYTHON_BIN),
            str(ROOT / "scripts" / "run_report_refresh_daemon.py"),
            "--base-dir",
            str(base_dir),
            "--interval-seconds",
            str(interval_seconds),
        ],
        "WorkingDirectory": str(ROOT),
        "EnvironmentVariables": {
            "PYTHONUNBUFFERED": "1",
            "PATH": "/opt/homebrew/Caskroom/miniforge/base/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        },
        "RunAtLoad": True,
        "KeepAlive": True,
        "ProcessType": "Background",
        "StandardOutPath": str(logs_dir / "report_refresh.launchd.stdout.log"),
        "StandardErrorPath": str(logs_dir / "report_refresh.launchd.stderr.log"),
    }


def write_plist(base_dir: Path, interval_seconds: int) -> Path:
    if not PYTHON_BIN.exists():
        raise FileNotFoundError(f"Missing training venv Python: {PYTHON_BIN}")
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.write_text(plist_document(plist_payload(base_dir, interval_seconds)), encoding="utf-8")
    return PLIST_PATH


def install_agent(args: argparse.Namespace) -> int:
    base_dir = Path(args.base_dir).resolve()
    write_plist(base_dir, int(args.interval_seconds))
    stop_agent(args)
    start_agent(args)
    return status_agent(args)


def start_agent(_args: argparse.Namespace) -> int:
    if not PLIST_PATH.exists():
        raise FileNotFoundError(f"Missing plist: {PLIST_PATH}")
    run_launchctl("bootstrap", launchd_domain(), str(PLIST_PATH))
    run_launchctl("kickstart", "-k", service_target())
    return 0


def stop_agent(_args: argparse.Namespace) -> int:
    run_launchctl("bootout", launchd_domain(), str(PLIST_PATH))
    run_launchctl("bootout", service_target())
    return 0


def restart_agent(args: argparse.Namespace) -> int:
    stop_agent(args)
    if not PLIST_PATH.exists():
        write_plist(Path(args.base_dir).resolve(), int(args.interval_seconds))
    start_agent(args)
    return status_agent(args)


def status_agent(args: argparse.Namespace) -> int:
    base_dir = Path(args.base_dir).resolve()
    state_path = base_dir / "state" / "report_refresh_state.json"
    launchctl_status = run_launchctl("print", service_target())
    payload = {
        "label": LABEL,
        "plist_path": str(PLIST_PATH),
        "plist_exists": PLIST_PATH.exists(),
        "launchctl_returncode": launchctl_status.returncode,
        "launchctl_stdout": launchctl_status.stdout,
        "launchctl_stderr": launchctl_status.stderr,
        "state_path": str(state_path),
        "state": json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {},
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

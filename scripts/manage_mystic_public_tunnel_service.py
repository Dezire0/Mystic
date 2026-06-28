from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
LABEL = "com.mystic.public-tunnel"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
DEFAULT_BASE_DIR = ROOT / "mystic_data"
DEFAULT_PYTHON_BIN = Path(sys.executable).resolve()
DEFAULT_LOCAL_URL = "http://127.0.0.1:8765"


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
    parser = argparse.ArgumentParser(description="Install and manage the Mystic public tunnel launchd agent.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--base-dir", default=str(DEFAULT_BASE_DIR))
    common.add_argument("--python-bin", default=str(DEFAULT_PYTHON_BIN))
    common.add_argument("--local-url", default=DEFAULT_LOCAL_URL)
    common.add_argument("--gist-id", required=True)
    common.add_argument("--gist-file", default="mystic-origin.json")
    common.add_argument("--public-url", default="https://mystic.dexproject.workers.dev")

    install_parser = subparsers.add_parser("install", parents=[common], help="Write plist and start the Mystic public tunnel service.")
    install_parser.set_defaults(func=install_agent)

    start_parser = subparsers.add_parser("start", parents=[common], help="Start or restart the installed Mystic public tunnel service.")
    start_parser.set_defaults(func=start_agent)

    stop_parser = subparsers.add_parser("stop", parents=[common], help="Stop the Mystic public tunnel service.")
    stop_parser.set_defaults(func=stop_agent)

    restart_parser = subparsers.add_parser("restart", parents=[common], help="Restart the Mystic public tunnel service.")
    restart_parser.set_defaults(func=restart_agent)

    status_parser = subparsers.add_parser("status", parents=[common], help="Show Mystic public tunnel service status.")
    status_parser.set_defaults(func=status_agent)

    uninstall_parser = subparsers.add_parser("uninstall", parents=[common], help="Stop the service and remove the plist.")
    uninstall_parser.set_defaults(func=uninstall_agent)
    return parser


def launchd_domain() -> str:
    return f"gui/{os.getuid()}"


def service_target() -> str:
    return f"{launchd_domain()}/{LABEL}"


def daemon_command(args: argparse.Namespace) -> list[str]:
    return [
        str(Path(args.python_bin).resolve()),
        str(ROOT / "scripts" / "run_mystic_public_tunnel.py"),
        "--local-url",
        args.local_url,
        "--gist-id",
        args.gist_id,
        "--gist-file",
        args.gist_file,
    ]


def plist_payload(args: argparse.Namespace) -> dict[str, Any]:
    base_dir = Path(args.base_dir).resolve()
    logs_dir = base_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return {
        "Label": LABEL,
        "ProgramArguments": daemon_command(args),
        "WorkingDirectory": str(ROOT),
        "EnvironmentVariables": {
            "PYTHONUNBUFFERED": "1",
            "PATH": "/opt/homebrew/Caskroom/miniforge/base/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        },
        "RunAtLoad": True,
        "KeepAlive": True,
        "ProcessType": "Background",
        "StandardOutPath": str(logs_dir / "mystic_public_tunnel.launchd.stdout.log"),
        "StandardErrorPath": str(logs_dir / "mystic_public_tunnel.launchd.stderr.log"),
    }


def run_launchctl(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["launchctl", *args], capture_output=True, text=True, check=False)


def write_plist(args: argparse.Namespace) -> Path:
    python_bin = Path(args.python_bin).resolve()
    if not python_bin.exists():
        raise FileNotFoundError(f"Missing Python binary: {python_bin}")
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.write_text(plist_document(plist_payload(args)), encoding="utf-8")
    return PLIST_PATH


def install_agent(args: argparse.Namespace) -> int:
    write_plist(args)
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
        write_plist(args)
    start_agent(args)
    return status_agent(args)


def status_agent(args: argparse.Namespace) -> int:
    base_dir = Path(args.base_dir).resolve()
    logs_dir = base_dir / "logs"
    stdout_path = logs_dir / "mystic_public_tunnel.launchd.stdout.log"
    stderr_path = logs_dir / "mystic_public_tunnel.launchd.stderr.log"
    launchctl_status = run_launchctl("print", service_target())
    payload = {
        "label": LABEL,
        "plist_path": str(PLIST_PATH),
        "plist_exists": PLIST_PATH.exists(),
        "launchctl_returncode": launchctl_status.returncode,
        "launchctl_stdout": launchctl_status.stdout,
        "launchctl_stderr": launchctl_status.stderr,
        "stdout_log": str(stdout_path),
        "stderr_log": str(stderr_path),
        "stdout_exists": stdout_path.exists(),
        "stderr_exists": stderr_path.exists(),
        "stdout_tail": tail_text(stdout_path),
        "stderr_tail": tail_text(stderr_path),
        "public_healthcheck": public_healthcheck(args.public_url),
        "public_ping": public_ping(args.public_url),
        "public_mcp": f"{args.public_url.rstrip('/')}/mcp",
    }
    print(json.dumps(payload, indent=2, ensure_ascii=True))
    return 0


def public_healthcheck(public_url: str) -> dict[str, Any]:
    url = f"{public_url.rstrip('/')}/health"
    try:
        request = Request(url, headers={"user-agent": "Mozilla/5.0"})
        with urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8", errors="replace")
            return {"ok": True, "url": url, "status": response.status, "body": body}
    except URLError as exc:
        return {"ok": False, "url": url, "error": str(exc)}


def public_ping(public_url: str) -> dict[str, Any]:
    url = f"{public_url.rstrip('/')}/mcp"
    request = Request(
        url,
        data=b'{"jsonrpc":"2.0","id":1,"method":"ping"}',
        headers={"content-type": "application/json", "user-agent": "Mozilla/5.0"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8", errors="replace")
            return {"ok": True, "url": url, "status": response.status, "body": body}
    except URLError as exc:
        return {"ok": False, "url": url, "error": str(exc)}


def tail_text(path: Path, line_limit: int = 60) -> str:
    if not path.exists():
        return ""
    return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-line_limit:])


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

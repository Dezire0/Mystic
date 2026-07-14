"""Install or remove the private macOS launchd service for Mystic's trusted runner.

The runner token is fetched at runtime from Keychain; this script never writes it
to the plist or logs.  The service is intentionally user-scoped, not root-scoped.
"""
from __future__ import annotations

import argparse
import os
import plistlib
import subprocess
import sys
from pathlib import Path


LABEL = "com.mystic.engine-runner"
ROOT = Path(__file__).resolve().parents[1]
PLIST = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
LOG_DIR = Path.home() / "Library" / "Logs" / "Mystic"


def service_definition() -> dict[str, object]:
    return {
        "Label": LABEL,
        "ProgramArguments": [sys.executable, str(ROOT / "scripts" / "mystic_engine_runner.py"), "--start"],
        "WorkingDirectory": str(ROOT),
        "RunAtLoad": True,
        "KeepAlive": {"SuccessfulExit": False},
        "ProcessType": "Background",
        "EnvironmentVariables": {
            "MYSTIC_ENGINE_ENDPOINT": "https://mystic.dexproject.workers.dev",
            "MYSTIC_ENGINE_RUNNER_ID": "mystic-mac-runner",
            "MYSTIC_ENGINE_KEYCHAIN_SERVICE": "mystic-engine-runner-token",
            "MYSTIC_ENGINE_KEYCHAIN_ACCOUNT": "mystic-engine-runner",
        },
        "StandardOutPath": str(LOG_DIR / "engine-runner.log"),
        "StandardErrorPath": str(LOG_DIR / "engine-runner-error.log"),
    }


def run(*args: str) -> None:
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def install() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.chmod(0o700)
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    with PLIST.open("wb") as handle:
        plistlib.dump(service_definition(), handle, sort_keys=True)
    PLIST.chmod(0o600)
    # bootout is intentionally best-effort for upgrades of an existing service.
    domain = f"gui/{os.getuid()}"
    subprocess.run(["launchctl", "bootout", domain, str(PLIST)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    run("launchctl", "bootstrap", domain, str(PLIST))
    run("launchctl", "kickstart", "-k", f"{domain}/{LABEL}")


def uninstall() -> None:
    if PLIST.exists():
        subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}", str(PLIST)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        PLIST.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage the Mystic trusted engine runner launchd service.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--install", action="store_true")
    mode.add_argument("--uninstall", action="store_true")
    args = parser.parse_args()
    if args.install:
        install()
        print('{"status":"installed","label":"com.mystic.engine-runner"}')
    else:
        uninstall()
        print('{"status":"uninstalled","label":"com.mystic.engine-runner"}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

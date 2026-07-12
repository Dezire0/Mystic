#!/usr/bin/env python3
"""Install the Mystic manual-relay Native Messaging manifest for macOS Chrome."""
from __future__ import annotations
import argparse, json, os, stat, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = Path.home() / "Library" / "Application Support" / "Mystic"
CHROME_DIR = Path.home() / "Library" / "Application Support" / "Google" / "Chrome" / "NativeMessagingHosts"
MANIFEST = CHROME_DIR / "com.mystic.gemini_app_bridge.json"
CONFIG = APP_DIR / "gemini_app_bridge_host.json"
LAUNCHER = APP_DIR / "mystic_gemini_app_native_host_launcher.py"
HOST = ROOT / "scripts" / "mystic_gemini_app_native_host.py"

def install(extension_id: str) -> None:
    if not extension_id or any(char not in "abcdefghijklmnopqrstuvwxyz" for char in extension_id): raise SystemExit("extension ID must contain lowercase letters only")
    APP_DIR.mkdir(parents=True, exist_ok=True); CHROME_DIR.mkdir(parents=True, exist_ok=True); os.chmod(APP_DIR, 0o700)
    LAUNCHER.write_text(f'#!{sys.executable}\nimport runpy\nrunpy.run_path({str(HOST)!r}, run_name="__main__")\n', encoding="utf-8"); LAUNCHER.chmod(LAUNCHER.stat().st_mode | stat.S_IXUSR)
    CONFIG.write_text(json.dumps({"extension_id": extension_id}), encoding="utf-8"); os.chmod(CONFIG, 0o600)
    MANIFEST.write_text(json.dumps({"name":"com.mystic.gemini_app_bridge","description":"Mystic Gemini App Manual Relay","path":str(LAUNCHER),"type":"stdio","allowed_origins":[f"chrome-extension://{extension_id}/"]}, indent=2) + "\n", encoding="utf-8")
    print(f"Installed Native Messaging manifest: {MANIFEST}")
def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("--extension-id"); parser.add_argument("--status",action="store_true"); parser.add_argument("--uninstall",action="store_true"); args=parser.parse_args()
    if args.uninstall: MANIFEST.unlink(missing_ok=True); CONFIG.unlink(missing_ok=True); print("Uninstalled Mystic Native Messaging manifest."); return
    if args.status: print("installed" if MANIFEST.exists() and CONFIG.exists() else "not_installed"); return
    if not args.extension_id: parser.error("--extension-id is required")
    install(args.extension_id)
if __name__ == "__main__": main()

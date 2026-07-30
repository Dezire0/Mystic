from __future__ import annotations

import argparse
import json
import os
import platform
import signal
import subprocess
import threading
import time

import requests

from mystic.lab.engines import builtin_registry
from mystic.lab.engines.runtime import EngineJob, EngineRuntime

HEARTBEAT_INTERVAL_SECONDS = 20
LEASE_SECONDS = 60
IDLE_POLL_SECONDS = 5
RUNNER_PROTOCOL_VERSION = "2b.1"
shutdown_requested = threading.Event()


def runner_token() -> str:
    configured = os.environ.get("MYSTIC_ENGINE_RUNNER_TOKEN", "").strip()
    if configured:
        return configured
    token_file = os.environ.get("MYSTIC_ENGINE_RUNNER_TOKEN_FILE", "").strip()
    if token_file:
        try:
            token = open(token_file, encoding="utf-8").read(4097).strip()
        except OSError as error:
            raise RuntimeError("runner_token_file_unavailable") from error
        if not token or len(token) > 4096:
            raise RuntimeError("runner_token_file_invalid")
        return token
    service = os.environ.get("MYSTIC_ENGINE_KEYCHAIN_SERVICE", "mystic-engine-runner-token")
    account = os.environ.get("MYSTIC_ENGINE_KEYCHAIN_ACCOUNT", "mystic-engine-runner")
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as error:
        raise RuntimeError("runner_keychain_lookup_failed") from error
    token = result.stdout.strip()
    if not token:
        raise RuntimeError("runner token is not available in Keychain")
    return token


def production_request(action: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    endpoint = os.environ["MYSTIC_ENGINE_ENDPOINT"].rstrip("/")
    token = runner_token()
    try:
        response = requests.post(
            f"{endpoint}/internal/engine-runner/{action}",
            headers={"authorization": f"Bearer {token}", "content-type": "application/json", "user-agent": "MysticEngineRunner/phase2a"},
            json=payload or {},
            timeout=30,
        )
    except requests.RequestException as error:
        raise RuntimeError("runner_network_failure") from error
    if response.status_code != 200:
        raise RuntimeError(f"runner_backend_http_{response.status_code}")
    data=response.json()
    return data if isinstance(data,dict) else {}


def production_status() -> dict[str, object]:
    endpoint = os.environ["MYSTIC_ENGINE_ENDPOINT"].rstrip("/")
    token = runner_token()
    runner_id = os.environ.get("MYSTIC_ENGINE_RUNNER_ID", "mystic-mac-runner")
    try:
        response = requests.get(
            f"{endpoint}/internal/engine-runner/status",
            params={"runner_id": runner_id},
            headers={"authorization": f"Bearer {token}", "user-agent": "MysticEngineRunner/phase2a"},
            timeout=30,
        )
    except requests.RequestException as error:
        raise RuntimeError("runner_network_failure") from error
    if response.status_code != 200:
        raise RuntimeError(f"runner_backend_http_{response.status_code}")
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError("runner_backend_invalid_response")
    return data


def runner_registration(registry) -> dict[str, object]:
    """Return only scheduler-safe runner metadata, never host paths or credentials."""
    return {
        "runner_id": os.environ.get("MYSTIC_ENGINE_RUNNER_ID", "mystic-mac-runner"),
        "runner_version": os.environ.get("MYSTIC_ENGINE_RUNNER_VERSION", "phase2b.1"),
        "runtime_version": platform.python_version(),
        "operating_system": platform.system().lower(),
        "architecture": platform.machine().lower(),
        "supported_resource_classes": ["tiny", "small"],
        "max_concurrent_jobs": 1,
        "active_jobs": 0,
        "cpu_count": max(0, os.cpu_count() or 0),
        "memory_limit_mb": int(os.environ.get("MYSTIC_ENGINE_RUNNER_MEMORY_LIMIT_MB", "0") or 0),
        "region": os.environ.get("MYSTIC_ENGINE_RUNNER_REGION", ""),
        "priority": int(os.environ.get("MYSTIC_ENGINE_RUNNER_PRIORITY", "0") or 0),
        "protocol_version": RUNNER_PROTOCOL_VERSION,
        "engines": [{"engine_id": item.engine_id, "version": item.version} for item in registry.list()],
    }


def production_once(registry) -> dict[str, object]:
    registration = runner_registration(registry)
    runner_id = str(registration["runner_id"])
    production_request("register", registration)
    if shutdown_requested.is_set():
        production_request("enter-draining", {"runner_id": runner_id, "protocol_version": RUNNER_PROTOCOL_VERSION})
        return {"status": "draining"}
    claimed=production_request("claim",{"runner_id":runner_id,"lease_seconds":LEASE_SECONDS}).get("job")
    if not isinstance(claimed,dict): return {"status":"idle"}
    job=EngineJob(job_id=str(claimed["job_id"]),engine_id=str(claimed["engine_id"]),input_payload=dict(claimed.get("normalized_input") or {}),session_id=str(claimed.get("session_id") or ""),experiment_id=str(claimed.get("experiment_id") or ""),scene_id=str(claimed.get("scene_id") or ""))
    stop_heartbeat = threading.Event()
    cancellation_requested = threading.Event()
    def heartbeat() -> None:
        while not stop_heartbeat.wait(HEARTBEAT_INTERVAL_SECONDS):
            try:
                renewal = production_request("lease-renew", {"runner_id": runner_id, "job_id": job.job_id, "lease_seconds": LEASE_SECONDS, "protocol_version": RUNNER_PROTOCOL_VERSION})
                if renewal.get("ok") is False:
                    cancellation_requested.set()
            except RuntimeError:
                # The worker will expire/release the lease if connectivity remains down.
                pass
    heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
    heartbeat_thread.start()
    runtime=EngineRuntime(registry); runtime.queue.create(job)
    try:
        result=runtime.execute_next(runner_id)
    finally:
        stop_heartbeat.set()
        heartbeat_thread.join(timeout=1)
    if cancellation_requested.is_set():
        production_request("cancellation-acknowledge", {"runner_id": runner_id, "job_id": job.job_id, "safe_error": "The runner acknowledged cancellation after bounded execution."})
        return {"status": "cancelled", "job_id": job.job_id}
    if result and result.get("status") == "completed":
        completion=production_request("complete",{"runner_id":runner_id,"job_id":job.job_id,"result":result})
        return {"status":"completed" if completion.get("ok") else "completion_rejected","job_id":job.job_id,"run_id":result.get("run_id","")}
    production_request("fail",{"runner_id":runner_id,"job_id":job.job_id,"status":str((result or {}).get("status","failed")),"safe_error":str((result or {}).get("safe_error","The engine did not complete."))})
    return {"status":"failed","job_id":job.job_id}


def production_start(registry) -> int:
    """Run indefinitely for launchd with bounded retry delay and no secret logging."""
    delay = 2
    while not shutdown_requested.is_set():
        try:
            result = production_once(registry)
            delay = 2 if result.get("status") != "idle" else 5
            sleep_seconds = IDLE_POLL_SECONDS if result.get("status") == "idle" else delay
        except (KeyError, RuntimeError, ValueError) as error:
            print(json.dumps({"status": "runner_retry", "error_category": str(error)}), flush=True)
            delay = min(delay * 2, 60)
            sleep_seconds = delay
        shutdown_requested.wait(sleep_seconds)
    try:
        production_request("release", {"runner_id": os.environ.get("MYSTIC_ENGINE_RUNNER_ID", "mystic-mac-runner"), "protocol_version": RUNNER_PROTOCOL_VERSION})
    except RuntimeError:
        # The lease expiry path handles a disconnected shutdown without leaking details.
        pass
    return 0


def request_shutdown(*_: object) -> None:
    shutdown_requested.set()


def main() -> int:
    parser=argparse.ArgumentParser(description="Mystic Phase 2A trusted local engine runner (no arbitrary code execution).")
    parser.add_argument("--once",action="store_true"); parser.add_argument("--start",action="store_true"); parser.add_argument("--list-engines",action="store_true"); parser.add_argument("--self-test",action="store_true"); parser.add_argument("--status",action="store_true")
    args=parser.parse_args(); registry=builtin_registry()
    if args.list_engines: print(json.dumps([manifest.public_dict() for manifest in registry.list()],sort_keys=True)); return 0
    if args.self_test:
        from scripts.check_engine_runtime import main as verify
        return verify()
    if args.status:
        if os.environ.get("MYSTIC_ENGINE_ENDPOINT"):
            status = production_status()
            print(json.dumps({"status": status.get("status", "unknown"), "runner_count": len(status.get("runners", [])), "runner_token_configured": bool(status.get("runner_token_configured"))}, sort_keys=True))
            return 0
        print(json.dumps({"status":"local_runner_ready","engine_count":len(registry.list()),"production_note":"Supabase claim/heartbeat requires a server-side runner deployment and secret."})); return 0
    if args.once:
        if os.environ.get("MYSTIC_ENGINE_ENDPOINT"):
            print(json.dumps(production_once(registry))); return 0
        print(json.dumps({"status":"idle","result":EngineRuntime(registry).execute_next()})); return 0
    if args.start:
        if not os.environ.get("MYSTIC_ENGINE_ENDPOINT"):
            parser.error("--start requires MYSTIC_ENGINE_ENDPOINT")
        signal.signal(signal.SIGTERM, request_shutdown)
        signal.signal(signal.SIGINT, request_shutdown)
        return production_start(registry)
    parser.error("select --status, --list-engines, --self-test, --once, or --start")
    return 2


if __name__ == "__main__": raise SystemExit(main())

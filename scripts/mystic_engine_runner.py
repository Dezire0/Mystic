from __future__ import annotations

import argparse
import json
import os
import subprocess
import threading
import time

import requests

from mystic.lab.engines import builtin_registry
from mystic.lab.engines.runtime import EngineJob, EngineRuntime

HEARTBEAT_INTERVAL_SECONDS = 20
LEASE_SECONDS = 60
IDLE_POLL_SECONDS = 5


def runner_token() -> str:
    configured = os.environ.get("MYSTIC_ENGINE_RUNNER_TOKEN", "").strip()
    if configured:
        return configured
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
    try:
        response = requests.get(
            f"{endpoint}/internal/engine-runner/status",
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


def production_once(registry) -> dict[str, object]:
    runner_id=os.environ.get("MYSTIC_ENGINE_RUNNER_ID","mystic-mac-runner")
    production_request("register",{"runner_id":runner_id,"runner_version":os.environ.get("MYSTIC_ENGINE_RUNNER_VERSION","phase2a"),"supported_resource_classes":["tiny","small"],"engines":[{"engine_id":item.engine_id,"version":item.version} for item in registry.list()]})
    claimed=production_request("claim",{"runner_id":runner_id,"lease_seconds":LEASE_SECONDS}).get("job")
    if not isinstance(claimed,dict): return {"status":"idle"}
    job=EngineJob(job_id=str(claimed["job_id"]),engine_id=str(claimed["engine_id"]),input_payload=dict(claimed.get("normalized_input") or {}),session_id=str(claimed.get("session_id") or ""),experiment_id=str(claimed.get("experiment_id") or ""),scene_id=str(claimed.get("scene_id") or ""))
    stop_heartbeat = threading.Event()
    def heartbeat() -> None:
        while not stop_heartbeat.wait(HEARTBEAT_INTERVAL_SECONDS):
            try:
                production_request("heartbeat", {"runner_id": runner_id, "job_id": job.job_id, "lease_seconds": LEASE_SECONDS})
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
    if result and result.get("status") == "completed":
        completion=production_request("complete",{"runner_id":runner_id,"job_id":job.job_id,"result":result})
        return {"status":"completed" if completion.get("ok") else "completion_rejected","job_id":job.job_id,"run_id":result.get("run_id","")}
    production_request("fail",{"runner_id":runner_id,"job_id":job.job_id,"status":str((result or {}).get("status","failed")),"safe_error":str((result or {}).get("safe_error","The engine did not complete."))})
    return {"status":"failed","job_id":job.job_id}


def production_start(registry) -> int:
    """Run indefinitely for launchd with bounded retry delay and no secret logging."""
    delay = 2
    while True:
        try:
            result = production_once(registry)
            delay = 2 if result.get("status") != "idle" else 5
            sleep_seconds = IDLE_POLL_SECONDS if result.get("status") == "idle" else delay
        except (KeyError, RuntimeError, ValueError) as error:
            print(json.dumps({"status": "runner_retry", "error_category": str(error)}), flush=True)
            delay = min(delay * 2, 60)
            sleep_seconds = delay
        time.sleep(sleep_seconds)


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
        return production_start(registry)
    parser.error("select --status, --list-engines, --self-test, --once, or --start")
    return 2


if __name__ == "__main__": raise SystemExit(main())

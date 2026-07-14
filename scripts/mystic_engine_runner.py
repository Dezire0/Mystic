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


def runner_token() -> str:
    configured = os.environ.get("MYSTIC_ENGINE_RUNNER_TOKEN", "").strip()
    if configured:
        return configured
    service = os.environ.get("MYSTIC_ENGINE_KEYCHAIN_SERVICE", "mystic-engine-runner-token")
    account = os.environ.get("MYSTIC_ENGINE_KEYCHAIN_ACCOUNT", "mystic-engine-runner")
    result = subprocess.run(
        ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
        check=True,
        text=True,
        capture_output=True,
    )
    token = result.stdout.strip()
    if not token:
        raise RuntimeError("runner token is not available in Keychain")
    return token


def production_request(action: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    endpoint=os.environ["MYSTIC_ENGINE_ENDPOINT"].rstrip("/")
    token=runner_token()
    response=requests.post(f"{endpoint}/internal/engine-runner/{action}",headers={"authorization":f"Bearer {token}","content-type":"application/json","user-agent":"MysticEngineRunner/phase2a"},json=payload or {},timeout=30)
    if response.status_code != 200: raise RuntimeError("runner backend rejected the safe request")
    data=response.json()
    return data if isinstance(data,dict) else {}


def production_once(registry) -> dict[str, object]:
    runner_id=os.environ.get("MYSTIC_ENGINE_RUNNER_ID","mystic-mac-runner")
    production_request("register",{"runner_id":runner_id,"supported_resource_classes":["tiny","small"],"engines":[{"engine_id":item.engine_id,"version":item.version} for item in registry.list()]})
    claimed=production_request("claim",{"runner_id":runner_id,"lease_seconds":60}).get("job")
    if not isinstance(claimed,dict): return {"status":"idle"}
    job=EngineJob(job_id=str(claimed["job_id"]),engine_id=str(claimed["engine_id"]),input_payload=dict(claimed.get("normalized_input") or {}),session_id=str(claimed.get("session_id") or ""),experiment_id=str(claimed.get("experiment_id") or ""),scene_id=str(claimed.get("scene_id") or ""))
    stop_heartbeat = threading.Event()
    def heartbeat() -> None:
        while not stop_heartbeat.wait(20):
            try:
                production_request("heartbeat", {"runner_id": runner_id, "job_id": job.job_id, "lease_seconds": 60})
            except requests.RequestException:
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
        except (KeyError, RuntimeError, requests.RequestException, ValueError):
            delay = min(delay * 2, 60)
        time.sleep(delay)


def main() -> int:
    parser=argparse.ArgumentParser(description="Mystic Phase 2A trusted local engine runner (no arbitrary code execution).")
    parser.add_argument("--once",action="store_true"); parser.add_argument("--start",action="store_true"); parser.add_argument("--list-engines",action="store_true"); parser.add_argument("--self-test",action="store_true"); parser.add_argument("--status",action="store_true")
    args=parser.parse_args(); registry=builtin_registry()
    if args.list_engines: print(json.dumps([manifest.public_dict() for manifest in registry.list()],sort_keys=True)); return 0
    if args.self_test:
        from scripts.check_engine_runtime import main as verify
        return verify()
    if args.status: print(json.dumps({"status":"local_runner_ready","engine_count":len(registry.list()),"production_note":"Supabase claim/heartbeat requires a server-side runner deployment and secret."})); return 0
    if args.once:
        if os.environ.get("MYSTIC_ENGINE_ENDPOINT") and os.environ.get("MYSTIC_ENGINE_RUNNER_TOKEN"):
            print(json.dumps(production_once(registry))); return 0
        print(json.dumps({"status":"idle","result":EngineRuntime(registry).execute_next()})); return 0
    if args.start:
        if not os.environ.get("MYSTIC_ENGINE_ENDPOINT"):
            parser.error("--start requires MYSTIC_ENGINE_ENDPOINT")
        return production_start(registry)
    parser.error("select --status, --list-engines, --self-test, --once, or --start")
    return 2


if __name__ == "__main__": raise SystemExit(main())

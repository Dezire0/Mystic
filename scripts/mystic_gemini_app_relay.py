#!/usr/bin/env python3
"""Authenticated local runner for user-submitted Gemini App Manual Relay responses."""
from __future__ import annotations
import argparse, json, os, socket, sys, time, uuid
from pathlib import Path
from urllib import request, error

DEFAULT_ENDPOINT="https://mystic.dexproject.workers.dev"; APP_DIR=Path.home()/"Library"/"Application Support"/"Mystic"; SOCKET_PATH=APP_DIR/"gemini_app_bridge.sock"; RUNNER_ID_PATH=APP_DIR/"gemini_app_bridge_runner_id"
def runner_id() -> str:
    APP_DIR.mkdir(parents=True,exist_ok=True)
    if RUNNER_ID_PATH.exists(): return RUNNER_ID_PATH.read_text().strip()
    value=f"relay-{uuid.uuid4()}"; RUNNER_ID_PATH.write_text(value); os.chmod(RUNNER_ID_PATH,0o600); return value
def token() -> str:
    value=os.environ.get("MYSTIC_RUNNER_BEARER_TOKEN","").strip()
    if not value: raise RuntimeError("MYSTIC_RUNNER_BEARER_TOKEN is required")
    return value
def worker(path:str, body:dict|None=None) -> dict:
    endpoint=os.environ.get("MYSTIC_PUBLIC_BASE_URL",DEFAULT_ENDPOINT).rstrip("/"); data=None if body is None else json.dumps(body).encode(); req=request.Request(endpoint+path,data=data,method="POST" if body is not None else "GET",headers={"Authorization":f"Bearer {token()}","Content-Type":"application/json"})
    try:
        with request.urlopen(req,timeout=20) as response: return json.loads(response.read().decode())
    except error.HTTPError as exc:
        try: return json.loads(exc.read().decode())
        except Exception: return {"status":"worker_error","http_status":exc.code}
def host(operation:str, **payload:object) -> dict:
    message=json.dumps({"operation":operation,**payload}).encode()
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
        client.settimeout(5); client.connect(str(SOCKET_PATH)); client.sendall(message); return json.loads(client.recv(1024*1024).decode())
def run_once(wait_seconds:int=0) -> dict:
    claimed=worker("/local-relay/jobs/claim",{"runner_id":runner_id()})
    job=claimed.get("job")
    if not job: return claimed
    dispatched=host("job_next",job=job,queue_count=claimed.get("queue_count",0))
    if dispatched.get("status") != "awaiting_user_submission": return dispatched
    deadline=time.monotonic()+wait_seconds
    while time.monotonic() < deadline:
        current=host("job_get")
        response=current.get("response",{})
        if response.get("response_text"):
            return worker(f"/local-relay/jobs/{job['job_id']}/complete",{"runner_id":runner_id(),**response})
        time.sleep(2)
    return {"status":"awaiting_user_submission","job_id":job["job_id"]}
def main() -> None:
    parser=argparse.ArgumentParser(); group=parser.add_mutually_exclusive_group(required=True)
    for name in ("start","once","status","pause","resume","stop","self-test"): group.add_argument(f"--{name}",action="store_true")
    parser.add_argument("--poll-seconds",type=int,default=4); args=parser.parse_args()
    if args.status: print(json.dumps(host("relay_status"),indent=2)); return
    if args.pause: print(json.dumps(host("relay_pause"),indent=2)); return
    if args.resume: print(json.dumps(host("relay_resume"),indent=2)); return
    if args.stop: print(json.dumps(host("relay_stop"),indent=2)); return
    if args.self_test: print(json.dumps({"status":"manual_action_required","message":"Start the extension and submit an actual relay job; this command never fabricates a Gemini response."},indent=2)); return
    if args.once: print(json.dumps(run_once(),indent=2)); return
    while True:
        result=run_once(wait_seconds=args.poll_seconds)
        print(json.dumps({key:value for key,value in result.items() if key not in {"response_text"}},indent=2)); time.sleep(max(1,args.poll_seconds))
if __name__ == "__main__": main()

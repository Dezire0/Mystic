from __future__ import annotations

import argparse
import json
import os
from typing import Any

import requests

from mystic.lab.engines import builtin_registry
from mystic.lab.engines.reproducibility import payload_hash


def local_engines() -> list[dict[str, Any]]:
    rows=[]
    for manifest in builtin_registry().list(enabled_only=False):
        public=manifest.public_dict()
        rows.append({"engine_id":manifest.engine_id,"display_name":manifest.display_name,"version":manifest.version,"domain":manifest.domain,"capabilities":list(manifest.capabilities),"manifest":public,"manifest_hash":payload_hash(public),"enabled":manifest.enabled,"deprecated":manifest.deprecated})
    return rows


def endpoint() -> str:
    return os.environ.get("MYSTIC_ENGINE_ENDPOINT", "").rstrip("/") + "/internal/engine-runner/registry-sync"


def main() -> int:
    parser=argparse.ArgumentParser(description="Synchronize built-in engine manifests through the authenticated Mystic Worker only.")
    mode=parser.add_mutually_exclusive_group(required=True); mode.add_argument("--check",action="store_true"); mode.add_argument("--apply",action="store_true")
    args=parser.parse_args(); token=os.environ.get("MYSTIC_ENGINE_RUNNER_TOKEN","").strip(); url=endpoint()
    if not token or not url.startswith("https://"):
        print("engine_registry_sync_unconfigured: set MYSTIC_ENGINE_ENDPOINT and MYSTIC_ENGINE_RUNNER_TOKEN in the runner environment")
        return 2
    rows=local_engines()
    try:
        response=requests.post(url,headers={"authorization":f"Bearer {token}","content-type":"application/json","user-agent":"MysticEngineRunner/phase2a"},json={"engines":rows,"apply":args.apply},timeout=20)
    except requests.RequestException:
        print("engine_registry_sync_unavailable")
        return 3
    if response.status_code != 200:
        print("engine_registry_sync_rejected")
        return 4
    payload=response.json(); existing={str(row.get("engine_id")):row for row in payload.get("engines",[])}
    changed=[row["engine_id"] for row in rows if existing.get(row["engine_id"],{}).get("manifest_hash") != row["manifest_hash"]]
    print(json.dumps({"status":payload.get("status","applied" if args.apply else "check"),"engine_count":len(rows),"changed_engine_ids":changed,"deleted_engine_ids":[]},sort_keys=True))
    return 0


if __name__ == "__main__": raise SystemExit(main())

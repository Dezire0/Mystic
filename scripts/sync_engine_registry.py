from __future__ import annotations

import argparse
import os
from typing import Any

from mystic.lab.engines import builtin_registry
from mystic.lab.engines.reproducibility import payload_hash
from mystic.lab.storage import SupabaseLabStorage


def registry_rows() -> list[dict[str, Any]]:
    rows=[]
    for manifest in builtin_registry().list(enabled_only=False):
        public=manifest.public_dict(); rows.append({"engine_id":manifest.engine_id,"display_name":manifest.display_name,"version":manifest.version,"domain":manifest.domain,"capabilities":list(manifest.capabilities),"manifest":public,"manifest_hash":payload_hash(public),"enabled":manifest.enabled,"deprecated":manifest.deprecated,"availability":"available"})
    return rows


def main() -> int:
    parser=argparse.ArgumentParser(description="Synchronize only Mystic's built-in allowlisted engine manifests.")
    mode=parser.add_mutually_exclusive_group(required=True); mode.add_argument("--check",action="store_true"); mode.add_argument("--apply",action="store_true")
    args=parser.parse_args(); storage=SupabaseLabStorage(".")
    if not storage.describe_status()["configured"]:
        print("engine_registry_sync_unconfigured: set MYSTIC_SUPABASE_URL and MYSTIC_SUPABASE_SERVICE_ROLE_KEY in the runner environment")
        return 2
    rows=registry_rows(); existing={str(row.get("engine_id")):row for row in storage._select_rows("lab_engine_registry",{},order="engine_id.asc")}
    changed=[row["engine_id"] for row in rows if existing.get(row["engine_id"],{}).get("manifest_hash") != row["manifest_hash"]]
    if args.check:
        print({"status":"check","engine_count":len(rows),"changed_engine_ids":changed,"unchanged_engine_ids":[row["engine_id"] for row in rows if row["engine_id"] not in changed]})
        return 0
    storage._upsert_rows("lab_engine_registry",rows,on_conflict="engine_id")
    print({"status":"applied","engine_count":len(rows),"changed_engine_ids":changed,"deleted_engine_ids":[]})
    return 0


if __name__ == "__main__": raise SystemExit(main())

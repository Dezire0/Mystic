from __future__ import annotations

import argparse
import json

from mystic.lab.engines import builtin_registry
from mystic.lab.engines.runtime import EngineRuntime


def main() -> int:
    parser=argparse.ArgumentParser(description="Mystic Phase 2A trusted local engine runner (no arbitrary code execution).")
    parser.add_argument("--once",action="store_true"); parser.add_argument("--list-engines",action="store_true"); parser.add_argument("--self-test",action="store_true"); parser.add_argument("--status",action="store_true")
    args=parser.parse_args(); registry=builtin_registry()
    if args.list_engines: print(json.dumps([manifest.public_dict() for manifest in registry.list()],sort_keys=True)); return 0
    if args.self_test:
        from scripts.check_engine_runtime import main as verify
        return verify()
    if args.status: print(json.dumps({"status":"local_runner_ready","engine_count":len(registry.list()),"production_note":"Supabase claim/heartbeat requires a server-side runner deployment and secret."})); return 0
    if args.once: print(json.dumps({"status":"idle","result":EngineRuntime(registry).execute_next()})); return 0
    parser.error("select --status, --list-engines, --self-test, or --once")
    return 2


if __name__ == "__main__": raise SystemExit(main())

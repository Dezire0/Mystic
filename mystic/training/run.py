"""Minimal training entrypoint for dry-run validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mystic.training.environment import audit_training_environment
from mystic.training.launcher import build_training_plan
from mystic.training.modeling import run_local_training


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m mystic.training.run")
    parser.add_argument("--agent", required=True)
    parser.add_argument("--config", required=False)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parents[2]
    plan = build_training_plan(root, args.agent)
    wants_execute = bool(args.execute)
    dry_run = not wants_execute
    local_training = run_local_training(root, args.agent, dry_run=dry_run)
    payload = {
        "plan": plan,
        "environment": audit_training_environment(),
        "dry_run": dry_run,
        "local_training": local_training,
    }
    print(json.dumps(payload, indent=2))
    return 0 if plan["ready"] or dry_run else 1


if __name__ == "__main__":
    raise SystemExit(main())

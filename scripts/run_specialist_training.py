from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.execution_history import write_execution_history_outputs
from mystic.training.executor import execute_training_job


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", required=True)
    parser.add_argument("--backend", default="manual", choices=["manual", "unsloth", "axolotl"])
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--real-train", action="store_true")
    parser.add_argument("--epochs", type=int, default=0)
    parser.add_argument("--max-steps", type=int, default=0)
    parser.add_argument("--learning-rate", type=float, default=0.0)
    parser.add_argument("--sequence-length", type=int, default=0)
    args = parser.parse_args()
    dry_run = not (args.execute or args.real_train)
    payload = execute_training_job(
        ROOT,
        agent=args.agent,
        backend=args.backend,
        dry_run=dry_run,
        overrides={
            "epochs": args.epochs or None,
            "max_steps": args.max_steps or None,
            "learning_rate": args.learning_rate or None,
            "sequence_length": args.sequence_length or None,
        },
    )
    payload["history_outputs"] = write_execution_history_outputs(ROOT / "mystic_data")
    print(json.dumps(payload, indent=2))
    if payload.get("executed") and int(payload.get("returncode", 0) or 0) != 0:
        return int(payload["returncode"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

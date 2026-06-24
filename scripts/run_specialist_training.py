from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.training.executor import execute_training_job


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", required=True)
    parser.add_argument("--backend", default="manual", choices=["manual", "unsloth", "axolotl"])
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--real-train", action="store_true")
    args = parser.parse_args()
    dry_run = not (args.execute or args.real_train)
    payload = execute_training_job(
        ROOT,
        agent=args.agent,
        backend=args.backend,
        dry_run=dry_run,
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

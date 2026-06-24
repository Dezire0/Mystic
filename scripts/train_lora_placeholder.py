from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.training.environment import audit_training_environment
from mystic.training.launcher import build_training_plan

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", required=False, default="raven")
    parser.add_argument("--backend", required=False, default="manual")
    args = parser.parse_args()
    payload = {
        "message": "LoRA training placeholder",
        "agent": args.agent,
        "backend": args.backend,
        "plan": build_training_plan(ROOT, args.agent),
        "environment": audit_training_environment(),
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

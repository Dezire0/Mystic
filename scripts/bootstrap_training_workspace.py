from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.training.bootstrap import init_training_workspace, write_train_ready_seed


def main() -> None:
    base_dir = ROOT / "mystic_data"
    payload = init_training_workspace(base_dir)
    payload["train_ready_files"] = write_train_ready_seed(base_dir)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

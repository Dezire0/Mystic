from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.training.bootstrap import init_internal_data_files, write_train_ready_seed


def main() -> None:
    base_dir = ROOT / "mystic_data"
    payload = {
        "internal_files": init_internal_data_files(base_dir),
        "train_ready_files": write_train_ready_seed(base_dir),
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

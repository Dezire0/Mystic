from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.training.prepare import prepare_train_ready_datasets


def main() -> None:
    base_dir = ROOT / "mystic_data"
    print(json.dumps(prepare_train_ready_datasets(base_dir), indent=2))


if __name__ == "__main__":
    main()


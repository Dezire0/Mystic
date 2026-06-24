from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.training.bootstrap import build_metadata_bundle


def main() -> None:
    base_dir = ROOT / "mystic_data"
    print(json.dumps(build_metadata_bundle(base_dir), indent=2))


if __name__ == "__main__":
    main()

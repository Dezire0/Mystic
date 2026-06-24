from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.training.huggingface import get_hf_auth_status


def main() -> None:
    print(json.dumps(get_hf_auth_status(), indent=2))


if __name__ == "__main__":
    main()


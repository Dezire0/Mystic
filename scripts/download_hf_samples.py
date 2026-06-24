from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.training.huggingface import download_hf_samples


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slugs", nargs="*", default=[])
    parser.add_argument("--max-rows", type=int, default=3)
    args = parser.parse_args()
    base_dir = ROOT / "mystic_data"
    slugs = args.slugs or None
    print(json.dumps(download_hf_samples(base_dir, slugs=slugs, max_rows=args.max_rows), indent=2))


if __name__ == "__main__":
    main()


from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.jsonl_loop import DATA_DIRS, ensure_data_dirs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create local mystic_data folders for Mystic v1.")
    parser.add_argument(
        "--base-dir",
        default=str(ROOT / "mystic_data"),
        help="Base directory for JSONL data files.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = ensure_data_dirs(args.base_dir)
    payload = {
        "base_dir": str(paths.base_dir),
        "created_dirs": [str(paths.base_dir / name) for name in DATA_DIRS],
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

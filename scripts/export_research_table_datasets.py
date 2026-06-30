from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mystic.research_table.dataset_export import export_research_table_datasets


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export Research Table datasets for local LoRA training.")
    parser.add_argument(
        "--root-path",
        default=str(REPO_ROOT),
        help="Mystic repository root. Defaults to the current workspace root.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    payload = export_research_table_datasets(Path(args.root_path))
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

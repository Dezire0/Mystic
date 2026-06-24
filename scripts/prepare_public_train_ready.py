from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.execution_history import write_execution_history_outputs
from mystic.training.public_prepare import prepare_public_train_ready_datasets


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare train_ready JSONL files from real public raw dataset rows.")
    parser.add_argument("--base-dir", default=str(ROOT / "mystic_data"))
    parser.add_argument("--max-rows-per-agent", type=int, default=300)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--no-preserve-existing", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    base_dir = Path(args.base_dir)
    payload = prepare_public_train_ready_datasets(
        base_dir,
        max_rows_per_agent=args.max_rows_per_agent,
        overwrite=bool(args.overwrite),
        preserve_existing=not bool(args.no_preserve_existing),
    )
    payload["history_outputs"] = write_execution_history_outputs(base_dir)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

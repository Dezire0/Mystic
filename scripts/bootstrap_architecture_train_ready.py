from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.execution_history import write_execution_history_outputs
from mystic.training.architecture_bootstrap import bootstrap_architecture_train_ready


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bootstrap missing train_ready JSONL files for architecture-aligned specialist adapters."
    )
    parser.add_argument("--base-dir", default=str(ROOT / "mystic_data"))
    parser.add_argument("--force", action="store_true", help="Overwrite existing non-empty train_ready files.")
    parser.add_argument(
        "--rows-per-agent",
        type=int,
        default=3,
        help="Synthetic bootstrap rows to generate per missing specialist.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    base_dir = Path(args.base_dir)
    payload = bootstrap_architecture_train_ready(
        base_dir,
        force=args.force,
        rows_per_agent=args.rows_per_agent,
    )
    history = write_execution_history_outputs(base_dir)
    print(
        json.dumps(
            {
                "base_dir": str(base_dir),
                "force": bool(args.force),
                "rows_per_agent": int(args.rows_per_agent),
                "bootstrap": payload,
                "history": history,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

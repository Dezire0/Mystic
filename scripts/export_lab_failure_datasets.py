from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.lab.training_export import export_lab_failures_for_raven


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export Virtual Research Lab failures into Raven-compatible JSONL.")
    parser.add_argument("--root-path", default=str(ROOT), help="Mystic repository root.")
    parser.add_argument("--target", default="raven", choices=["raven"])
    parser.add_argument("--output", default="", help="Optional output JSONL path.")
    parser.add_argument("--limit", type=int, default=0, help="Optional maximum number of exported rows.")
    parser.add_argument("--min-failures", type=int, default=1, help="Minimum expected exported rows unless --allow-empty is set.")
    parser.add_argument("--include-non-reusable", action="store_true")
    parser.add_argument("--allow-empty", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root_path)
    output_path = Path(args.output) if args.output else (
        root / "mystic_data" / "datasets" / "lab" / "raven_lab_failures.jsonl"
    )
    try:
        summary = export_lab_failures_for_raven(
            root,
            output_path,
            limit=args.limit or None,
            include_non_reusable=args.include_non_reusable,
            allow_empty=args.allow_empty,
        )
        if not args.allow_empty and int(summary.get("rows_written", 0)) < int(args.min_failures):
            raise ValueError(
                f"Exported lab failure rows {summary.get('rows_written', 0)} did not reach --min-failures {args.min_failures}."
            )
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 1

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

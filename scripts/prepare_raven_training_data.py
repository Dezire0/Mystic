from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.jsonl_loop import ensure_data_dirs
from mystic.raven_training import load_jsonl, normalize_raven_lora_row, split_train_eval, write_jsonl


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare Raven LoRA data into train/eval chat-format JSONL files.")
    parser.add_argument(
        "--input",
        default=str(ROOT / "mystic_data" / "train_ready" / "raven_lora.jsonl"),
        help="Source Raven LoRA JSONL file.",
    )
    parser.add_argument(
        "--train-out",
        default=str(ROOT / "mystic_data" / "train_ready" / "raven_train.jsonl"),
        help="Output train JSONL path.",
    )
    parser.add_argument(
        "--eval-out",
        default=str(ROOT / "mystic_data" / "eval_holdout" / "raven_eval.jsonl"),
        help="Output eval JSONL path.",
    )
    parser.add_argument(
        "--eval-ratio",
        type=float,
        default=0.1,
        help="Fraction of validated rows to place in eval.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional limit on the number of source rows to inspect. Zero means no limit.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ensure_data_dirs(ROOT / "mystic_data")

    source_path = Path(args.input)
    if not source_path.exists():
        print(json.dumps({"error": f"Input file not found: {source_path}"}, indent=2))
        return 1
    if not 0 <= args.eval_ratio < 1:
        print(json.dumps({"error": "--eval-ratio must be in [0, 1)."}, indent=2))
        return 1

    source_rows = load_jsonl(source_path)
    if args.limit > 0:
        source_rows = source_rows[: args.limit]

    validated_rows: list[dict[str, object]] = []
    skipped: list[dict[str, str]] = []
    for index, row in enumerate(source_rows):
        normalized, error = normalize_raven_lora_row(row)
        if normalized is None:
            skipped.append({"index": str(index), "error": error or "unknown validation error"})
            continue
        validated_rows.append(normalized)

    train_rows, eval_rows = split_train_eval(validated_rows, args.eval_ratio)
    write_jsonl(args.train_out, train_rows)
    write_jsonl(args.eval_out, eval_rows)

    payload = {
        "input_file": str(source_path),
        "validated_rows": len(validated_rows),
        "skipped_rows": len(skipped),
        "train_rows": len(train_rows),
        "eval_rows": len(eval_rows),
        "train_out": str(args.train_out),
        "eval_out": str(args.eval_out),
    }
    if skipped:
        payload["skipped_examples"] = skipped[:5]
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

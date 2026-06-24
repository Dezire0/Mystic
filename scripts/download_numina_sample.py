from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from datasets import load_dataset

from mystic.jsonl_loop import NUMINA_REPO_ID, append_jsonl, ensure_data_dirs, normalize_numina_row, read_jsonl


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download NuminaMath-CoT samples into local JSONL.")
    parser.add_argument(
        "--base-dir",
        default=str(ROOT / "mystic_data"),
        help="Base directory for local JSONL artifacts.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Number of normalized samples to store.",
    )
    parser.add_argument(
        "--split",
        default="train",
        help="Dataset split to stream.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = ensure_data_dirs(args.base_dir)
    existing = read_jsonl(paths.raw_file)
    existing_ids = {str(item["sample_id"]) for item in existing}
    needed = max(args.limit - len(existing_ids), 0)

    downloaded = 0
    if needed > 0:
        dataset = load_dataset(NUMINA_REPO_ID, split=args.split, streaming=True)
        seen_index = 0
        for row in dataset:
            normalized = normalize_numina_row(seen_index, dict(row))
            seen_index += 1
            sample_id = normalized["sample_id"]
            if sample_id in existing_ids:
                continue
            append_jsonl(paths.raw_file, normalized)
            existing_ids.add(sample_id)
            downloaded += 1
            if downloaded >= needed:
                break

    payload = {
        "dataset": NUMINA_REPO_ID,
        "output_file": str(paths.raw_file),
        "requested_limit": args.limit,
        "existing_count": len(existing),
        "downloaded_count": downloaded,
        "final_count": len(existing_ids),
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

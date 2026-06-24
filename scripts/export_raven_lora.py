from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.jsonl_loop import ensure_data_dirs, export_raven_lora_rows, read_jsonl


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export Raven critique rows into LoRA-ready JSONL.")
    parser.add_argument(
        "--base-dir",
        default=str(ROOT / "mystic_data"),
        help="Base directory for JSONL artifacts.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = ensure_data_dirs(args.base_dir)
    critiques = read_jsonl(paths.raven_critiques_file)
    rows = export_raven_lora_rows(critiques)
    payload_text = "\n".join(json.dumps(row, ensure_ascii=True) for row in rows) + ("\n" if rows else "")
    paths.raven_lora_file.write_text(payload_text, encoding="utf-8")
    paths.raven_lora_train_ready_file.write_text(payload_text, encoding="utf-8")
    payload = {
        "source_file": str(paths.raven_critiques_file),
        "output_files": [
            str(paths.raven_lora_file),
            str(paths.raven_lora_train_ready_file),
        ],
        "row_count": len(rows),
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

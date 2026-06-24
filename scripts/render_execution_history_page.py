from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.execution_history import write_execution_history_outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render a simple HTML execution history page from Mystic logs.")
    parser.add_argument("--base-dir", default=str(ROOT / "mystic_data"))
    parser.add_argument("--output-html", default="")
    parser.add_argument("--output-json", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    base_dir = Path(args.base_dir)
    reports_dir = base_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    payload = write_execution_history_outputs(base_dir)
    output_html = Path(args.output_html) if args.output_html else Path(str(payload["output_html"]))
    output_json = Path(args.output_json) if args.output_json else Path(str(payload["output_json"]))
    if args.output_html or args.output_json:
        default_html = Path(str(payload["output_html"]))
        default_json = Path(str(payload["output_json"]))
        if args.output_html and output_html != default_html:
            output_html.write_text(default_html.read_text(encoding="utf-8"), encoding="utf-8")
        if args.output_json and output_json != default_json:
            output_json.write_text(default_json.read_text(encoding="utf-8"), encoding="utf-8")

    print(
        json.dumps(
            {
                "generated_at": payload["generated_at"],
                "record_count": payload["record_count"],
                "output_html": str(output_html),
                "output_json": str(output_json),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

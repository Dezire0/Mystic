from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.execution_history import collect_execution_records, render_execution_history_html


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


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

    output_html = Path(args.output_html) if args.output_html else reports_dir / "execution_history.html"
    output_json = Path(args.output_json) if args.output_json else reports_dir / "execution_history.json"

    records = collect_execution_records(base_dir)
    generated_at = now_iso()
    html_text = render_execution_history_html(records, generated_at=generated_at)
    output_html.write_text(html_text, encoding="utf-8")

    json_payload = {
        "generated_at": generated_at,
        "record_count": len(records),
        "records": [
            {
                "record_id": record.record_id,
                "timestamp": record.timestamp,
                "part": record.part,
                "model_name": record.model_name,
                "success": record.success,
                "duration_seconds": record.duration_seconds,
                "source": record.source,
                "status": record.status,
            }
            for record in records
        ],
    }
    output_json.write_text(json.dumps(json_payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "generated_at": generated_at,
                "record_count": len(records),
                "output_html": str(output_html),
                "output_json": str(output_json),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

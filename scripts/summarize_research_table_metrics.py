from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mystic.research_table.metrics import summarize_research_table_metrics, write_research_table_metrics_reports


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize Research Table metrics.")
    parser.add_argument(
        "--root-path",
        default=str(REPO_ROOT),
        help="Mystic repository root. Defaults to the current workspace root.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root_path = Path(args.root_path)
    payload = summarize_research_table_metrics(root_path)
    output_paths = write_research_table_metrics_reports(root_path, payload)
    print(
        json.dumps(
            {
                "generated_at": payload.get("generated_at", ""),
                "sessions": len(payload.get("sessions", [])),
                "models": len(payload.get("models", [])),
                "tools": len(payload.get("tools", [])),
                "warnings": len(payload.get("warnings", [])),
                "output_paths": output_paths,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

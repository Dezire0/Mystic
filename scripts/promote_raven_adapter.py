from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.jsonl_loop import append_jsonl, ensure_data_dirs, read_jsonl
from mystic.raven_compare import should_promote_adapter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Promote a Raven adapter to active status using comparison logs.")
    parser.add_argument("--model-id", required=True, help="Registered model id to promote.")
    parser.add_argument(
        "--comparison-log",
        default=str(ROOT / "mystic_data" / "logs" / "raven_comparison_results.jsonl"),
        help="Comparison log JSONL path.",
    )
    return parser


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _load_registry(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"models": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_summary(rows: list[dict[str, object]]) -> dict[str, object] | None:
    summaries = [row for row in rows if row.get("kind") == "summary"]
    return summaries[-1] if summaries else None


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = ensure_data_dirs(ROOT / "mystic_data")
    comparison_rows = read_jsonl(args.comparison_log)
    summary = _latest_summary(comparison_rows)
    if summary is None:
        print(json.dumps({"error": f"No summary comparison rows found in {args.comparison_log}"}, indent=2))
        return 1

    metrics = summary.get("metrics", {})
    promote, reason = should_promote_adapter(metrics)

    registry_path = ROOT / "mystic_data" / "metadata" / "model_versions.json"
    registry = _load_registry(registry_path)
    models = list(registry.get("models", []))
    target_entry = None
    for model in models:
        if model.get("model_id") == args.model_id:
            target_entry = model
        if "active" in model:
            model["active"] = False

    if target_entry is None:
        print(json.dumps({"error": f"Model id not found in registry: {args.model_id}"}, indent=2))
        return 1

    target_entry["active"] = bool(promote)
    target_entry["promoted_at"] = now_iso() if promote else None
    target_entry["promotion_reason"] = reason
    target_entry["metrics_snapshot"] = metrics

    registry["models"] = models
    registry_path.write_text(json.dumps(registry, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    decision_log = {
        "event_id": str(uuid.uuid4()),
        "timestamp": now_iso(),
        "model_id": args.model_id,
        "promoted": promote,
        "reason": reason,
        "metrics_snapshot": metrics,
        "comparison_log": str(args.comparison_log),
        "registry_path": str(registry_path),
    }
    append_jsonl(paths.raven_promotion_log_file, decision_log)
    print(json.dumps(decision_log, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

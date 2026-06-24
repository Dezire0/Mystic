from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Register adapter metadata in mystic_data/metadata/model_versions.json.")
    parser.add_argument("--model-id", required=True, help="Logical adapter identifier.")
    parser.add_argument("--base-model", required=True, help="Base model name.")
    parser.add_argument("--adapter-path", required=True, help="Adapter directory path.")
    parser.add_argument(
        "--training-data",
        default="mystic_data/train_ready/raven_train.jsonl",
        help="Training data path.",
    )
    parser.add_argument(
        "--eval-file",
        default="mystic_data/eval_holdout/raven_eval.jsonl",
        help="Evaluation file path.",
    )
    parser.add_argument(
        "--metrics",
        default="{}",
        help="JSON object string with metrics to store.",
    )
    parser.add_argument("--notes", default="", help="Free-form notes.")
    return parser


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def load_registry(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"models": []}
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    registry_path = ROOT / "mystic_data" / "metadata" / "model_versions.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry = load_registry(registry_path)

    try:
        metrics = json.loads(args.metrics)
    except json.JSONDecodeError as exc:
        print(json.dumps({"error": f"Invalid --metrics JSON: {exc}"}, indent=2))
        return 1

    entry = {
        "model_id": args.model_id,
        "base_model": args.base_model,
        "adapter_path": args.adapter_path,
        "created_at": now_iso(),
        "training_data": args.training_data,
        "eval_file": args.eval_file,
        "metrics": metrics,
        "notes": args.notes,
    }
    models = list(registry.get("models", []))
    models.append(entry)
    registry["models"] = models
    registry_path.write_text(json.dumps(registry, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps({"registry_path": str(registry_path), "registered_model": entry}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

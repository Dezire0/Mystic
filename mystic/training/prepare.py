"""Prepare train-ready specialist datasets from internal Mystic data."""

from __future__ import annotations

from collections import defaultdict
from hashlib import md5
import json
from pathlib import Path

from mystic.training.blueprints import AGENT_DIVISIONS, INTERNAL_DATASETS, INTERNAL_RECORD_ROUTING, TRAINING_TARGETS


def prepare_train_ready_datasets(base_dir: str | Path) -> dict[str, object]:
    root = Path(base_dir)
    processed_root = root / "processed" / "internal_mystic_data"
    train_ready_root = root / "train_ready"
    eval_root = root / "eval_holdout"
    train_ready_root.mkdir(parents=True, exist_ok=True)
    eval_root.mkdir(parents=True, exist_ok=True)

    target_by_agent = {item["agent"]: item for item in TRAINING_TARGETS}
    rows_by_agent: dict[str, list[dict]] = defaultdict(list)

    for record_type in INTERNAL_DATASETS:
        path = processed_root / f"{record_type}.jsonl"
        if not path.exists():
            continue
        for record in _iter_jsonl(path):
            for agent in INTERNAL_RECORD_ROUTING.get(record_type, []):
                rows_by_agent[agent].append(
                    _to_train_ready_row(record_type, record, target_by_agent[agent])
                )

    written_files: list[str] = []
    split_buckets: dict[str, list[dict]] = {"train": [], "validation": [], "test": []}

    for agent, rows in rows_by_agent.items():
        agent_path = train_ready_root / f"{agent}_train_ready.jsonl"
        _write_jsonl(agent_path, rows)
        written_files.append(str(agent_path))
        for row in rows:
            split_name = _split_for_row(row)
            row["metadata"]["split"] = split_name
            split_buckets[split_name].append(row)

    train_path = train_ready_root / "train.jsonl"
    validation_path = eval_root / "validation.jsonl"
    test_path = eval_root / "test.jsonl"
    _write_jsonl(train_path, split_buckets["train"])
    _write_jsonl(validation_path, split_buckets["validation"])
    _write_jsonl(test_path, split_buckets["test"])
    written_files.extend([str(train_path), str(validation_path), str(test_path)])

    return {
        "agent_files": written_files[:-3],
        "split_files": [str(train_path), str(validation_path), str(test_path)],
        "row_counts": {agent: len(rows) for agent, rows in rows_by_agent.items()},
        "split_counts": {name: len(items) for name, items in split_buckets.items()},
    }


def _to_train_ready_row(record_type: str, record: dict, training_target: dict) -> dict:
    metadata = dict(record.get("metadata", {}))
    metadata.update(
        {
            "dataset": record_type,
            "split": "train",
            "target_agent": training_target["agent"],
            "target_adapter": training_target["adapter"],
            "base_model": training_target["base_model"],
        }
    )
    return {
        "agent": training_target["agent"],
        "division": AGENT_DIVISIONS.get(training_target["agent"], "unknown"),
        "instruction": record.get("instruction", ""),
        "input": record.get("input", ""),
        "output": record.get("output", ""),
        "status": record.get("status", "UNKNOWN"),
        "metadata": metadata,
    }


def _split_for_row(row: dict) -> str:
    fingerprint = f"{row['agent']}|{row['instruction']}|{row['input']}|{row['output']}"
    bucket = int(md5(fingerprint.encode("utf-8")).hexdigest(), 16) % 10
    if bucket == 0:
        return "test"
    if bucket == 1:
        return "validation"
    return "train"


def _iter_jsonl(path: Path):
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        yield json.loads(stripped)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    payload = "\n".join(json.dumps(row, ensure_ascii=True) for row in rows)
    if payload:
        payload += "\n"
    path.write_text(payload, encoding="utf-8")


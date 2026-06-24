"""Training-bootstrap file generation."""

from __future__ import annotations

from pathlib import Path

from mystic.training.blueprints import (
    CHECKLIST_DATASETS,
    INTERNAL_DATASETS,
    SOFTWARE_STACK,
    TRAINING_TARGETS,
    write_json,
)


def init_internal_data_files(base_dir: str | Path) -> list[str]:
    root = Path(base_dir)
    internal_root = root / "processed" / "internal_mystic_data"
    internal_root.mkdir(parents=True, exist_ok=True)
    created = []
    for dataset_name in INTERNAL_DATASETS:
        path = internal_root / f"{dataset_name}.jsonl"
        if not path.exists():
            path.write_text("", encoding="utf-8")
        created.append(str(path))
    return created


def build_metadata_bundle(base_dir: str | Path) -> dict[str, str]:
    root = Path(base_dir)
    metadata_root = root / "metadata"
    schemas_root = metadata_root / "schemas"
    manifests_root = metadata_root / "manifests"
    training_root = manifests_root / "training_targets"
    schemas_root.mkdir(parents=True, exist_ok=True)
    training_root.mkdir(parents=True, exist_ok=True)

    internal_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "MysticInternalRecord",
        "type": "object",
        "required": ["record_type", "instruction", "input", "output", "metadata"],
        "properties": {
            "record_type": {"type": "string"},
            "instruction": {"type": "string"},
            "input": {"type": "string"},
            "output": {"type": "string"},
            "status": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "metadata": {
                "type": "object",
                "required": ["source", "created_at"],
                "properties": {
                    "source": {"type": "string"},
                    "created_at": {"type": "string"},
                    "session_id": {"type": ["string", "null"]},
                    "agent": {"type": ["string", "null"]},
                    "model": {"type": ["string", "null"]},
                    "adapter": {"type": ["string", "null"]},
                },
                "additionalProperties": True,
            },
        },
        "additionalProperties": True,
    }
    write_json(schemas_root / "internal_record.schema.json", internal_schema)

    train_ready_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "MysticTrainReadyRow",
        "type": "object",
        "required": ["agent", "instruction", "input", "output", "metadata"],
        "properties": {
            "agent": {"type": "string"},
            "division": {"type": "string"},
            "instruction": {"type": "string"},
            "input": {"type": "string"},
            "output": {"type": "string"},
            "status": {"type": "string"},
            "metadata": {
                "type": "object",
                "required": ["dataset", "split"],
                "properties": {
                    "dataset": {"type": "string"},
                    "split": {"type": "string"},
                    "session_id": {"type": ["string", "null"]},
                    "model": {"type": ["string", "null"]},
                    "adapter": {"type": ["string", "null"]},
                },
                "additionalProperties": True,
            },
        },
        "additionalProperties": True,
    }
    write_json(schemas_root / "train_ready_row.schema.json", train_ready_schema)

    dataset_catalog = {
        "internal_datasets": INTERNAL_DATASETS,
        "priority_datasets": CHECKLIST_DATASETS,
        "software_stack": SOFTWARE_STACK,
    }
    write_json(metadata_root / "dataset_catalog.json", dataset_catalog)

    training_manifest = {
        "version": "0.1",
        "description": "Checklist-derived specialist training plan",
        "targets": TRAINING_TARGETS,
    }
    write_json(manifests_root / "training_manifest.json", training_manifest)

    for target in TRAINING_TARGETS:
        payload = {
            "adapter": target["adapter"],
            "agent": target["agent"],
            "label": target["label"],
            "priority": target["priority"],
            "base_model": target["base_model"],
            "datasets": target["datasets"],
            "train_ready_output": f"mystic_data/train_ready/{target['agent']}_train_ready.jsonl",
        }
        write_json(training_root / f"{target['agent']}.json", payload)

    split_manifest = {
        "train": {"path": "mystic_data/train_ready/train.jsonl"},
        "validation": {"path": "mystic_data/eval_holdout/validation.jsonl"},
        "test": {"path": "mystic_data/eval_holdout/test.jsonl"},
    }
    write_json(manifests_root / "dataset_splits.json", split_manifest)

    return {
        "metadata_root": str(metadata_root),
        "schemas_root": str(schemas_root),
        "manifests_root": str(manifests_root),
    }


def init_training_workspace(base_dir: str | Path) -> dict[str, object]:
    created_files = init_internal_data_files(base_dir)
    bundle = build_metadata_bundle(base_dir)
    return {"internal_files": created_files, **bundle}


def write_train_ready_seed(base_dir: str | Path) -> list[str]:
    root = Path(base_dir)
    train_ready_root = root / "train_ready"
    train_ready_root.mkdir(parents=True, exist_ok=True)
    created = []
    for target in TRAINING_TARGETS:
        path = train_ready_root / f"{target['agent']}_train_ready.jsonl"
        if not path.exists():
            path.write_text("", encoding="utf-8")
        created.append(str(path))
    return created


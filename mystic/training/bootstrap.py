"""Training-bootstrap file generation."""

from __future__ import annotations

from pathlib import Path

from mystic.training.blueprints import (
    ARCHITECTURE_TRAINING_TARGETS,
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


def _count_jsonl_rows(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _build_architecture_plan_markdown(base_dir: Path) -> str:
    snapshot = {
        "numina_raw_rows": _count_jsonl_rows(base_dir / "raw" / "numina_math_cot_100.jsonl"),
        "raven_critiques_rows": _count_jsonl_rows(base_dir / "internal" / "raven_critiques.jsonl"),
        "failed_proofs_rows": _count_jsonl_rows(base_dir / "internal" / "failed_proofs.jsonl"),
        "raven_lora_rows": _count_jsonl_rows(base_dir / "train_ready" / "raven_lora.jsonl"),
        "raven_train_rows": _count_jsonl_rows(base_dir / "train_ready" / "raven_train.jsonl"),
        "raven_eval_rows": _count_jsonl_rows(base_dir / "eval_holdout" / "raven_eval.jsonl"),
    }

    lines = [
        "# Mystic Architecture-Aligned Training Plan",
        "",
        "This plan follows `mystic_v0_1_architecture_canvas.md` instead of collapsing Mystic into one generic model.",
        "Even when two agents use the same base model, the code structure and future adapter path remain separate.",
        "",
        "## Current Local Snapshot",
        "",
        f"- Numina raw rows: `{snapshot['numina_raw_rows']}`",
        f"- Raven critiques rows: `{snapshot['raven_critiques_rows']}`",
        f"- Failed proofs rows: `{snapshot['failed_proofs_rows']}`",
        f"- Raven LoRA export rows: `{snapshot['raven_lora_rows']}`",
        f"- Raven train rows: `{snapshot['raven_train_rows']}`",
        f"- Raven eval rows: `{snapshot['raven_eval_rows']}`",
        "",
        "## Architecture Targets",
        "",
    ]

    for index, target in enumerate(ARCHITECTURE_TRAINING_TARGETS, start=1):
        adapter_text = target["adapter"] if target["adapter"] else "none"
        datasets = ", ".join(target["datasets"])
        lines.extend(
            [
                f"{index}. {target['name']} - model `{target['model']}` - adapter `{adapter_text}`",
                f"   Division: {target['division']}",
                f"   Implementation priority: {target['implementation_priority']}",
                f"   Current stage: {target['current_stage']}",
                f"   Checklist datasets: {datasets}",
                f"   Training plan: {target['training_plan']}",
                "",
            ]
        )

    lines.extend(
        [
            "## Execution Note",
            "",
            "- The current repository can run a real Raven training cycle through the Qwen 0.5B Kaggle path.",
            "- Other agents are mapped here for data planning and manifest alignment, but most still need dedicated train-ready builders, configs, and higher-volume datasets before real training starts.",
            "",
        ]
    )
    return "\n".join(lines)


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

    architecture_plan = {
        "version": "0.1",
        "description": "Architecture-aligned training plan derived from mystic_v0_1_architecture_canvas.md and the checklist datasets",
        "targets": ARCHITECTURE_TRAINING_TARGETS,
    }
    write_json(manifests_root / "architecture_training_plan.json", architecture_plan)

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

    architecture_plan_markdown = _build_architecture_plan_markdown(root)
    (metadata_root / "architecture_training_plan.md").write_text(
        architecture_plan_markdown + "\n",
        encoding="utf-8",
    )

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

"""Minimal local specialist training backend."""

from __future__ import annotations

import json
from pathlib import Path

from mystic.training.config import load_training_config, load_runtime_defaults


def run_local_training(
    root_path: str | Path,
    agent: str,
    dry_run: bool = True,
    overrides: dict[str, object] | None = None,
) -> dict[str, object]:
    root = Path(root_path)
    config = load_training_config(root, agent)
    runtime = load_runtime_defaults(root)
    plan = _build_local_plan(root, config, runtime, overrides=overrides)

    if dry_run:
        return {"executed": False, "plan": plan}

    result = _execute_local_training(plan)
    return {"executed": True, "plan": plan, "result": result}


def _build_local_plan(root: Path, config: dict, runtime: dict, overrides: dict[str, object] | None = None) -> dict:
    train_ready_path = root / config["train_ready_path"]
    output_dir = root / config["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    merged = dict(runtime.get("defaults", {}))
    merged.update(config)
    if overrides:
        merged.update({key: value for key, value in overrides.items() if value not in (None, "")})
    model_name = merged.get("training_model") or merged.get("smoke_model") or merged["base_model"]
    dataset_size = _count_jsonl_rows(train_ready_path)
    return {
        "agent": merged["agent"],
        "adapter_name": merged["adapter_name"],
        "base_model": merged["base_model"],
        "model_name": model_name,
        "method": merged["method"],
        "train_ready_path": str(train_ready_path),
        "output_dir": str(output_dir),
        "epochs": int(merged.get("epochs", 1)),
        "max_steps": int(merged.get("max_steps", 10)),
        "learning_rate": float(merged.get("learning_rate", 2e-4)),
        "micro_batch_size": int(merged.get("micro_batch_size", 1)),
        "gradient_accumulation_steps": int(merged.get("gradient_accumulation_steps", 4)),
        "sequence_length": int(merged.get("sequence_length", 512)),
        "lora_r": int(merged.get("lora_r", 8)),
        "lora_alpha": int(merged.get("lora_alpha", 16)),
        "lora_dropout": float(merged.get("lora_dropout", 0.05)),
        "target_modules": merged.get("target_modules", []),
        "dataset_size": dataset_size,
    }


def _execute_local_training(plan: dict) -> dict:
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        DataCollatorForLanguageModeling,
        Trainer,
        TrainingArguments,
    )

    records = _load_training_records(Path(plan["train_ready_path"]))
    if not records:
        raise ValueError("No training rows found for the requested specialist")

    tokenizer = AutoTokenizer.from_pretrained(plan["model_name"])
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(plan["model_name"])
    lora_config = LoraConfig(
        r=plan["lora_r"],
        lora_alpha=plan["lora_alpha"],
        target_modules=plan["target_modules"] or _infer_target_modules(model),
        lora_dropout=plan["lora_dropout"],
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)

    dataset = Dataset.from_list(
        [{"text": _format_row_text(row)} for row in records]
    )

    def tokenize(batch):
        return tokenizer(
            batch["text"],
            truncation=True,
            max_length=plan["sequence_length"],
            padding="max_length",
        )

    tokenized = dataset.map(tokenize, batched=True, remove_columns=["text"])
    data_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

    args = TrainingArguments(
        output_dir=plan["output_dir"],
        num_train_epochs=plan["epochs"],
        per_device_train_batch_size=plan["micro_batch_size"],
        gradient_accumulation_steps=plan["gradient_accumulation_steps"],
        max_steps=plan["max_steps"],
        learning_rate=plan["learning_rate"],
        logging_steps=1,
        save_steps=max(plan["max_steps"], 1),
        report_to=[],
        remove_unused_columns=False,
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=tokenized,
        data_collator=data_collator,
    )
    train_result = trainer.train()
    model.save_pretrained(plan["output_dir"])
    tokenizer.save_pretrained(plan["output_dir"])

    metrics_path = Path(plan["output_dir"]) / "train_metrics.json"
    metrics = dict(train_result.metrics)
    metrics_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return {
        "metrics_path": str(metrics_path),
        "metrics": metrics,
        "saved_model_dir": plan["output_dir"],
    }


def _format_row_text(row: dict) -> str:
    return (
        f"Instruction:\n{row.get('instruction', '')}\n\n"
        f"Input:\n{row.get('input', '')}\n\n"
        f"Output:\n{row.get('output', '')}"
    )


def _load_training_records(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(json.loads(stripped))
    return rows


def _count_jsonl_rows(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _infer_target_modules(model) -> list[str]:
    module_names = list(dict.fromkeys(name.split(".")[-1] for name, _ in model.named_modules()))
    preferred = [
        "q_proj",
        "k_proj",
        "v_proj",
        "o_proj",
        "gate_proj",
        "up_proj",
        "down_proj",
        "c_attn",
        "c_proj",
        "query_key_value",
        "dense",
    ]
    found = [name for name in preferred if name in module_names]
    if found:
        return found
    linearish = [name for name in module_names if "proj" in name or "attn" in name]
    return linearish[:8] or ["c_attn", "c_proj"]

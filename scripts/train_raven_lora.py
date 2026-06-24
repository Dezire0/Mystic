from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import platform
import sys
from typing import Any
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.jsonl_loop import ensure_data_dirs
from mystic.raven_training import append_jsonl, load_jsonl, render_chat_text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train a Raven LoRA/QLoRA adapter from local JSONL data.")
    parser.add_argument("--base-model", default="", help="Base model name.")
    parser.add_argument(
        "--train-file",
        default=str(ROOT / "mystic_data" / "train_ready" / "raven_train.jsonl"),
        help="Prepared train JSONL file.",
    )
    parser.add_argument(
        "--eval-file",
        default=str(ROOT / "mystic_data" / "eval_holdout" / "raven_eval.jsonl"),
        help="Prepared eval JSONL file.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "mystic_data" / "adapters" / "raven_lora_v0"),
        help="Adapter output directory.",
    )
    parser.add_argument("--epochs", type=int, default=0, help="Number of training epochs.")
    parser.add_argument("--batch-size", type=int, default=0, help="Per-device batch size.")
    parser.add_argument("--learning-rate", type=float, default=0.0, help="Learning rate.")
    parser.add_argument("--max-length", type=int, default=0, help="Maximum sequence length.")
    parser.add_argument("--qlora", action="store_true", help="Enable 4-bit QLoRA when supported.")
    parser.add_argument("--dry-run", action="store_true", help="Only validate data and tokenization.")
    return parser


def load_training_defaults(config_path: str | Path) -> dict[str, Any]:
    return json.loads(Path(config_path).read_text(encoding="utf-8"))


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def load_prepared_rows(path: str | Path) -> list[dict[str, Any]]:
    rows = load_jsonl(path)
    return [row for row in rows if row.get("messages") and row.get("assistant_output")]


def choose_device(torch_module: Any) -> str:
    if torch_module.cuda.is_available():
        return "cuda"
    if torch_module.backends.mps.is_available():
        return "mps"
    return "cpu"


def qlora_support_status(torch_module: Any) -> dict[str, Any]:
    bitsandbytes_available = False
    try:
        import bitsandbytes  # noqa: F401

        bitsandbytes_available = True
    except ModuleNotFoundError:
        bitsandbytes_available = False

    return {
        "bitsandbytes_available": bitsandbytes_available,
        "cuda_available": bool(torch_module.cuda.is_available()),
        "platform": platform.system(),
        "supported": bitsandbytes_available and bool(torch_module.cuda.is_available()) and platform.system() != "Darwin",
    }


def write_config_snapshot(output_dir: str | Path, config: dict[str, Any]) -> Path:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    snapshot = target / "training_config.json"
    snapshot.write_text(json.dumps(config, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return snapshot


def build_log_event(
    *,
    run_id: str,
    status: str,
    config: dict[str, Any],
    metrics: dict[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "event_id": str(uuid.uuid4()),
        "timestamp": now_iso(),
        "run_id": run_id,
        "status": status,
        "base_model": config["base_model"],
        "train_file": config["train_file"],
        "eval_file": config["eval_file"],
        "output_dir": config["output_dir"],
        "qlora": config["qlora"],
        "dry_run": config["dry_run"],
        "metrics": metrics or {},
        "error": error,
    }


def tokenize_rows(tokenizer: Any, rows: list[dict[str, Any]], max_length: int) -> tuple[list[dict[str, Any]], dict[str, float]]:
    tokenized_rows: list[dict[str, Any]] = []
    lengths: list[int] = []
    for row in rows:
        text = render_chat_text(tokenizer, row["messages"], add_generation_prompt=False)
        encoded = tokenizer(
            text,
            truncation=True,
            max_length=max_length,
            padding="max_length",
        )
        input_ids = list(encoded["input_ids"])
        attention_mask = list(encoded["attention_mask"])
        tokenized_rows.append(
            {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
                "labels": list(input_ids),
            }
        )
        lengths.append(int(sum(attention_mask)))

    if not lengths:
        return tokenized_rows, {"min": 0.0, "max": 0.0, "avg": 0.0}
    return tokenized_rows, {
        "min": float(min(lengths)),
        "max": float(max(lengths)),
        "avg": float(sum(lengths) / len(lengths)),
    }


def build_runtime_config(args: argparse.Namespace) -> dict[str, Any]:
    defaults = load_training_defaults(ROOT / "configs" / "training_raven.json")
    config = {
        "base_model": args.base_model or defaults["base_model"],
        "adapter_name": defaults["adapter_name"],
        "train_file": str(Path(args.train_file)),
        "eval_file": str(Path(args.eval_file)),
        "output_dir": str(Path(args.output_dir)),
        "epochs": args.epochs or int(defaults["epochs"]),
        "batch_size": args.batch_size or int(defaults["batch_size"]),
        "learning_rate": args.learning_rate or float(defaults["learning_rate"]),
        "max_length": args.max_length or int(defaults["max_length"]),
        "lora_r": int(defaults["lora_r"]),
        "lora_alpha": int(defaults["lora_alpha"]),
        "lora_dropout": float(defaults["lora_dropout"]),
        "qlora": bool(args.qlora),
        "dry_run": bool(args.dry_run),
    }
    return config


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = ensure_data_dirs(ROOT / "mystic_data")
    config = build_runtime_config(args)
    run_id = str(uuid.uuid4())

    train_rows = load_prepared_rows(config["train_file"])
    eval_rows = load_prepared_rows(config["eval_file"])
    if not train_rows:
        print(json.dumps({"error": f"No train rows found in {config['train_file']}"}, indent=2))
        return 1

    try:
        import torch
        from transformers import AutoTokenizer
    except ModuleNotFoundError as exc:
        append_jsonl(paths.training_log_file, build_log_event(run_id=run_id, status="IMPORT_ERROR", config=config, error=str(exc)))
        print(json.dumps({"error": str(exc)}, indent=2))
        return 1

    qlora_status = qlora_support_status(torch)
    device = choose_device(torch)
    config["device"] = device
    config["qlora_support"] = qlora_status
    snapshot_path = write_config_snapshot(config["output_dir"], config)

    if config["qlora"] and not qlora_status["supported"]:
        message = (
            "QLoRA is not available on this machine. "
            "Run QLoRA on a Linux NVIDIA GPU environment such as Colab, Kaggle, or RunPod."
        )
        append_jsonl(paths.training_log_file, build_log_event(run_id=run_id, status="QLORA_UNSUPPORTED", config=config, error=message))
        print(json.dumps({"error": message, "qlora_support": qlora_status}, indent=2))
        return 1

    print(f"[info] loading tokenizer for {config['base_model']}")
    tokenizer = AutoTokenizer.from_pretrained(config["base_model"])
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token or tokenizer.unk_token

    train_tokenized, train_lengths = tokenize_rows(tokenizer, train_rows, config["max_length"])
    eval_tokenized, eval_lengths = tokenize_rows(tokenizer, eval_rows, config["max_length"])

    dry_run_metrics = {
        "train_rows": len(train_rows),
        "eval_rows": len(eval_rows),
        "train_token_lengths": train_lengths,
        "eval_token_lengths": eval_lengths,
        "device": device,
        "qlora_support": qlora_status,
        "config_snapshot": str(snapshot_path),
    }
    if config["dry_run"]:
        append_jsonl(paths.training_log_file, build_log_event(run_id=run_id, status="DRY_RUN_OK", config=config, metrics=dry_run_metrics))
        print(json.dumps({"run_id": run_id, "status": "DRY_RUN_OK", "metrics": dry_run_metrics}, indent=2))
        return 0

    try:
        from datasets import Dataset
        from peft import LoraConfig, get_peft_model
        from transformers import AutoModelForCausalLM, Trainer, TrainingArguments
        if config["qlora"]:
            from peft import prepare_model_for_kbit_training
            from transformers import BitsAndBytesConfig
    except ModuleNotFoundError as exc:
        append_jsonl(paths.training_log_file, build_log_event(run_id=run_id, status="IMPORT_ERROR", config=config, error=str(exc)))
        print(json.dumps({"error": str(exc)}, indent=2))
        return 1

    print(f"[info] loading model on {device}")
    model_kwargs: dict[str, Any] = {}
    if device == "cuda":
        model_kwargs["torch_dtype"] = torch.float16
    elif device == "mps":
        model_kwargs["torch_dtype"] = torch.float16

    if config["qlora"]:
        model_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.float16,
        )
        model_kwargs["device_map"] = "auto"

    model = AutoModelForCausalLM.from_pretrained(config["base_model"], **model_kwargs)
    if config["qlora"]:
        model = prepare_model_for_kbit_training(model)

    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
    lora_config = LoraConfig(
        r=config["lora_r"],
        lora_alpha=config["lora_alpha"],
        lora_dropout=config["lora_dropout"],
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=target_modules,
    )
    model = get_peft_model(model, lora_config)

    train_dataset = Dataset.from_list(train_tokenized)
    eval_dataset = Dataset.from_list(eval_tokenized) if eval_tokenized else None

    training_args = TrainingArguments(
        output_dir=config["output_dir"],
        num_train_epochs=config["epochs"],
        per_device_train_batch_size=config["batch_size"],
        per_device_eval_batch_size=config["batch_size"],
        learning_rate=config["learning_rate"],
        logging_steps=1,
        save_strategy="epoch",
        evaluation_strategy="epoch" if eval_dataset is not None else "no",
        report_to=[],
        remove_unused_columns=False,
        fp16=bool(device == "cuda"),
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
    )

    try:
        train_result = trainer.train()
        metrics = dict(train_result.metrics)
        if eval_dataset is not None:
            metrics.update({f"eval_{key}": value for key, value in trainer.evaluate().items()})
        model.save_pretrained(config["output_dir"])
        tokenizer.save_pretrained(config["output_dir"])
        append_jsonl(paths.training_log_file, build_log_event(run_id=run_id, status="TRAIN_OK", config=config, metrics=metrics))
        print(json.dumps({"run_id": run_id, "status": "TRAIN_OK", "metrics": metrics, "output_dir": config["output_dir"]}, indent=2))
        return 0
    except Exception as exc:
        append_jsonl(paths.training_log_file, build_log_event(run_id=run_id, status="TRAIN_ERROR", config=config, error=repr(exc)))
        print(json.dumps({"error": repr(exc), "run_id": run_id}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

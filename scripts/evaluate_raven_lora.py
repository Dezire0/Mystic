from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from typing import Any
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.jsonl_loop import ensure_data_dirs
from mystic.parsers import parse_raven_output
from mystic.raven_training import append_jsonl, load_jsonl, render_chat_text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate a trained Raven adapter on the Raven eval set.")
    parser.add_argument("--base-model", required=True, help="Base model name.")
    parser.add_argument("--adapter-path", required=True, help="Path to the trained adapter.")
    parser.add_argument(
        "--eval-file",
        default=str(ROOT / "mystic_data" / "eval_holdout" / "raven_eval.jsonl"),
        help="Prepared eval JSONL file.",
    )
    parser.add_argument("--limit", type=int, default=100, help="Maximum examples to evaluate.")
    return parser


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def choose_device(torch_module: Any) -> str:
    if torch_module.cuda.is_available():
        return "cuda"
    if torch_module.backends.mps.is_available():
        return "mps"
    return "cpu"


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    if total == 0:
        return {
            "total": 0,
            "exact_verdict_match_rate": 0.0,
            "valid_json_rate": 0.0,
            "invalid_json_rate": 0.0,
            "average_output_length": 0.0,
            "simple_failure_count": 0,
        }

    verdict_matches = sum(1 for item in results if item.get("verdict_match"))
    valid_json = sum(1 for item in results if item.get("valid_json"))
    invalid_json = total - valid_json
    output_length = sum(int(item.get("output_length", 0)) for item in results)
    failures = sum(1 for item in results if item.get("failure"))
    return {
        "total": total,
        "exact_verdict_match_rate": verdict_matches / total,
        "valid_json_rate": valid_json / total,
        "invalid_json_rate": invalid_json / total,
        "average_output_length": output_length / total,
        "simple_failure_count": failures,
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = ensure_data_dirs(ROOT / "mystic_data")
    rows = load_jsonl(args.eval_file)
    if not rows:
        print(json.dumps({"error": f"No eval rows found in {args.eval_file}"}, indent=2))
        return 1

    limited_rows = rows[: args.limit] if args.limit > 0 else rows

    try:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ModuleNotFoundError as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 1

    device = choose_device(torch)
    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token or tokenizer.unk_token

    model_kwargs: dict[str, Any] = {}
    if device == "cuda":
        model_kwargs["torch_dtype"] = torch.float16
    elif device == "mps":
        model_kwargs["torch_dtype"] = torch.float16

    base_model = AutoModelForCausalLM.from_pretrained(args.base_model, **model_kwargs)
    model = PeftModel.from_pretrained(base_model, args.adapter_path)
    if device == "cuda":
        model = model.to("cuda")
    elif device == "mps":
        model = model.to("mps")
    model.eval()

    results: list[dict[str, Any]] = []
    run_id = str(uuid.uuid4())
    for index, row in enumerate(limited_rows):
        prompt_messages = list(row["messages"][:-1])
        prompt_text = render_chat_text(tokenizer, prompt_messages, add_generation_prompt=True)
        try:
            encoded = tokenizer(prompt_text, return_tensors="pt")
            if device == "cuda":
                encoded = {key: value.to("cuda") for key, value in encoded.items()}
            elif device == "mps":
                encoded = {key: value.to("mps") for key, value in encoded.items()}
            output = model.generate(**encoded, max_new_tokens=256, do_sample=False)
            new_tokens = output[0][encoded["input_ids"].shape[1] :]
            decoded = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
            parsed = parse_raven_output(
                raw_output=decoded,
                sample_id=str(row.get("sample_id", f"eval-{index}")),
                run_id=run_id,
                backend="adapter-eval",
                model=args.adapter_path,
                problem=str(row.get("problem", "")),
                answer_text=str(row.get("proof_attempt", "")),
            )
            verdict_match = parsed["verdict"] == str(row.get("target_verdict", ""))
            results.append(
                {
                    "sample_id": row.get("sample_id"),
                    "verdict_match": verdict_match,
                    "valid_json": parsed.get("parse_error") is None,
                    "output_length": len(decoded),
                    "failure": bool(parsed.get("parse_error")),
                }
            )
            print(f"[eval] {row.get('sample_id', index)} -> {parsed['verdict']}")
        except Exception as exc:
            results.append(
                {
                    "sample_id": row.get("sample_id"),
                    "verdict_match": False,
                    "valid_json": False,
                    "output_length": 0,
                    "failure": True,
                    "error": repr(exc),
                }
            )
            print(f"[error] evaluation failed for {row.get('sample_id', index)}: {exc}")

    metrics = summarize_results(results)
    summary = {
        "event_id": str(uuid.uuid4()),
        "timestamp": now_iso(),
        "run_id": run_id,
        "base_model": args.base_model,
        "adapter_path": str(args.adapter_path),
        "eval_file": str(args.eval_file),
        "limit": args.limit,
        "metrics": metrics,
    }
    append_jsonl(paths.raven_eval_results_file, summary)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

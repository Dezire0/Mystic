from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.jsonl_loop import append_jsonl, ensure_data_dirs, read_jsonl
from mystic.llm_client import LLMClientError, build_client
from mystic.parsers import parse_raven_output
from mystic.raven_compare import build_comparison_record, summarize_comparison_rows
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare base Raven vs trained Raven adapter on eval JSONL.")
    parser.add_argument("--base-model", required=True, help="Base model name.")
    parser.add_argument("--adapter-path", required=True, help="Adapter path.")
    parser.add_argument(
        "--eval-file",
        default=str(ROOT / "mystic_data" / "eval_holdout" / "raven_eval.jsonl"),
        help="Prepared Raven eval JSONL file.",
    )
    parser.add_argument("--limit", type=int, default=100, help="Maximum rows to compare.")
    return parser


def _inference_user_prompt(row: dict[str, object]) -> str:
    messages = row.get("messages", [])
    if isinstance(messages, list) and len(messages) >= 2:
        return str(messages[1].get("content", ""))
    problem = str(row.get("problem", ""))
    proof_attempt = str(row.get("proof_attempt", ""))
    return f"Problem:\n{problem}\n\nProof attempt:\n{proof_attempt}"


def _inference_system_prompt(row: dict[str, object]) -> str:
    messages = row.get("messages", [])
    if isinstance(messages, list) and messages:
        return str(messages[0].get("content", ""))
    return "You are Mystic-Raven."


def _call_client(client, *, model: str, system_prompt: str, user_prompt: str) -> tuple[str, float]:
    started = time.perf_counter()
    output = client.generate_text(model=model, system_prompt=system_prompt, user_prompt=user_prompt)
    return output, time.perf_counter() - started


def _append_adapter_log(paths, *, run_id: str, sample_id: str, adapter_path: str, base_model: str, latency: float | None, status: str, error: str | None = None) -> None:
    append_jsonl(
        paths.adapter_inference_log_file,
        {
            "event_id": str(uuid.uuid4()),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "run_id": run_id,
            "sample_id": sample_id,
            "context": "compare_script",
            "adapter_path": adapter_path,
            "base_model": base_model,
            "latency_seconds": latency,
            "status": status,
            "error": error,
        },
    )


def _append_failed_adapter_output(paths, *, run_id: str, sample_id: str, problem: str, proof_text: str, adapter_path: str, base_model: str, raw_output: str, error: str | None) -> None:
    append_jsonl(
        paths.failed_adapter_outputs_file,
        {
            "event_id": str(uuid.uuid4()),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "run_id": run_id,
            "sample_id": sample_id,
            "problem": problem,
            "proof_text": proof_text,
            "adapter_path": adapter_path,
            "base_model": base_model,
            "raw_output": raw_output,
            "error": error,
        },
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = ensure_data_dirs(ROOT / "mystic_data")
    rows = read_jsonl(args.eval_file)
    if not rows:
        print(json.dumps({"error": f"No eval rows found in {args.eval_file}"}, indent=2))
        return 1

    limited_rows = rows[: args.limit] if args.limit > 0 else rows
    run_id = str(uuid.uuid4())
    try:
        base_client = build_client("adapter", config_path=ROOT / "configs" / "models.json", base_model=args.base_model, adapter_path=None)
        adapter_client = build_client("adapter", config_path=ROOT / "configs" / "models.json", base_model=args.base_model, adapter_path=args.adapter_path)
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 1

    comparison_rows: list[dict[str, object]] = []
    for index, row in enumerate(limited_rows):
        sample_id = str(row.get("sample_id", f"eval-{index}"))
        system_prompt = _inference_system_prompt(row)
        user_prompt = _inference_user_prompt(row)
        proof_text = str(row.get("proof_attempt", ""))
        if not proof_text:
            messages = row.get("messages", [])
            if isinstance(messages, list) and len(messages) > 1:
                prompt_text = str(messages[1].get("content", ""))
                proof_text = prompt_text.split("Proof attempt:\n", 1)[-1].strip()

        try:
            base_raw, base_latency = _call_client(
                base_client,
                model=args.base_model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            adapter_raw, adapter_latency = _call_client(
                adapter_client,
                model=args.base_model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            base_critique = parse_raven_output(
                raw_output=base_raw,
                sample_id=sample_id,
                run_id=run_id,
                backend="adapter-base",
                model=args.base_model,
                problem=str(row.get("problem", "")),
                answer_text=proof_text,
            )
            adapter_critique = parse_raven_output(
                raw_output=adapter_raw,
                sample_id=sample_id,
                run_id=run_id,
                backend="adapter",
                model=args.adapter_path,
                problem=str(row.get("problem", "")),
                answer_text=proof_text,
            )
            record = build_comparison_record(
                sample_id=sample_id,
                source="eval_script",
                problem=str(row.get("problem", "")),
                proof_text=proof_text,
                target_verdict=str(row.get("target_verdict", "") or "") or None,
                base_critique=base_critique,
                adapter_critique=adapter_critique,
                base_latency=base_latency,
                adapter_latency=adapter_latency,
                base_model=args.base_model,
                adapter_path=args.adapter_path,
                run_id=run_id,
            )
            append_jsonl(paths.raven_comparison_results_file, record)
            _append_adapter_log(
                paths,
                run_id=run_id,
                sample_id=sample_id,
                adapter_path=args.adapter_path,
                base_model=args.base_model,
                latency=adapter_latency,
                status="OK" if adapter_critique.get("parse_error") is None else "PARSE_ERROR",
                error=adapter_critique.get("parse_error"),
            )
            if adapter_critique.get("parse_error") is not None:
                _append_failed_adapter_output(
                    paths,
                    run_id=run_id,
                    sample_id=sample_id,
                    problem=str(row.get("problem", "")),
                    proof_text=proof_text,
                    adapter_path=args.adapter_path,
                    base_model=args.base_model,
                    raw_output=adapter_raw,
                    error=adapter_critique.get("parse_error"),
                )
            comparison_rows.append(record)
            print(f"[compare] {sample_id} -> adapter_better_or_equal={record['adapter_better_or_equal']}")
        except (LLMClientError, RuntimeError, ValueError) as exc:
            failure_record = {
                "event_id": str(uuid.uuid4()),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "run_id": run_id,
                "source": "eval_script",
                "sample_id": sample_id,
                "base_model": args.base_model,
                "adapter_path": args.adapter_path,
                "error": str(exc),
            }
            append_jsonl(paths.raven_comparison_results_file, failure_record)
            _append_adapter_log(
                paths,
                run_id=run_id,
                sample_id=sample_id,
                adapter_path=args.adapter_path,
                base_model=args.base_model,
                latency=None,
                status="ERROR",
                error=str(exc),
            )
            _append_failed_adapter_output(
                paths,
                run_id=run_id,
                sample_id=sample_id,
                problem=str(row.get("problem", "")),
                proof_text=proof_text,
                adapter_path=args.adapter_path,
                base_model=args.base_model,
                raw_output="",
                error=str(exc),
            )

    summary = {
        "event_id": str(uuid.uuid4()),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "run_id": run_id,
        "kind": "summary",
        "source": "eval_script",
        "base_model": args.base_model,
        "adapter_path": args.adapter_path,
        "eval_file": str(args.eval_file),
        "limit": args.limit,
        "metrics": summarize_comparison_rows(comparison_rows),
    }
    append_jsonl(paths.raven_comparison_results_file, summary)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.llm_client import LLMClientError, build_client, load_model_defaults
from mystic.jsonl_loop import (
    append_jsonl,
    build_failed_proof_record,
    build_proof_attempt,
    build_raven_critique_record,
    build_rejected_record,
    build_result_record,
    build_run_log_event,
    build_verified_record,
    ensure_data_dirs,
    normalize_problem_item,
    processed_ids,
    read_jsonl,
)
from mystic.parsers import parse_raven_output
from mystic.prompts import PROOF_GENERATOR_PROMPT, RAVEN_CRITIC_PROMPT
from mystic.raven_compare import build_comparison_record


TRACK_FAILURES = {"INVALID", "GAP", "NEEDS_MORE_DETAIL"}
DEFAULT_CONFIG_PATH = ROOT / "configs" / "models.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Mystic v3 automatic JSONL research loop.")
    parser.add_argument(
        "--base-dir",
        default=str(ROOT / "mystic_data"),
        help="Base directory for JSONL artifacts.",
    )
    parser.add_argument(
        "--input",
        default="",
        help="Optional JSONL input file. Defaults to mystic_data/raw/numina_math_cot_100.jsonl.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of new samples to process in this run.",
    )
    parser.add_argument(
        "--run-id",
        default="",
        help="Optional run identifier. A UUID is generated when omitted.",
    )
    parser.add_argument(
        "--backend",
        default="",
        choices=["ollama", "openai-compatible", "adapter"],
        help="Raven critic backend to use. Defaults to configs/models.json active Raven settings.",
    )
    parser.add_argument(
        "--generator-model",
        default="",
        help="Override the proof generator model name.",
    )
    parser.add_argument(
        "--raven-model",
        default="",
        help="Override the Raven critic model name.",
    )
    parser.add_argument(
        "--adapter-path",
        default="",
        help="PEFT adapter path for --backend adapter.",
    )
    parser.add_argument(
        "--base-model",
        default="",
        help="Base model for adapter inference and comparison.",
    )
    parser.add_argument(
        "--compare-raven",
        action="store_true",
        help="Run both base Raven and adapter Raven on the same proof attempt and append comparison logs.",
    )
    return parser


def _resolve_model_name(explicit: str, env_name: str, default: str) -> str:
    if explicit:
        return explicit
    env_value = os.getenv(env_name, "").strip()
    if env_value:
        return env_value
    return default


def _proof_user_prompt(problem: str) -> str:
    return f"Problem:\n{problem}"


def _raven_user_prompt(problem: str, proof_text: str) -> str:
    return f"Problem:\n{problem}\n\nProof attempt:\n{proof_text}"


def _call_text_client(client, *, model: str, system_prompt: str, user_prompt: str) -> tuple[str, float]:
    started = time.perf_counter()
    output = client.generate_text(model=model, system_prompt=system_prompt, user_prompt=user_prompt)
    latency = time.perf_counter() - started
    return output, latency


def _append_adapter_inference_log(
    *,
    paths,
    run_id: str,
    sample_id: str,
    context: str,
    base_model: str,
    adapter_path: str | None,
    latency: float | None,
    status: str,
    error: str | None = None,
) -> None:
    append_jsonl(
        paths.adapter_inference_log_file,
        {
            "event_id": str(uuid.uuid4()),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "run_id": run_id,
            "sample_id": sample_id,
            "context": context,
            "base_model": base_model,
            "adapter_path": adapter_path,
            "latency_seconds": latency,
            "status": status,
            "error": error,
        },
    )


def _append_failed_adapter_output(
    *,
    paths,
    run_id: str,
    sample_id: str,
    problem: str,
    proof_text: str,
    base_model: str,
    adapter_path: str | None,
    raw_output: str,
    error: str | None,
) -> None:
    append_jsonl(
        paths.failed_adapter_outputs_file,
        {
            "event_id": str(uuid.uuid4()),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "run_id": run_id,
            "sample_id": sample_id,
            "problem": problem,
            "proof_text": proof_text,
            "base_model": base_model,
            "adapter_path": adapter_path,
            "raw_output": raw_output,
            "error": error,
        },
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = ensure_data_dirs(args.base_dir)
    defaults = load_model_defaults(DEFAULT_CONFIG_PATH)
    raven_backend = args.backend or str(defaults.get("active_raven_backend", defaults.get("backend", "ollama")))
    generator_backend = str(defaults.get("backend", "ollama"))
    if generator_backend == "adapter":
        generator_backend = "ollama"
    generator_model = _resolve_model_name(
        args.generator_model,
        "MYSTIC_GENERATOR_MODEL",
        str(defaults.get("generator_model", "qwen2.5:7b")),
    )
    base_model = args.base_model or str(defaults.get("active_raven_base_model", "Qwen/Qwen2.5-0.5B-Instruct"))
    adapter_path = args.adapter_path or str(defaults.get("active_raven_adapter", ""))
    raven_model = _resolve_model_name(
        args.raven_model,
        "MYSTIC_RAVEN_MODEL",
        str(defaults.get("raven_model", base_model)),
    )
    raven_model_identifier = adapter_path if raven_backend == "adapter" else raven_model
    run_id = args.run_id or str(uuid.uuid4())
    input_path = Path(args.input) if args.input else paths.raw_file
    samples = read_jsonl(input_path)
    done_ids = processed_ids(paths.processed_ids_file)
    try:
        generator_client = build_client(generator_backend, config_path=DEFAULT_CONFIG_PATH)
        raven_client = build_client(
            raven_backend,
            config_path=DEFAULT_CONFIG_PATH,
            base_model=base_model,
            adapter_path=adapter_path,
        )
    except ValueError as exc:
        print(json.dumps({"error": str(exc), "backend": raven_backend}, indent=2))
        return 1

    base_compare_client = None
    adapter_compare_client = None
    if args.compare_raven:
        try:
            base_compare_client = build_client(
                "adapter",
                config_path=DEFAULT_CONFIG_PATH,
                base_model=base_model,
                adapter_path=None,
            )
            if raven_backend == "adapter":
                adapter_compare_client = raven_client
            else:
                adapter_compare_client = build_client(
                    "adapter",
                    config_path=DEFAULT_CONFIG_PATH,
                    base_model=base_model,
                    adapter_path=adapter_path,
                )
        except ValueError as exc:
            print(json.dumps({"error": str(exc), "compare_raven": True}, indent=2))
            return 1

    processed = 0
    skipped = 0
    classifications: dict[str, int] = {key: 0 for key in ["VALID", "INVALID", "GAP", "NEEDS_MORE_DETAIL"]}

    print(
        json.dumps(
            {
                "run_id": run_id,
                "backend": raven_backend,
                "generator_backend": generator_backend,
                "generator_model": generator_model,
                "raven_model": raven_model_identifier,
                "base_model": base_model,
                "adapter_path": adapter_path if raven_backend == "adapter" else "",
                "compare_raven": args.compare_raven,
                "input_file": str(input_path),
            },
            indent=2,
        )
    )

    for index, raw_sample in enumerate(samples):
        sample = normalize_problem_item(index, raw_sample)
        sample_id = str(sample["sample_id"])
        if sample_id in done_ids:
            skipped += 1
            continue

        proof_prompt = _proof_user_prompt(sample["problem"])
        try:
            generator_raw_output, _ = _call_text_client(
                generator_client,
                model=generator_model,
                system_prompt=PROOF_GENERATOR_PROMPT,
                user_prompt=proof_prompt,
            )
        except (LLMClientError, ValueError, RuntimeError) as exc:
            append_jsonl(
                paths.run_log_file,
                build_run_log_event(
                    sample_id=sample_id,
                    run_id=run_id,
                    backend=raven_backend,
                    generator_model=generator_model,
                    raven_model=raven_model_identifier,
                    status="GENERATOR_ERROR",
                    error=str(exc),
                ),
            )
            print(f"[error] {sample_id} generator failed: {exc}")
            continue

        proof_text = generator_raw_output.strip() or "The generator returned an empty proof attempt."
        proof_attempt = build_proof_attempt(
            sample=sample,
            run_id=run_id,
            backend=generator_backend,
            model=generator_model,
            prompt=PROOF_GENERATOR_PROMPT,
            proof_text=proof_text,
            raw_output=generator_raw_output,
        )

        raven_prompt = _raven_user_prompt(sample["problem"], proof_text)
        try:
            raven_raw_output, raven_latency = _call_text_client(
                raven_client,
                model=base_model if raven_backend == "adapter" else raven_model,
                system_prompt=RAVEN_CRITIC_PROMPT,
                user_prompt=raven_prompt,
            )
        except (LLMClientError, ValueError, RuntimeError) as exc:
            append_jsonl(
                paths.run_log_file,
                build_run_log_event(
                    sample_id=sample_id,
                    run_id=run_id,
                    backend=raven_backend,
                    generator_model=generator_model,
                    raven_model=raven_model_identifier,
                    status="RAVEN_ERROR",
                    error=str(exc),
                ),
            )
            if raven_backend == "adapter":
                _append_adapter_inference_log(
                    paths=paths,
                    run_id=run_id,
                    sample_id=sample_id,
                    context="loop_primary",
                    base_model=base_model,
                    adapter_path=adapter_path,
                    latency=None,
                    status="ERROR",
                    error=str(exc),
                )
                _append_failed_adapter_output(
                    paths=paths,
                    run_id=run_id,
                    sample_id=sample_id,
                    problem=sample["problem"],
                    proof_text=proof_text,
                    base_model=base_model,
                    adapter_path=adapter_path,
                    raw_output="",
                    error=str(exc),
                )
            print(f"[error] {sample_id} raven failed: {exc}")
            continue

        critique = parse_raven_output(
            raw_output=raven_raw_output,
            sample_id=sample_id,
            run_id=run_id,
            backend=raven_backend,
            model=raven_model_identifier,
        )
        if not critique["first_fatal_error"] and critique["verdict"] == "VALID":
            critique["first_fatal_error"] = ""
        if raven_backend == "adapter":
            _append_adapter_inference_log(
                paths=paths,
                run_id=run_id,
                sample_id=sample_id,
                context="loop_primary",
                base_model=base_model,
                adapter_path=adapter_path,
                latency=raven_latency,
                status="OK" if critique.get("parse_error") is None else "PARSE_ERROR",
                error=critique.get("parse_error"),
            )
            if critique.get("parse_error") is not None:
                _append_failed_adapter_output(
                    paths=paths,
                    run_id=run_id,
                    sample_id=sample_id,
                    problem=sample["problem"],
                    proof_text=proof_text,
                    base_model=base_model,
                    adapter_path=adapter_path,
                    raw_output=raven_raw_output,
                    error=critique.get("parse_error"),
                )

        result = build_result_record(
            sample=sample,
            proof_attempt=proof_attempt,
            raven_critique=critique,
            run_id=run_id,
            backend=raven_backend,
            generator_model=generator_model,
            raven_model=raven_model_identifier,
        )

        append_jsonl(paths.results_file, result)
        append_jsonl(
            paths.processed_ids_file,
            {"sample_id": sample_id, "processed_at": result["timestamp"], "run_id": run_id},
        )
        append_jsonl(paths.raven_critiques_file, build_raven_critique_record(result))

        classification = critique["verdict"]
        classifications[classification] = classifications.get(classification, 0) + 1

        if classification in TRACK_FAILURES:
            append_jsonl(paths.rejected_file, build_rejected_record(result))
            append_jsonl(paths.failed_proofs_file, build_failed_proof_record(result))
        else:
            append_jsonl(paths.verified_file, build_verified_record(result))

        append_jsonl(
            paths.run_log_file,
            build_run_log_event(
                sample_id=sample_id,
                run_id=run_id,
                backend=raven_backend,
                generator_model=generator_model,
                raven_model=raven_model_identifier,
                status=classification,
                error=critique.get("parse_error"),
            ),
        )

        if args.compare_raven and base_compare_client is not None and adapter_compare_client is not None:
            try:
                if raven_backend == "adapter":
                    adapter_raw_output = raven_raw_output
                    adapter_latency = raven_latency
                    adapter_critique = critique
                else:
                    adapter_raw_output, adapter_latency = _call_text_client(
                        adapter_compare_client,
                        model=base_model,
                        system_prompt=RAVEN_CRITIC_PROMPT,
                        user_prompt=raven_prompt,
                    )
                    adapter_critique = parse_raven_output(
                        raw_output=adapter_raw_output,
                        sample_id=sample_id,
                        run_id=run_id,
                        backend="adapter",
                        model=adapter_path,
                    )
                base_raw_output, base_latency = _call_text_client(
                    base_compare_client,
                    model=base_model,
                    system_prompt=RAVEN_CRITIC_PROMPT,
                    user_prompt=raven_prompt,
                )
                base_critique = parse_raven_output(
                    raw_output=base_raw_output,
                    sample_id=sample_id,
                    run_id=run_id,
                    backend="adapter-base",
                    model=base_model,
                )
                comparison_record = build_comparison_record(
                    sample_id=sample_id,
                    source="loop",
                    problem=sample["problem"],
                    proof_text=proof_text,
                    target_verdict=str(raw_sample.get("target_verdict", "") or "") or None,
                    base_critique=base_critique,
                    adapter_critique=adapter_critique,
                    base_latency=base_latency,
                    adapter_latency=adapter_latency,
                    base_model=base_model,
                    adapter_path=adapter_path,
                    run_id=run_id,
                )
                append_jsonl(paths.raven_comparison_results_file, comparison_record)
                append_jsonl(
                    paths.run_log_file,
                    build_run_log_event(
                        sample_id=sample_id,
                        run_id=run_id,
                        backend=raven_backend,
                        generator_model=generator_model,
                        raven_model=raven_model_identifier,
                        status="COMPARE_OK" if comparison_record["adapter_better_or_equal"] else "COMPARE_BASE_BETTER",
                        error=None,
                    ),
                )
                _append_adapter_inference_log(
                    paths=paths,
                    run_id=run_id,
                    sample_id=sample_id,
                    context="loop_compare",
                    base_model=base_model,
                    adapter_path=adapter_path,
                    latency=adapter_latency,
                    status="OK" if adapter_critique.get("parse_error") is None else "PARSE_ERROR",
                    error=adapter_critique.get("parse_error"),
                )
                if adapter_critique.get("parse_error") is not None:
                    _append_failed_adapter_output(
                        paths=paths,
                        run_id=run_id,
                        sample_id=sample_id,
                        problem=sample["problem"],
                        proof_text=proof_text,
                        base_model=base_model,
                        adapter_path=adapter_path,
                        raw_output=adapter_raw_output,
                        error=adapter_critique.get("parse_error"),
                    )
            except (LLMClientError, RuntimeError, ValueError) as exc:
                append_jsonl(
                    paths.raven_comparison_results_file,
                    {
                        "event_id": str(uuid.uuid4()),
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "run_id": run_id,
                        "source": "loop",
                        "sample_id": sample_id,
                        "base_model": base_model,
                        "adapter_path": adapter_path,
                        "error": str(exc),
                    },
                )
                _append_adapter_inference_log(
                    paths=paths,
                    run_id=run_id,
                    sample_id=sample_id,
                    context="loop_compare",
                    base_model=base_model,
                    adapter_path=adapter_path,
                    latency=None,
                    status="ERROR",
                    error=str(exc),
                )

        done_ids.add(sample_id)
        processed += 1
        print(f"[processed] {sample_id} -> {classification}")
        if processed >= args.limit:
            break

    payload = {
        "run_id": run_id,
        "backend": raven_backend,
        "generator_backend": generator_backend,
        "generator_model": generator_model,
        "raven_model": raven_model_identifier,
        "base_model": base_model,
        "adapter_path": adapter_path if raven_backend == "adapter" else "",
        "processed_count": processed,
        "skipped_count": skipped,
        "classifications": classifications,
        "results_file": str(paths.results_file),
        "verified_file": str(paths.verified_file),
        "rejected_file": str(paths.rejected_file),
        "failed_proofs_file": str(paths.failed_proofs_file),
        "raven_critiques_file": str(paths.raven_critiques_file),
        "run_log_file": str(paths.run_log_file),
        "adapter_inference_log_file": str(paths.adapter_inference_log_file),
        "raven_comparison_results_file": str(paths.raven_comparison_results_file),
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

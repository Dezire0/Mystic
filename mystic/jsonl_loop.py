"""Shared JSONL helpers for the Mystic research loop."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable
import uuid

from mystic.schema import LoopResult, ProblemItem, ProofAttempt, RavenCritique, RunLogEvent


DATA_DIRS = [
    "raw",
    "processed",
    "internal",
    "logs",
    "exports",
    "state",
    "verified",
    "rejected",
    "train_ready",
    "eval_holdout",
    "adapters",
]


NUMINA_REPO_ID = "AI-MO/NuminaMath-CoT"


@dataclass(slots=True)
class Paths:
    base_dir: Path
    raw_file: Path
    results_file: Path
    verified_file: Path
    rejected_file: Path
    failed_proofs_file: Path
    raven_critiques_file: Path
    run_log_file: Path
    success_log_file: Path
    failure_log_file: Path
    processed_ids_file: Path
    raven_lora_file: Path
    raven_lora_train_ready_file: Path
    raven_train_file: Path
    raven_eval_file: Path
    training_log_file: Path
    raven_eval_results_file: Path
    adapter_inference_log_file: Path
    raven_comparison_results_file: Path
    raven_promotion_log_file: Path
    failed_adapter_outputs_file: Path


def build_paths(base_dir: str | Path) -> Paths:
    root = Path(base_dir)
    return Paths(
        base_dir=root,
        raw_file=root / "raw" / "numina_math_cot_100.jsonl",
        results_file=root / "processed" / "mystic_loop_results.jsonl",
        verified_file=root / "verified" / "verified.jsonl",
        rejected_file=root / "rejected" / "rejected.jsonl",
        failed_proofs_file=root / "internal" / "failed_proofs.jsonl",
        raven_critiques_file=root / "internal" / "raven_critiques.jsonl",
        run_log_file=root / "logs" / "run_log.jsonl",
        success_log_file=root / "logs" / "success_log.jsonl",
        failure_log_file=root / "logs" / "failure_log.jsonl",
        processed_ids_file=root / "state" / "processed_ids.jsonl",
        raven_lora_file=root / "exports" / "raven_lora.jsonl",
        raven_lora_train_ready_file=root / "train_ready" / "raven_lora.jsonl",
        raven_train_file=root / "train_ready" / "raven_train.jsonl",
        raven_eval_file=root / "eval_holdout" / "raven_eval.jsonl",
        training_log_file=root / "logs" / "training_log.jsonl",
        raven_eval_results_file=root / "logs" / "raven_eval_results.jsonl",
        adapter_inference_log_file=root / "logs" / "adapter_inference_log.jsonl",
        raven_comparison_results_file=root / "logs" / "raven_comparison_results.jsonl",
        raven_promotion_log_file=root / "logs" / "raven_promotion_log.jsonl",
        failed_adapter_outputs_file=root / "internal" / "failed_adapter_outputs.jsonl",
    )


def ensure_data_dirs(base_dir: str | Path) -> Paths:
    paths = build_paths(base_dir)
    for dirname in DATA_DIRS:
        (paths.base_dir / dirname).mkdir(parents=True, exist_ok=True)
    for file_path in [
        paths.results_file,
        paths.verified_file,
        paths.rejected_file,
        paths.failed_proofs_file,
        paths.raven_critiques_file,
        paths.run_log_file,
        paths.success_log_file,
        paths.failure_log_file,
        paths.processed_ids_file,
        paths.raven_lora_train_ready_file,
        paths.raven_train_file,
        paths.raven_eval_file,
        paths.training_log_file,
        paths.raven_eval_results_file,
        paths.adapter_inference_log_file,
        paths.raven_comparison_results_file,
        paths.raven_promotion_log_file,
        paths.failed_adapter_outputs_file,
    ]:
        file_path.touch(exist_ok=True)
    return paths


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def append_jsonl(path: str | Path, payload: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    target = Path(path)
    if not target.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(json.loads(stripped))
    return rows


def processed_ids(path: str | Path) -> set[str]:
    ids: set[str] = set()
    for item in read_jsonl(path):
        if "sample_id" in item:
            ids.add(str(item["sample_id"]))
        elif "id" in item:
            ids.add(str(item["id"]))
    return ids


def stable_sample_id(index: int, row: dict[str, Any]) -> str:
    source_id = row.get("id") or row.get("uuid")
    if source_id is not None:
        return str(source_id)
    source_text = row.get("problem") or row.get("messages") or row.get("solution") or row
    digest = hashlib.sha256(json.dumps(source_text, sort_keys=True, ensure_ascii=True).encode("utf-8")).hexdigest()[:16]
    return f"numina-{index:04d}-{digest}"


def normalize_numina_row(index: int, row: dict[str, Any]) -> dict[str, Any]:
    problem = row.get("problem")
    if not problem and isinstance(row.get("messages"), list) and row["messages"]:
        first = row["messages"][0]
        if isinstance(first, dict):
            problem = first.get("content", "")
    solution = row.get("solution")
    if not solution and isinstance(row.get("messages"), list) and len(row["messages"]) > 1:
        second = row["messages"][1]
        if isinstance(second, dict):
            solution = second.get("content", "")
    sample_id = stable_sample_id(index, row)
    return {
        "sample_id": sample_id,
        "source_dataset": NUMINA_REPO_ID,
        "downloaded_at": now_iso(),
        "problem": str(problem or ""),
        "reference_solution": str(solution or ""),
        "raw": row,
    }


def normalize_problem_item(index: int, row: dict[str, Any]) -> ProblemItem:
    if "sample_id" in row and "problem" in row:
        return ProblemItem(
            sample_id=str(row["sample_id"]),
            source_dataset=str(row.get("source_dataset", "custom")),
            downloaded_at=str(row.get("downloaded_at", now_iso())),
            problem=str(row.get("problem", "")),
            reference_solution=str(row.get("reference_solution", "")),
            raw=row.get("raw", row),
        )
    return ProblemItem(normalize_numina_row(index, row))


def build_proof_attempt(
    *,
    sample: ProblemItem,
    run_id: str,
    backend: str,
    model: str,
    prompt: str,
    proof_text: str,
    raw_output: str,
    error: str | None = None,
) -> ProofAttempt:
    return ProofAttempt(
        proof_id=str(uuid.uuid4()),
        sample_id=str(sample["sample_id"]),
        run_id=run_id,
        backend=backend,
        model=model,
        prompt=prompt,
        proof_text=proof_text,
        raw_output=raw_output,
        generated_at=now_iso(),
        error=error,
    )


def build_result_record(
    *,
    sample: ProblemItem,
    proof_attempt: ProofAttempt,
    raven_critique: RavenCritique,
    run_id: str,
    backend: str,
    generator_model: str,
    raven_model: str,
) -> LoopResult:
    return LoopResult(
        result_id=str(uuid.uuid4()),
        sample_id=str(sample["sample_id"]),
        run_id=run_id,
        timestamp=now_iso(),
        backend=backend,
        generator_model=generator_model,
        raven_model=raven_model,
        problem=str(sample.get("problem", "")),
        reference_solution=str(sample.get("reference_solution", "")),
        proof_attempt=proof_attempt,
        raven_critique=raven_critique,
        verdict=raven_critique["verdict"],
        final_status=str(raven_critique.get("final_status", raven_critique["verdict"])),
    )


def build_failed_proof_record(result: LoopResult) -> dict[str, Any]:
    proof_attempt = result["proof_attempt"]
    critique = result["raven_critique"]
    return {
        "sample_id": result["sample_id"],
        "run_id": result["run_id"],
        "problem": result["problem"],
        "proof_text": proof_attempt["proof_text"],
        "generator_model": result["generator_model"],
        "verdict": result["verdict"],
        "first_fatal_error": critique.get("first_fatal_error", ""),
        "final_status": critique.get("final_status", result["verdict"]),
        "recorded_at": now_iso(),
    }


def build_raven_critique_record(result: LoopResult) -> dict[str, Any]:
    proof_attempt = result["proof_attempt"]
    critique = result["raven_critique"]
    return {
        "critique_id": critique["critique_id"],
        "sample_id": result["sample_id"],
        "run_id": result["run_id"],
        "backend": critique["backend"],
        "model": critique["model"],
        "problem": result["problem"],
        "proof_text": proof_attempt["proof_text"],
        "verdict": critique["verdict"],
        "first_fatal_error": critique["first_fatal_error"],
        "missing_assumptions": critique["missing_assumptions"],
        "invalid_steps": critique["invalid_steps"],
        "valid_steps": critique["valid_steps"],
        "repair_possible": critique["repair_possible"],
        "confidence": critique["confidence"],
        "final_status": critique["final_status"],
        "raw_output": critique["raw_output"],
        "parse_error": critique.get("parse_error"),
        "recorded_at": now_iso(),
    }


def build_verified_record(result: LoopResult) -> dict[str, Any]:
    return {
        "sample_id": result["sample_id"],
        "run_id": result["run_id"],
        "problem": result["problem"],
        "verdict": result["verdict"],
        "proof_attempt": result["proof_attempt"],
        "raven_critique": result["raven_critique"],
        "recorded_at": now_iso(),
    }


def build_rejected_record(result: LoopResult) -> dict[str, Any]:
    return {
        "sample_id": result["sample_id"],
        "run_id": result["run_id"],
        "problem": result["problem"],
        "verdict": result["verdict"],
        "proof_attempt": result["proof_attempt"],
        "raven_critique": result["raven_critique"],
        "recorded_at": now_iso(),
    }


def build_run_log_event(
    *,
    sample_id: str,
    run_id: str,
    backend: str,
    generator_model: str,
    raven_model: str,
    status: str,
    error: str | None = None,
) -> RunLogEvent:
    return RunLogEvent(
        event_id=str(uuid.uuid4()),
        id=sample_id,
        timestamp=now_iso(),
        run_id=run_id,
        backend=backend,
        generator_model=generator_model,
        raven_model=raven_model,
        status=status,
        error=error,
    )


def export_raven_lora_rows(critiques: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for critique in critiques:
        output_payload = {
            "verdict": critique.get("verdict", "NEEDS_MORE_DETAIL"),
            "first_fatal_error": critique.get("first_fatal_error", ""),
            "missing_assumptions": critique.get("missing_assumptions", []),
            "invalid_steps": critique.get("invalid_steps", []),
            "valid_steps": critique.get("valid_steps", []),
            "repair_possible": critique.get("repair_possible", True),
            "confidence": critique.get("confidence", 0.0),
            "final_status": critique.get("final_status", critique.get("verdict", "NEEDS_MORE_DETAIL")),
        }
        rows.append(
            {
                "instruction": "Critique the proof like Mystic-Raven and return JSON only.",
                "input": (
                    f"Problem:\n{critique.get('problem', '')}\n\n"
                    f"Proof attempt:\n{critique.get('proof_text', '')}"
                ),
                "output": json.dumps(output_payload, ensure_ascii=True),
                "classification": critique.get("verdict", "NEEDS_MORE_DETAIL"),
                "problem": critique.get("problem", ""),
                "proof_attempt": critique.get("proof_text", ""),
                "metadata": {
                    "sample_id": critique.get("sample_id"),
                    "problem": critique.get("problem"),
                    "run_id": critique.get("run_id"),
                },
            }
        )
    return rows

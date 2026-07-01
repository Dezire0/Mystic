from __future__ import annotations

import argparse
import copy
from collections import Counter
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import random
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.raven_training import build_chat_messages, load_jsonl, write_jsonl
from mystic.research_table.training_quality import (
    DEFAULT_MIN_INVALID_ROWS,
    evaluate_raven_training_quality,
    raven_training_row_fingerprint,
)


MIN_INVALID_ROWS_WARNING_THRESHOLD = DEFAULT_MIN_INVALID_ROWS


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert Research Table Raven rows into Raven LoRA training rows.")
    parser.add_argument("--root-path", default=str(ROOT), help="Mystic repository root used for default paths.")
    parser.add_argument("--target", default="raven", choices=["raven"])
    parser.add_argument(
        "--input",
        default="",
        help="Research Table Raven dataset JSONL path.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Prepared Raven training JSONL output path.",
    )
    parser.add_argument("--min-rows", type=int, default=0, help="Optional minimum number of rows required after filtering.")
    parser.add_argument("--max-rows", type=int, default=0, help="Optional maximum number of rows to write.")
    parser.add_argument("--shuffle", action="store_true", help="Shuffle rows before applying --max-rows.")
    parser.add_argument("--seed", type=int, default=0, help="Seed used with --shuffle.")
    parser.add_argument("--allow-empty", action="store_true", help="Allow writing an empty prepared dataset.")
    parser.add_argument("--include-adversarial-seeds", action="store_true")
    parser.add_argument("--adversarial-path", default="", help="Optional adversarial Raven seed JSONL path.")
    parser.add_argument("--adversarial-weight", type=int, default=1)
    parser.add_argument("--max-adversarial-rows", type=int, default=0)
    parser.add_argument("--include-lab-failures", action="store_true")
    parser.add_argument("--lab-failures-path", default="", help="Optional lab failure Raven JSONL path.")
    parser.add_argument("--lab-failure-weight", type=int, default=1)
    parser.add_argument("--max-lab-failure-rows", type=int, default=0)
    parser.add_argument(
        "--min-invalid-rows",
        type=int,
        default=0,
        help="Optional enforced minimum INVALID rows. The default quality recommendation remains five.",
    )
    parser.add_argument("--allow-low-invalid", action="store_true")
    return parser


def normalize_raven_verdict(verdict: str) -> str:
    normalized = str(verdict or "").strip().upper()
    if normalized == "VALID_COMPLETE_PROOF":
        return "VALID"
    if normalized == "UNCLEAR":
        return "NEEDS_MORE_DETAIL"
    if normalized in {"VALID", "INVALID", "GAP", "NEEDS_MORE_DETAIL"}:
        return normalized
    return "NEEDS_MORE_DETAIL"


def build_sample_id(source: dict[str, Any], verdict: str) -> str:
    source_type = str(source.get("source_type", "research_table")).strip() or "research_table"
    preferred_key = "|".join(
        [
            source_type,
            str(source.get("session_id", "")).strip(),
            str(source.get("claim_id", "")).strip(),
            str(source.get("failure_id", "")).strip(),
        ]
    )
    if source_type == "lab_failure" and any(part.strip() for part in preferred_key.split("|")[1:]):
        digest = hashlib.sha256(preferred_key.encode("utf-8")).hexdigest()[:16]
        return f"lab-failure-raven-{digest}"
    text = "|".join(
        [
            source_type,
            str(source.get("seed_id", "")).strip(),
            str(source.get("case_type", "")).strip(),
            str(source.get("session_id", "")).strip(),
            str(source.get("turn_id", "")).strip(),
            str(source.get("discovery_id", "")).strip(),
            str(source.get("claim_id", "")).strip(),
            str(source.get("failure_id", "")).strip(),
            str(source.get("label_id", "")).strip(),
            normalize_raven_verdict(verdict),
        ]
    )
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    prefix = {
        "adversarial_seed": "adversarial-raven",
        "lab_failure": "lab-failure-raven",
    }.get(source_type, "research-table-raven")
    return f"{prefix}-{digest}"


def build_proof_attempt(input_payload: dict[str, Any]) -> str:
    sections: list[str] = []
    model_output = str(input_payload.get("model_output", "") or "").strip()
    discovery_or_claim = str(input_payload.get("discovery_or_claim", "") or "").strip()
    tool_evidence = str(input_payload.get("tool_evidence", "") or "").strip()
    context = str(input_payload.get("context", "") or "").strip()
    if model_output:
        sections.append(f"Model output:\n{model_output}")
    if discovery_or_claim:
        sections.append(f"Discovery or claim:\n{discovery_or_claim}")
    if tool_evidence:
        sections.append(f"Tool evidence:\n{tool_evidence}")
    if context:
        sections.append(f"Context:\n{context}")
    sections.append(
        "Instruction:\nJudge strictly. Do not mark VALID unless the proof is complete, "
        "and let deterministic tool evidence override the model claim."
    )
    return "\n\n".join(sections).strip()


def build_assistant_output(output_payload: dict[str, Any], verdict: str) -> str:
    first_fatal_error = str(output_payload.get("first_fatal_error", "") or "").strip()
    critique = str(output_payload.get("critique", "") or "").strip()
    recommended_next_action = str(output_payload.get("recommended_next_action", "") or "").strip()

    invalid_steps: list[str] = []
    valid_steps: list[str] = []
    if verdict in {"INVALID", "GAP", "NEEDS_MORE_DETAIL"} and first_fatal_error:
        invalid_steps.append(first_fatal_error)
    if verdict == "VALID" and critique:
        valid_steps.append(critique)

    payload = {
        "verdict": verdict,
        "first_fatal_error": first_fatal_error,
        "missing_assumptions": [],
        "invalid_steps": invalid_steps,
        "valid_steps": valid_steps,
        "repair_possible": verdict != "VALID",
        "confidence": 0.9 if verdict == "VALID" else 0.3,
        "final_status": verdict,
        "critique": critique,
        "recommended_next_action": recommended_next_action,
    }
    return json.dumps(payload, ensure_ascii=True)


def is_verifier_derived(source: dict[str, Any]) -> bool:
    if "verifier_derived" in source:
        return bool(source.get("verifier_derived"))
    return bool(str(source.get("discovery_id", "")).strip()) and not bool(str(source.get("label_id", "")).strip())


def dataset_source_for_row(source: dict[str, Any]) -> str:
    source_type = str(source.get("source_type", "") or "").strip()
    if source_type in {"adversarial_seed", "lab_failure"}:
        return source_type
    return "research_table"


def metadata_payload_for_row(
    *,
    source: dict[str, Any],
    input_payload: dict[str, Any],
    output_payload: dict[str, Any],
    verdict: str,
    verifier_derived: bool,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    dataset_source = dataset_source_for_row(source)
    source_payload = {
        "source_type": str(source.get("source_type", "") or dataset_source),
        "session_id": str(source.get("session_id", "") or ""),
        "turn_id": str(source.get("turn_id", "") or ""),
        "discovery_id": str(source.get("discovery_id", "") or ""),
        "label_id": str(source.get("label_id", "") or ""),
        "seed_id": str(source.get("seed_id", "") or ""),
        "case_type": str(source.get("case_type", "") or ""),
        "claim_id": str(source.get("claim_id", "") or ""),
        "failure_id": str(source.get("failure_id", "") or ""),
        "source_turn_id": str(source.get("source_turn_id", "") or ""),
    }
    shared_payload = {
        "problem": str(input_payload.get("problem", "") or ""),
        "model_output": str(input_payload.get("model_output", "") or ""),
        "discovery_or_claim": str(input_payload.get("discovery_or_claim", "") or ""),
        "tool_evidence": str(input_payload.get("tool_evidence", "") or ""),
        "expected_verdict": verdict,
        "first_fatal_error": str(output_payload.get("first_fatal_error", "") or ""),
        "critique": str(output_payload.get("critique", "") or ""),
        "recommended_next_action": str(output_payload.get("recommended_next_action", "") or ""),
        "source": source_payload,
        "verifier_derived": verifier_derived,
    }
    metadata = {
        "target_agent": "raven",
        "dataset_source": dataset_source,
        "session_id": source_payload["session_id"],
        "turn_id": source_payload["turn_id"],
        "discovery_id": source_payload["discovery_id"],
        "label_id": source_payload["label_id"],
        "seed_id": source_payload["seed_id"],
        "case_type": source_payload["case_type"],
        "claim_id": source_payload["claim_id"],
        "failure_id": source_payload["failure_id"],
        "verdict": verdict,
        "has_first_fatal_error": bool(shared_payload["first_fatal_error"].strip()),
        "has_tool_evidence": bool(shared_payload["tool_evidence"].strip()),
        "verifier_derived": verifier_derived,
    }
    if dataset_source == "lab_failure":
        metadata["lab_failure"] = dict(shared_payload)
        metadata["failure_type"] = str(source.get("failure_type", "") or "")
    else:
        metadata["research_table"] = dict(shared_payload)
    return dataset_source, source_payload, metadata


def row_source_payload(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata", {})
    if not isinstance(metadata, dict):
        return {}
    for key in ("lab_failure", "research_table"):
        payload = metadata.get(key)
        if isinstance(payload, dict):
            source = payload.get("source")
            if isinstance(source, dict):
                return source
    return {}


def convert_research_table_row(row: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    if str(row.get("agent", "")).strip() != "raven":
        return None, "unsupported agent"

    input_payload = row.get("input")
    output_payload = row.get("output")
    source = row.get("source")
    if not isinstance(input_payload, dict):
        return None, "missing input payload"
    if not isinstance(output_payload, dict):
        return None, "missing output payload"
    if not isinstance(source, dict):
        return None, "missing source payload"

    problem = str(input_payload.get("problem", "") or "").strip()
    proof_attempt = build_proof_attempt(input_payload)
    if not problem:
        return None, "missing problem"
    if not proof_attempt:
        return None, "missing proof_attempt"

    verdict = normalize_raven_verdict(str(output_payload.get("verdict", "") or ""))
    assistant_output = build_assistant_output(output_payload, verdict)
    verifier_derived = is_verifier_derived(source)
    dataset_source, source_payload, metadata = metadata_payload_for_row(
        source=source,
        input_payload=input_payload,
        output_payload=output_payload,
        verdict=verdict,
        verifier_derived=verifier_derived,
    )
    metadata["sample_id"] = build_sample_id(source_payload, verdict)
    prepared = {
        "sample_id": metadata["sample_id"],
        "problem": problem,
        "proof_attempt": proof_attempt,
        "messages": build_chat_messages(problem, proof_attempt, assistant_output),
        "assistant_output": assistant_output,
        "target_verdict": verdict,
        "metadata": metadata,
    }
    return prepared, None


def build_source_counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    sessions: Counter[str] = Counter()
    source_types: Counter[str] = Counter()
    unique_turns: set[str] = set()
    unique_discoveries: set[str] = set()
    unique_labels: set[str] = set()
    unique_seeds: set[str] = set()
    unique_failures: set[str] = set()
    for row in rows:
        metadata = row.get("metadata", {})
        source = row_source_payload(row)
        source_type = str(source.get("source_type", "") or metadata.get("dataset_source", "")).strip()
        session_id = str(source.get("session_id", "")).strip()
        turn_id = str(source.get("turn_id", "")).strip()
        discovery_id = str(source.get("discovery_id", "")).strip()
        label_id = str(source.get("label_id", "")).strip()
        seed_id = str(source.get("seed_id", "")).strip()
        failure_id = str(source.get("failure_id", "")).strip()
        if source_type:
            source_types[source_type] += 1
        if session_id:
            sessions[session_id] += 1
        if turn_id:
            unique_turns.add(turn_id)
        if discovery_id:
            unique_discoveries.add(discovery_id)
        if label_id:
            unique_labels.add(label_id)
        if seed_id:
            unique_seeds.add(seed_id)
        if failure_id:
            unique_failures.add(failure_id)
    return {
        "source_types": dict(sorted(source_types.items())),
        "sessions": dict(sorted(sessions.items())),
        "unique_turns": len(unique_turns),
        "unique_discoveries": len(unique_discoveries),
        "unique_labels": len(unique_labels),
        "unique_seeds": len(unique_seeds),
        "unique_failures": len(unique_failures),
    }


def build_failure_type_distribution(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        metadata = row.get("metadata", {})
        if not isinstance(metadata, dict):
            continue
        failure_type = str(metadata.get("failure_type", "")).strip()
        if failure_type:
            counts[failure_type] += 1
    return dict(sorted(counts.items()))


def validate_rows(
    rows: list[dict[str, Any]],
    *,
    min_invalid_rows: int = 0,
    allow_low_invalid: bool = False,
    duplicate_rows_removed: int = 0,
) -> dict[str, Any]:
    quality = evaluate_raven_training_quality(
        rows,
        min_invalid_rows=min_invalid_rows or MIN_INVALID_ROWS_WARNING_THRESHOLD,
        enforce_min_invalid=min_invalid_rows > 0,
        allow_low_invalid=allow_low_invalid,
        duplicate_rows_removed=duplicate_rows_removed,
    )
    stats = quality["stats"]
    missing_fatal = int(stats["first_fatal_error_coverage"]["total"]) - int(
        stats["first_fatal_error_coverage"]["covered"]
    )
    missing_tool_evidence = int(stats["tool_evidence_coverage"]["total"]) - int(
        stats["tool_evidence_coverage"]["covered"]
    )
    warnings = list(quality["warnings"])
    if missing_fatal:
        warnings.append(f"{missing_fatal} INVALID rows are missing first_fatal_error.")
    if missing_tool_evidence:
        warnings.append(f"{missing_tool_evidence} verifier-derived rows are missing tool_evidence.")
    quality["warnings"] = list(dict.fromkeys(warnings))
    return quality


def write_manifest(
    *,
    target: str,
    input_path: Path,
    adversarial_path: Path | None,
    lab_failures_path: Path | None,
    output_path: Path,
    rows_total: int,
    rows_written: int,
    research_table_rows: int,
    adversarial_seed_rows: int,
    lab_failure_rows: int,
    lab_failure_weight: int,
    combined_rows: int,
    duplicate_rows_removed: int,
    rows: list[dict[str, Any]],
    quality_gate: dict[str, Any],
    warnings: list[str],
) -> Path:
    verdict_distribution = Counter(str(row.get("target_verdict", "")).strip().upper() for row in rows)
    quality_stats = quality_gate.get("stats", {})
    manifest = {
        "target_agent": target,
        "input_path": str(input_path),
        "adversarial_path": str(adversarial_path) if adversarial_path else "",
        "lab_failures_path": str(lab_failures_path) if lab_failures_path else "",
        "output_path": str(output_path),
        "rows_total": rows_total,
        "rows_written": rows_written,
        "research_table_rows": research_table_rows,
        "adversarial_seed_rows": adversarial_seed_rows,
        "lab_failure_rows": lab_failure_rows,
        "lab_failure_weight": lab_failure_weight,
        "combined_rows": combined_rows,
        "verdict_distribution": dict(sorted(verdict_distribution.items())),
        "invalid_rows_count": int(quality_stats.get("invalid_rows_count", 0)),
        "needs_more_detail_rows_count": int(quality_stats.get("needs_more_detail_rows_count", 0)),
        "valid_rows_count": int(quality_stats.get("valid_rows_count", 0)),
        "first_fatal_error_coverage_for_invalid": quality_stats.get("first_fatal_error_coverage", {}),
        "tool_evidence_coverage_for_verifier_rows": quality_stats.get("tool_evidence_coverage", {}),
        "duplicate_rows_removed": duplicate_rows_removed,
        "duplicate_rate": float(quality_stats.get("duplicate_rate", 0.0)),
        "source_counts": build_source_counts(rows),
        "failure_type_distribution": build_failure_type_distribution(rows),
        "quality_gate": quality_gate,
        "created_at": now_iso(),
        "warnings": warnings,
    }
    manifest_path = output_path.parent / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return manifest_path


def prepare_research_table_training(
    *,
    target: str,
    input_path: str | Path,
    output_path: str | Path,
    min_rows: int = 0,
    max_rows: int = 0,
    shuffle: bool = False,
    seed: int = 0,
    allow_empty: bool = False,
    include_adversarial_seeds: bool = False,
    adversarial_path: str | Path | None = None,
    adversarial_weight: int = 1,
    max_adversarial_rows: int = 0,
    include_lab_failures: bool = False,
    lab_failures_path: str | Path | None = None,
    lab_failure_weight: int = 1,
    max_lab_failure_rows: int = 0,
    min_invalid_rows: int = 0,
    allow_low_invalid: bool = False,
) -> dict[str, Any]:
    source_path = Path(input_path)
    target_path = Path(output_path)
    if not source_path.exists():
        raise FileNotFoundError(f"Input file not found: {source_path}")
    if adversarial_weight < 1:
        raise ValueError("--adversarial-weight must be at least 1.")
    if lab_failure_weight < 1:
        raise ValueError("--lab-failure-weight must be at least 1.")
    if max_adversarial_rows < 0:
        raise ValueError("--max-adversarial-rows must be zero or positive.")
    if max_lab_failure_rows < 0:
        raise ValueError("--max-lab-failure-rows must be zero or positive.")

    source_rows = load_jsonl(source_path)
    adversarial_source_path = Path(adversarial_path) if adversarial_path else None
    adversarial_source_rows: list[dict[str, Any]] = []
    lab_failure_source_path = Path(lab_failures_path) if lab_failures_path else None
    lab_failure_source_rows: list[dict[str, Any]] = []
    if include_adversarial_seeds:
        if adversarial_source_path is None:
            adversarial_source_path = source_path.parent / "adversarial_seed_raven.jsonl"
        if not adversarial_source_path.exists():
            raise FileNotFoundError(
                "Adversarial seeds were requested but the dataset is missing: "
                f"{adversarial_source_path}"
            )
        adversarial_source_rows = load_jsonl(adversarial_source_path)
        if max_adversarial_rows > 0:
            adversarial_source_rows = adversarial_source_rows[:max_adversarial_rows]
    if include_lab_failures:
        if lab_failure_source_path is None:
            lab_failure_source_path = source_path.parents[1] / "lab" / "raven_lab_failures.jsonl"
        if not lab_failure_source_path.exists():
            raise FileNotFoundError(
                "Lab failures were requested but the dataset is missing: "
                f"{lab_failure_source_path}"
            )
        lab_failure_source_rows = load_jsonl(lab_failure_source_path)
        if max_lab_failure_rows > 0:
            lab_failure_source_rows = lab_failure_source_rows[:max_lab_failure_rows]

    research_rows: list[dict[str, Any]] = []
    adversarial_rows: list[dict[str, Any]] = []
    lab_failure_rows: list[dict[str, Any]] = []
    skipped_rows: list[dict[str, str]] = []
    for index, row in enumerate(source_rows):
        converted, error = convert_research_table_row(row)
        if converted is None:
            skipped_rows.append(
                {"dataset": "research_table", "index": str(index), "error": error or "unknown conversion error"}
            )
            continue
        research_rows.append(converted)
    for index, row in enumerate(adversarial_source_rows):
        converted, error = convert_research_table_row(row)
        if converted is None:
            skipped_rows.append(
                {"dataset": "adversarial_seed", "index": str(index), "error": error or "unknown conversion error"}
            )
            continue
        adversarial_rows.append(converted)
    for index, row in enumerate(lab_failure_source_rows):
        converted, error = convert_research_table_row(row)
        if converted is None:
            skipped_rows.append(
                {"dataset": "lab_failure", "index": str(index), "error": error or "unknown conversion error"}
            )
            continue
        lab_failure_rows.append(converted)

    deduplicated: list[dict[str, Any]] = []
    seen_sample_ids: set[str] = set()
    seen_fingerprints: set[str] = set()
    duplicate_rows_removed = 0
    for row in [*research_rows, *adversarial_rows, *lab_failure_rows]:
        sample_id = str(row.get("sample_id", "")).strip()
        fingerprint = raven_training_row_fingerprint(row)
        if sample_id in seen_sample_ids or fingerprint in seen_fingerprints:
            duplicate_rows_removed += 1
            continue
        seen_sample_ids.add(sample_id)
        seen_fingerprints.add(fingerprint)
        deduplicated.append(row)

    unique_research_rows = [
        row for row in deduplicated if row.get("metadata", {}).get("dataset_source") == "research_table"
    ]
    unique_adversarial_rows = [
        row for row in deduplicated if row.get("metadata", {}).get("dataset_source") == "adversarial_seed"
    ]
    unique_lab_failure_rows = [
        row for row in deduplicated if row.get("metadata", {}).get("dataset_source") == "lab_failure"
    ]
    weighted_adversarial_rows: list[dict[str, Any]] = []
    for row in unique_adversarial_rows:
        weighted_adversarial_rows.append(row)
        for weight_index in range(2, adversarial_weight + 1):
            weighted = copy.deepcopy(row)
            weighted["sample_id"] = f"{row['sample_id']}-weight-{weight_index}"
            weighted["metadata"]["sample_id"] = weighted["sample_id"]
            weighted["metadata"]["adversarial_weight_index"] = weight_index
            weighted_adversarial_rows.append(weighted)
    weighted_lab_failure_rows: list[dict[str, Any]] = []
    for row in unique_lab_failure_rows:
        weighted_lab_failure_rows.append(row)
        for weight_index in range(2, lab_failure_weight + 1):
            weighted = copy.deepcopy(row)
            weighted["sample_id"] = f"{row['sample_id']}-lab-weight-{weight_index}"
            weighted["metadata"]["sample_id"] = weighted["sample_id"]
            weighted["metadata"]["lab_failure_weight_index"] = weight_index
            weighted_lab_failure_rows.append(weighted)

    converted_rows = [*unique_research_rows, *weighted_adversarial_rows, *weighted_lab_failure_rows]
    combined_rows = len(converted_rows)

    if shuffle:
        random.Random(seed).shuffle(converted_rows)
    if max_rows > 0:
        converted_rows = converted_rows[:max_rows]

    if min_rows > 0 and len(converted_rows) < min_rows:
        raise ValueError(f"Prepared rows {len(converted_rows)} did not reach --min-rows {min_rows}.")
    if not converted_rows and not allow_empty:
        raise ValueError("Prepared dataset is empty. Use --allow-empty to write an empty dataset.")

    quality_gate = validate_rows(
        converted_rows,
        min_invalid_rows=min_invalid_rows,
        allow_low_invalid=allow_low_invalid,
        duplicate_rows_removed=duplicate_rows_removed,
    )
    quality_errors = list(quality_gate.get("errors", []))
    if allow_empty:
        quality_errors = [error for error in quality_errors if error != "Prepared Raven dataset has no rows."]
        quality_gate["errors"] = quality_errors
        quality_gate["passed"] = not quality_errors
    if quality_errors:
        raise ValueError("Raven training quality gate failed: " + " ".join(quality_errors))
    warnings = list(quality_gate.get("warnings", []))
    write_jsonl(target_path, converted_rows)
    manifest_path = write_manifest(
        target=target,
        input_path=source_path,
        adversarial_path=adversarial_source_path if include_adversarial_seeds else None,
        lab_failures_path=lab_failure_source_path if include_lab_failures else None,
        output_path=target_path,
        rows_total=len(source_rows) + len(adversarial_source_rows) + len(lab_failure_source_rows),
        rows_written=len(converted_rows),
        research_table_rows=len(unique_research_rows),
        adversarial_seed_rows=len(unique_adversarial_rows),
        lab_failure_rows=len(unique_lab_failure_rows),
        lab_failure_weight=lab_failure_weight,
        combined_rows=combined_rows,
        duplicate_rows_removed=duplicate_rows_removed,
        rows=converted_rows,
        quality_gate=quality_gate,
        warnings=warnings,
    )
    payload = {
        "target_agent": target,
        "input_path": str(source_path),
        "adversarial_path": str(adversarial_source_path) if include_adversarial_seeds else "",
        "lab_failures_path": str(lab_failure_source_path) if include_lab_failures else "",
        "output_path": str(target_path),
        "rows_total": len(source_rows) + len(adversarial_source_rows) + len(lab_failure_source_rows),
        "rows_written": len(converted_rows),
        "research_table_rows": len(unique_research_rows),
        "adversarial_seed_rows": len(unique_adversarial_rows),
        "lab_failure_rows": len(unique_lab_failure_rows),
        "combined_rows": combined_rows,
        "duplicate_rows_removed": duplicate_rows_removed,
        "skipped_rows": len(skipped_rows),
        "manifest_path": str(manifest_path),
        "quality_gate": quality_gate,
        "warnings": warnings,
    }
    if skipped_rows:
        payload["skipped_examples"] = skipped_rows[:5]
    return payload


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root_path)
    input_path = Path(args.input) if args.input else (
        root / "mystic_data" / "datasets" / "raven" / "research_table_raven.jsonl"
    )
    output_path = Path(args.output) if args.output else (
        root / "mystic_data" / "training" / "raven" / "research_table_train.jsonl"
    )
    adversarial_path = Path(args.adversarial_path) if args.adversarial_path else (
        root / "mystic_data" / "datasets" / "raven" / "adversarial_seed_raven.jsonl"
    )
    lab_failures_path = Path(args.lab_failures_path) if args.lab_failures_path else (
        root / "mystic_data" / "datasets" / "lab" / "raven_lab_failures.jsonl"
    )
    try:
        payload = prepare_research_table_training(
            target=args.target,
            input_path=input_path,
            output_path=output_path,
            min_rows=args.min_rows,
            max_rows=args.max_rows,
            shuffle=args.shuffle,
            seed=args.seed,
            allow_empty=args.allow_empty,
            include_adversarial_seeds=args.include_adversarial_seeds,
            adversarial_path=adversarial_path,
            adversarial_weight=args.adversarial_weight,
            max_adversarial_rows=args.max_adversarial_rows,
            include_lab_failures=args.include_lab_failures,
            lab_failures_path=lab_failures_path,
            lab_failure_weight=args.lab_failure_weight,
            max_lab_failure_rows=args.max_lab_failure_rows,
            min_invalid_rows=args.min_invalid_rows,
            allow_low_invalid=args.allow_low_invalid,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 1

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

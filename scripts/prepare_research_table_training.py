from __future__ import annotations

import argparse
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


MIN_INVALID_ROWS_WARNING_THRESHOLD = 5


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert Research Table Raven rows into Raven LoRA training rows.")
    parser.add_argument("--target", default="raven", choices=["raven"])
    parser.add_argument(
        "--input",
        default=str(ROOT / "mystic_data" / "datasets" / "raven" / "research_table_raven.jsonl"),
        help="Research Table Raven dataset JSONL path.",
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "mystic_data" / "training" / "raven" / "research_table_train.jsonl"),
        help="Prepared Raven training JSONL output path.",
    )
    parser.add_argument("--min-rows", type=int, default=0, help="Optional minimum number of rows required after filtering.")
    parser.add_argument("--max-rows", type=int, default=0, help="Optional maximum number of rows to write.")
    parser.add_argument("--shuffle", action="store_true", help="Shuffle rows before applying --max-rows.")
    parser.add_argument("--seed", type=int, default=0, help="Seed used with --shuffle.")
    parser.add_argument("--allow-empty", action="store_true", help="Allow writing an empty prepared dataset.")
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
    text = "|".join(
        [
            str(source.get("session_id", "")).strip(),
            str(source.get("turn_id", "")).strip(),
            str(source.get("discovery_id", "")).strip(),
            str(source.get("label_id", "")).strip(),
            normalize_raven_verdict(verdict),
        ]
    )
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return f"research-table-raven-{digest}"


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
    return bool(str(source.get("discovery_id", "")).strip()) and not bool(str(source.get("label_id", "")).strip())


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
    metadata = {
        "target_agent": "raven",
        "dataset_source": "research_table",
        "research_table": {
            "problem": problem,
            "model_output": str(input_payload.get("model_output", "") or ""),
            "discovery_or_claim": str(input_payload.get("discovery_or_claim", "") or ""),
            "tool_evidence": str(input_payload.get("tool_evidence", "") or ""),
            "expected_verdict": verdict,
            "first_fatal_error": str(output_payload.get("first_fatal_error", "") or ""),
            "critique": str(output_payload.get("critique", "") or ""),
            "recommended_next_action": str(output_payload.get("recommended_next_action", "") or ""),
            "source": {
                "session_id": str(source.get("session_id", "") or ""),
                "turn_id": str(source.get("turn_id", "") or ""),
                "discovery_id": str(source.get("discovery_id", "") or ""),
                "label_id": str(source.get("label_id", "") or ""),
            },
            "verifier_derived": is_verifier_derived(source),
        },
        "sample_id": build_sample_id(source, verdict),
    }
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
    unique_turns: set[str] = set()
    unique_discoveries: set[str] = set()
    unique_labels: set[str] = set()
    for row in rows:
        metadata = row.get("metadata", {})
        research_table = metadata.get("research_table", {}) if isinstance(metadata, dict) else {}
        source = research_table.get("source", {}) if isinstance(research_table, dict) else {}
        session_id = str(source.get("session_id", "")).strip()
        turn_id = str(source.get("turn_id", "")).strip()
        discovery_id = str(source.get("discovery_id", "")).strip()
        label_id = str(source.get("label_id", "")).strip()
        if session_id:
            sessions[session_id] += 1
        if turn_id:
            unique_turns.add(turn_id)
        if discovery_id:
            unique_discoveries.add(discovery_id)
        if label_id:
            unique_labels.add(label_id)
    return {
        "sessions": dict(sorted(sessions.items())),
        "unique_turns": len(unique_turns),
        "unique_discoveries": len(unique_discoveries),
        "unique_labels": len(unique_labels),
    }


def validate_rows(rows: list[dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    verdicts = Counter(str(row.get("target_verdict", "")).strip().upper() for row in rows)
    invalid_count = int(verdicts.get("INVALID", 0))
    if rows and invalid_count < MIN_INVALID_ROWS_WARNING_THRESHOLD:
        warnings.append(
            f"Too few INVALID rows for conservative Raven training: {invalid_count} < {MIN_INVALID_ROWS_WARNING_THRESHOLD}."
        )

    missing_fatal = 0
    missing_tool_evidence = 0
    for row in rows:
        assistant_output = str(row.get("assistant_output", "") or "")
        metadata = row.get("metadata", {})
        research_table = metadata.get("research_table", {}) if isinstance(metadata, dict) else {}
        try:
            output_payload = json.loads(assistant_output)
        except json.JSONDecodeError:
            continue
        verdict = str(output_payload.get("verdict", "")).strip().upper()
        first_fatal_error = str(output_payload.get("first_fatal_error", "") or "").strip()
        tool_evidence = str(research_table.get("tool_evidence", "") or "").strip()
        verifier_derived = bool(research_table.get("verifier_derived"))
        if verdict == "INVALID" and not first_fatal_error:
            missing_fatal += 1
        if verifier_derived and not tool_evidence:
            missing_tool_evidence += 1

    if missing_fatal:
        warnings.append(f"{missing_fatal} INVALID rows are missing first_fatal_error.")
    if missing_tool_evidence:
        warnings.append(f"{missing_tool_evidence} verifier-derived rows are missing tool_evidence.")
    return warnings


def write_manifest(
    *,
    target: str,
    input_path: Path,
    output_path: Path,
    rows_total: int,
    rows_written: int,
    rows: list[dict[str, Any]],
    warnings: list[str],
) -> Path:
    verdict_distribution = Counter(str(row.get("target_verdict", "")).strip().upper() for row in rows)
    manifest = {
        "target_agent": target,
        "input_path": str(input_path),
        "output_path": str(output_path),
        "rows_total": rows_total,
        "rows_written": rows_written,
        "verdict_distribution": dict(sorted(verdict_distribution.items())),
        "source_counts": build_source_counts(rows),
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
) -> dict[str, Any]:
    source_path = Path(input_path)
    target_path = Path(output_path)
    if not source_path.exists():
        raise FileNotFoundError(f"Input file not found: {source_path}")

    source_rows = load_jsonl(source_path)
    converted_rows: list[dict[str, Any]] = []
    skipped_rows: list[dict[str, str]] = []
    for index, row in enumerate(source_rows):
        converted, error = convert_research_table_row(row)
        if converted is None:
            skipped_rows.append({"index": str(index), "error": error or "unknown conversion error"})
            continue
        converted_rows.append(converted)

    if shuffle:
        random.Random(seed).shuffle(converted_rows)
    if max_rows > 0:
        converted_rows = converted_rows[:max_rows]

    if min_rows > 0 and len(converted_rows) < min_rows:
        raise ValueError(f"Prepared rows {len(converted_rows)} did not reach --min-rows {min_rows}.")
    if not converted_rows and not allow_empty:
        raise ValueError("Prepared dataset is empty. Use --allow-empty to write an empty dataset.")

    warnings = validate_rows(converted_rows)
    write_jsonl(target_path, converted_rows)
    manifest_path = write_manifest(
        target=target,
        input_path=source_path,
        output_path=target_path,
        rows_total=len(source_rows),
        rows_written=len(converted_rows),
        rows=converted_rows,
        warnings=warnings,
    )
    payload = {
        "target_agent": target,
        "input_path": str(source_path),
        "output_path": str(target_path),
        "rows_total": len(source_rows),
        "rows_written": len(converted_rows),
        "skipped_rows": len(skipped_rows),
        "manifest_path": str(manifest_path),
        "warnings": warnings,
    }
    if skipped_rows:
        payload["skipped_examples"] = skipped_rows[:5]
    return payload


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = prepare_research_table_training(
            target=args.target,
            input_path=args.input,
            output_path=args.output,
            min_rows=args.min_rows,
            max_rows=args.max_rows,
            shuffle=args.shuffle,
            seed=args.seed,
            allow_empty=args.allow_empty,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 1

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any

from mystic.jsonl_loop import build_paths, export_raven_lora_rows, read_jsonl
from mystic.training.public_prepare import _normalize_public_row


RAVEN_ALLOWED_SOURCES = (
    "numinamath_cot",
    "openmathinstruct_2",
    "openr1_mixture_of_thoughts",
    "proofnet",
    "leandojo",
)

VERDICT_PATTERN = (
    "VALID",
    "INVALID",
    "INVALID",
    "INVALID",
    "INVALID",
    "GAP",
    "GAP",
    "GAP",
    "NEEDS_MORE_DETAIL",
    "NEEDS_MORE_DETAIL",
)


def build_raven_lora_export(base_dir: str | Path, *, target_rows: int = 0) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    base = Path(base_dir)
    paths = build_paths(base)
    internal_rows = export_raven_lora_rows(read_jsonl(paths.raven_critiques_file))
    desired_rows = max(int(target_rows), len(internal_rows))
    if desired_rows == 0:
        desired_rows = len(internal_rows)

    rows = list(internal_rows)
    synthetic_rows: list[dict[str, Any]] = []
    candidate_rows = load_raven_source_candidates(base)
    source_counter: Counter[str] = Counter()
    verdict_counter: Counter[str] = Counter()

    existing_ids = {
        str(row.get("metadata", {}).get("sample_id", ""))
        for row in rows
        if isinstance(row.get("metadata"), dict)
    }

    if desired_rows > len(rows) and candidate_rows:
        needed = desired_rows - len(rows)
        for index in range(needed):
            candidate = candidate_rows[index % len(candidate_rows)]
            variant = index // len(candidate_rows)
            row = build_synthetic_raven_row(candidate, sample_index=index, variant=variant)
            sample_id = str(row.get("metadata", {}).get("sample_id", ""))
            if sample_id in existing_ids:
                continue
            existing_ids.add(sample_id)
            rows.append(row)
            synthetic_rows.append(row)
            source_counter[str(row["metadata"].get("source_slug", "unknown"))] += 1
            verdict_counter[str(row.get("classification", "NEEDS_MORE_DETAIL"))] += 1

    payload = {
        "source_file": str(paths.raven_critiques_file),
        "output_files": [
            str(paths.raven_lora_file),
            str(paths.raven_lora_train_ready_file),
        ],
        "row_count": len(rows),
        "internal_row_count": len(internal_rows),
        "synthetic_row_count": len(synthetic_rows),
        "target_rows": int(target_rows),
        "candidate_count": len(candidate_rows),
        "synthetic_source_counts": dict(source_counter),
        "synthetic_verdict_counts": dict(verdict_counter),
    }
    return rows, payload


def load_raven_source_candidates(base_dir: Path) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    seen: set[str] = set()

    raw_root = base_dir / "raw"
    raw_paths = {
        "numinamath_cot": raw_root / "numina_math_cot_100.jsonl",
        "openmathinstruct_2": raw_root / "openmathinstruct_2" / "sample.jsonl",
        "openr1_mixture_of_thoughts": raw_root / "openr1_mixture_of_thoughts" / "sample.jsonl",
        "proofnet": raw_root / "proofnet" / "sample.jsonl",
        "leandojo": raw_root / "leandojo" / "sample.jsonl",
    }
    for source_slug, path in raw_paths.items():
        if not path.exists():
            continue
        for row in iter_jsonl(path):
            normalized = normalize_candidate_row(source_slug, row)
            if normalized is None:
                continue
            key = dedupe_key(normalized["problem"], normalized["solution"], normalized["source_slug"])
            if key in seen:
                continue
            seen.add(key)
            candidates.append(normalized)

    train_ready_root = base_dir / "train_ready"
    for path in sorted(train_ready_root.glob("*_train_ready.jsonl")):
        for row in iter_jsonl(path):
            metadata = row.get("metadata", {})
            if not isinstance(metadata, dict):
                continue
            source_slug = str(metadata.get("dataset", "")).strip()
            if source_slug not in RAVEN_ALLOWED_SOURCES:
                continue
            normalized = normalize_train_ready_candidate(source_slug, row)
            if normalized is None:
                continue
            key = dedupe_key(normalized["problem"], normalized["solution"], normalized["source_slug"])
            if key in seen:
                continue
            seen.add(key)
            candidates.append(normalized)

    return candidates


def iter_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(json.loads(stripped))
    return rows


def normalize_candidate_row(source_slug: str, row: dict[str, Any]) -> dict[str, str] | None:
    if source_slug == "numinamath_cot":
        problem = str(row.get("problem", "")).strip()
        solution = str(row.get("reference_solution", "") or row.get("solution", "")).strip()
        if problem and solution:
            return {"problem": problem, "solution": solution, "source_slug": source_slug}
        return None
    normalized = _normalize_public_row(source_slug, row)
    if normalized is None:
        return None
    return {
        "problem": normalized["problem"],
        "solution": normalized["solution"],
        "source_slug": source_slug,
    }


def normalize_train_ready_candidate(source_slug: str, row: dict[str, Any]) -> dict[str, str] | None:
    input_text = str(row.get("input", "")).strip()
    output_text = str(row.get("output", "")).strip()
    problem = input_text
    if "Problem:\n" in input_text:
        problem = input_text.split("Problem:\n", 1)[1].strip()
    if not problem or not output_text:
        return None
    return {
        "problem": problem,
        "solution": output_text,
        "source_slug": source_slug,
    }


def dedupe_key(problem: str, solution: str, source_slug: str) -> str:
    text = f"{source_slug}\n{problem}\n{solution[:400]}"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_synthetic_raven_row(candidate: dict[str, str], *, sample_index: int, variant: int) -> dict[str, Any]:
    verdict = VERDICT_PATTERN[sample_index % len(VERDICT_PATTERN)]
    proof_attempt = build_proof_attempt(candidate["solution"], verdict=verdict, variant=variant)
    output_payload = build_raven_output(candidate["problem"], proof_attempt, candidate["solution"], verdict=verdict)
    sample_id = build_sample_id(candidate, verdict=verdict, sample_index=sample_index, variant=variant)
    return {
        "instruction": "Critique the proof like Mystic-Raven and return JSON only.",
        "input": f"Problem:\n{candidate['problem']}\n\nProof attempt:\n{proof_attempt}",
        "output": json.dumps(output_payload, ensure_ascii=True),
        "classification": verdict,
        "problem": candidate["problem"],
        "proof_attempt": proof_attempt,
            "metadata": {
                "sample_id": sample_id,
                "source_slug": candidate["source_slug"],
                "synthetic": True,
                "sample_index": sample_index,
                "variant": variant,
            },
        }


def build_sample_id(candidate: dict[str, str], *, verdict: str, sample_index: int, variant: int) -> str:
    digest = hashlib.sha256(
        f"{candidate['source_slug']}|{candidate['problem']}|{verdict}|{sample_index}|{variant}".encode("utf-8")
    ).hexdigest()[:16]
    return f"raven-{candidate['source_slug']}-{sample_index:04d}-{variant:04d}-{digest}"


def build_proof_attempt(solution: str, *, verdict: str, variant: int) -> str:
    cleaned = compact_text(solution, limit=2200)
    short = first_sentences(cleaned, sentence_count=2, fallback_chars=320)
    if verdict == "VALID":
        return cleaned
    if verdict == "INVALID":
        return (
            f"{short}\n\n"
            "Clearly, checking a few examples proves the general statement.\n"
            "Therefore the omitted algebra is harmless, so the conclusion follows for every case."
        )
    if verdict == "GAP":
        return (
            f"{short}\n\n"
            "The remaining key derivation is standard and we omit it.\n"
            "Hence the theorem follows."
        )
    return short


def build_raven_output(problem: str, proof_attempt: str, solution: str, *, verdict: str) -> dict[str, Any]:
    base_valid_steps = [
        "The attempt identifies the target claim.",
        "Some relevant setup or notation is present.",
    ]
    if verdict == "VALID":
        return {
            "verdict": "VALID",
            "first_fatal_error": "",
            "missing_assumptions": [],
            "invalid_steps": [],
            "valid_steps": base_valid_steps + ["The derivation is internally consistent at a coarse level."],
            "repair_possible": True,
            "confidence": 0.55,
            "final_status": "VALID",
        }
    if verdict == "INVALID":
        return {
            "verdict": "INVALID",
            "first_fatal_error": "The argument jumps from a few examples to a universal claim without justification.",
            "missing_assumptions": ["A general proof covering all cases is missing."],
            "invalid_steps": [
                "Empirical checks are treated as a proof.",
                "An omitted algebraic justification is asserted to be harmless without proof.",
            ],
            "valid_steps": base_valid_steps,
            "repair_possible": True,
            "confidence": 0.93,
            "final_status": "INVALID",
        }
    if verdict == "GAP":
        return {
            "verdict": "GAP",
            "first_fatal_error": "A crucial intermediate derivation is omitted exactly where the conclusion depends on it.",
            "missing_assumptions": ["The missing lemma or calculation is not established."],
            "invalid_steps": [],
            "valid_steps": base_valid_steps + ["The high-level strategy may be relevant to the problem."],
            "repair_possible": True,
            "confidence": 0.88,
            "final_status": "GAP",
        }
    return {
        "verdict": "NEEDS_MORE_DETAIL",
        "first_fatal_error": "The proof attempt is too compressed to verify the main transition.",
        "missing_assumptions": ["Intermediate steps and explicit justification are absent."],
        "invalid_steps": [],
        "valid_steps": ["The attempt appears to point at a possible approach."],
        "repair_possible": True,
        "confidence": 0.9,
        "final_status": "NEEDS_MORE_DETAIL",
    }


def compact_text(text: str, *, limit: int) -> str:
    single_line = " ".join(str(text).split())
    return single_line[:limit].strip()


def first_sentences(text: str, *, sentence_count: int, fallback_chars: int) -> str:
    parts = [part.strip() for part in text.replace("\n", " ").split(".") if part.strip()]
    if parts:
        clipped = ". ".join(parts[:sentence_count]).strip()
        if clipped:
            return clipped + "."
    return text[:fallback_chars].strip()

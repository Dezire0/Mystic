"""Shared helpers for the Mystic v2 Raven training pipeline."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any


RAVEN_TRAINING_SYSTEM_PROMPT = (
    "You are Mystic-Raven, a hostile mathematical proof referee. "
    "Your job is to detect invalid reasoning, hidden assumptions, gaps, and false proof claims."
)


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    target = Path(path)
    if not target.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(json.loads(stripped))
    return rows


def write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(json.dumps(row, ensure_ascii=True) for row in rows)
    target.write_text(payload + ("\n" if rows else ""), encoding="utf-8")


def append_jsonl(path: str | Path, row: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def build_user_prompt(problem: str, proof_attempt: str) -> str:
    return (
        f"Problem:\n{problem}\n\n"
        f"Proof attempt:\n{proof_attempt}\n\n"
        "Critique the proof attempt. Output JSON only."
    )


def build_chat_messages(problem: str, proof_attempt: str, assistant_output: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": RAVEN_TRAINING_SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(problem, proof_attempt)},
        {"role": "assistant", "content": assistant_output},
    ]


def fallback_chat_text(messages: list[dict[str, str]], add_generation_prompt: bool = False) -> str:
    parts: list[str] = []
    for message in messages:
        parts.append(f"{message['role'].upper()}:\n{message['content']}")
    if add_generation_prompt:
        parts.append("ASSISTANT:\n")
    return "\n\n".join(parts)


def render_chat_text(tokenizer: Any, messages: list[dict[str, str]], add_generation_prompt: bool = False) -> str:
    if hasattr(tokenizer, "apply_chat_template"):
        rendered = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=add_generation_prompt,
        )
        if isinstance(rendered, str) and rendered.strip():
            return rendered
    return fallback_chat_text(messages, add_generation_prompt=add_generation_prompt)


def parse_problem_and_proof(row: dict[str, Any]) -> tuple[str, str]:
    problem = str(row.get("problem", "")).strip()
    proof_attempt = str(row.get("proof_attempt", "")).strip()
    if problem and proof_attempt:
        return problem, proof_attempt

    input_text = str(row.get("input", "")).strip()
    if "Problem:\n" in input_text and "\n\nProof attempt:\n" in input_text:
        _, remainder = input_text.split("Problem:\n", 1)
        problem_part, proof_part = remainder.split("\n\nProof attempt:\n", 1)
        return problem_part.strip(), proof_part.strip()
    return problem, proof_attempt


def parse_target_verdict(output_text: str) -> str | None:
    try:
        payload = json.loads(output_text)
    except json.JSONDecodeError:
        return None
    verdict = str(payload.get("verdict", "")).strip().upper()
    return verdict or None


def normalize_raven_lora_row(row: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    output_text = str(row.get("output", "")).strip()
    if not output_text:
        return None, "missing output"

    try:
        json.loads(output_text)
    except json.JSONDecodeError as exc:
        return None, f"invalid output json: {exc}"

    problem, proof_attempt = parse_problem_and_proof(row)
    if not problem:
        return None, "missing problem"
    if not proof_attempt:
        return None, "missing proof_attempt"

    sample_id = str(row.get("metadata", {}).get("sample_id") or row.get("sample_id") or "").strip()
    target_verdict = parse_target_verdict(output_text)
    if not target_verdict:
        return None, "missing verdict in output"

    normalized = {
        "sample_id": sample_id or f"row-{hashlib.sha256(output_text.encode('utf-8')).hexdigest()[:12]}",
        "problem": problem,
        "proof_attempt": proof_attempt,
        "messages": build_chat_messages(problem, proof_attempt, output_text),
        "assistant_output": output_text,
        "target_verdict": target_verdict,
        "metadata": row.get("metadata", {}),
    }
    return normalized, None


def split_train_eval(rows: list[dict[str, Any]], eval_ratio: float) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not rows:
        return [], []
    if eval_ratio <= 0:
        return rows, []
    if eval_ratio >= 1:
        return [], rows

    ordered = sorted(rows, key=lambda item: str(item.get("sample_id", "")))
    eval_count = max(1, int(round(len(ordered) * eval_ratio))) if len(ordered) > 1 else 0
    train_count = max(len(ordered) - eval_count, 1)
    train_rows = ordered[:train_count]
    eval_rows = ordered[train_count:]
    if not eval_rows and len(ordered) > 1:
        eval_rows = [train_rows.pop()]
    return train_rows, eval_rows

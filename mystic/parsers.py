"""Robust parsers for model outputs used by the Mystic loop."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from typing import Any
import uuid

from mystic.schema import RavenCritique, Verdict


ALLOWED_VERDICTS: set[Verdict] = {"VALID", "INVALID", "GAP", "NEEDS_MORE_DETAIL"}


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _strip_code_fences(raw_output: str) -> str:
    stripped = raw_output.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()
    return stripped


def _candidate_json_strings(raw_output: str) -> list[str]:
    stripped = _strip_code_fences(raw_output)
    candidates = [stripped]
    decoder = json.JSONDecoder()
    for index, char in enumerate(stripped):
        if char != "{":
            continue
        try:
            payload, end = decoder.raw_decode(stripped[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            candidates.append(stripped[index : index + end])
            break
    return candidates


def _parse_json_object(raw_output: str) -> tuple[dict[str, Any] | None, str | None]:
    last_error: str | None = "Raven returned empty output."
    for candidate in _candidate_json_strings(raw_output):
        if not candidate:
            continue
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = str(exc)
            continue
        if isinstance(payload, dict):
            return payload, None
        last_error = "Raven JSON root must be an object."
    return None, last_error


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def _string_value(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _bool_value(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1"}:
            return True
        if lowered in {"false", "no", "0"}:
            return False
    return default


def _float_value(value: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _normalize_verdict(value: Any) -> Verdict:
    verdict = str(value or "").strip().upper()
    if verdict in ALLOWED_VERDICTS:
        return verdict  # type: ignore[return-value]
    return "NEEDS_MORE_DETAIL"


def fallback_raven_critique(
    *,
    sample_id: str,
    run_id: str,
    backend: str,
    model: str,
    raw_output: str,
    first_fatal_error: str,
    final_status: str = "NEEDS_MORE_DETAIL",
    parse_error: str | None = None,
) -> RavenCritique:
    return RavenCritique(
        critique_id=str(uuid.uuid4()),
        sample_id=sample_id,
        run_id=run_id,
        backend=backend,
        model=model,
        verdict="NEEDS_MORE_DETAIL",
        first_fatal_error=first_fatal_error,
        missing_assumptions=[],
        invalid_steps=[],
        valid_steps=[],
        repair_possible=True,
        confidence=0.0,
        final_status=final_status,
        raw_output=raw_output,
        parse_error=parse_error,
        parsed_at=_now_iso(),
    )


def parse_raven_output(
    *,
    raw_output: str,
    sample_id: str,
    run_id: str,
    backend: str,
    model: str,
) -> RavenCritique:
    payload, parse_error = _parse_json_object(raw_output)
    if payload is None:
        return fallback_raven_critique(
            sample_id=sample_id,
            run_id=run_id,
            backend=backend,
            model=model,
            raw_output=raw_output,
            first_fatal_error="Raven returned invalid JSON.",
            parse_error=parse_error,
        )

    verdict = _normalize_verdict(payload.get("verdict"))
    first_fatal_error = _string_value(payload.get("first_fatal_error"))
    if not first_fatal_error and verdict != "VALID":
        first_fatal_error = "No fatal error was provided."

    final_status = _string_value(payload.get("final_status"), verdict)
    return RavenCritique(
        critique_id=str(uuid.uuid4()),
        sample_id=sample_id,
        run_id=run_id,
        backend=backend,
        model=model,
        verdict=verdict,
        first_fatal_error=first_fatal_error,
        missing_assumptions=_string_list(payload.get("missing_assumptions")),
        invalid_steps=_string_list(payload.get("invalid_steps")),
        valid_steps=_string_list(payload.get("valid_steps")),
        repair_possible=_bool_value(payload.get("repair_possible"), True),
        confidence=_float_value(payload.get("confidence"), 0.0),
        final_status=final_status or verdict,
        raw_output=raw_output,
        parse_error=None if parse_error is None else parse_error,
        parsed_at=_now_iso(),
    )

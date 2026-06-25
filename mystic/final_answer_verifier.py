from __future__ import annotations

from fractions import Fraction
import re
from typing import Any


EGYPTIAN_FRACTION_PATTERN = re.compile(
    r"1\s*/\s*x\s*\+\s*1\s*/\s*y\s*\+\s*1\s*/\s*z\s*=\s*1",
    re.IGNORECASE,
)
ORDER_PATTERN = re.compile(r"x\s*<=\s*y\s*<=\s*z", re.IGNORECASE)
POSITIVE_INTEGER_PATTERN = re.compile(r"positive integers|양의 정수", re.IGNORECASE)
TUPLE_PATTERN = re.compile(r"\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)")


def verify_final_answer(*, problem: str, answer_text: str) -> dict[str, Any] | None:
    if is_egyptian_fraction_tuple_problem(problem):
        return verify_egyptian_fraction_tuples(problem=problem, answer_text=answer_text)
    return None


def is_egyptian_fraction_tuple_problem(problem: str) -> bool:
    text = " ".join(problem.split())
    return bool(
        EGYPTIAN_FRACTION_PATTERN.search(text)
        and ORDER_PATTERN.search(text)
        and POSITIVE_INTEGER_PATTERN.search(text)
    )


def extract_candidate_tuples(answer_text: str) -> list[tuple[int, int, int]]:
    seen: list[tuple[int, int, int]] = []
    for match in TUPLE_PATTERN.finditer(answer_text):
        triple = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        if triple not in seen:
            seen.append(triple)
    return seen


def enumerate_egyptian_fraction_solutions() -> list[tuple[int, int, int]]:
    results: list[tuple[int, int, int]] = []
    for x in range(1, 4):
        for y in range(x, 16):
            for z in range(y, 32):
                if Fraction(1, x) + Fraction(1, y) + Fraction(1, z) == 1:
                    results.append((x, y, z))
    return results


def verify_egyptian_fraction_tuples(*, problem: str, answer_text: str) -> dict[str, Any]:
    del problem
    candidates = extract_candidate_tuples(answer_text)
    valid_solutions = enumerate_egyptian_fraction_solutions()
    valid_set = set(valid_solutions)
    candidate_set = set(candidates)

    invalid_candidates: list[str] = []
    for triple in candidates:
        lhs = Fraction(1, triple[0]) + Fraction(1, triple[1]) + Fraction(1, triple[2])
        if lhs != 1:
            invalid_candidates.append(f"{triple} gives {lhs} != 1")
        elif not (triple[0] <= triple[1] <= triple[2]):
            invalid_candidates.append(f"{triple} violates x <= y <= z")

    missing_candidates = sorted(valid_set - candidate_set)
    if invalid_candidates or missing_candidates:
        details: list[str] = []
        details.extend(invalid_candidates)
        if missing_candidates:
            details.append(
                "Missing valid solutions: " + ", ".join(str(item) for item in missing_candidates)
            )
        return {
            "verdict": "INVALID",
            "first_fatal_error": details[0],
            "invalid_steps": details,
            "valid_steps": [f"Verified solutions: {', '.join(str(item) for item in valid_solutions)}"],
            "repair_possible": True,
            "confidence": 1.0,
            "final_status": "INVALID",
        }

    if candidates:
        return {
            "verdict": "VALID",
            "first_fatal_error": "",
            "invalid_steps": [],
            "valid_steps": [f"All listed solutions pass substitution: {', '.join(str(item) for item in candidates)}"],
            "repair_possible": False,
            "confidence": 1.0,
            "final_status": "VALID",
        }
    return {
        "verdict": "NEEDS_MORE_DETAIL",
        "first_fatal_error": "No candidate tuples were found for direct verification.",
        "invalid_steps": [],
        "valid_steps": [],
        "repair_possible": True,
        "confidence": 0.0,
        "final_status": "NEEDS_MORE_DETAIL",
    }

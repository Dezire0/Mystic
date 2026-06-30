from __future__ import annotations

from fractions import Fraction

from mystic.verification.candidate_extractor import POSITIVE_INTEGER_PATTERN, extract_order_constraints


def check_positive_integer_constraints(problem: str, assignment: dict[str, Fraction]) -> list[str]:
    if not POSITIVE_INTEGER_PATTERN.search(problem):
        return []
    failures: list[str] = []
    for variable, value in assignment.items():
        if value.denominator != 1 or value <= 0:
            failures.append(f"{variable}={value} violates positive integer constraint")
    return failures


def check_order_constraints(problem: str, assignment: dict[str, Fraction]) -> list[str]:
    failures: list[str] = []
    for left, operator, right in extract_order_constraints(problem):
        left_value = assignment.get(left)
        right_value = assignment.get(right)
        if left_value is None or right_value is None:
            continue
        if operator == "<=" and not (left_value <= right_value):
            failures.append(f"{left}={left_value} > {right}={right_value}")
        elif operator == "<" and not (left_value < right_value):
            failures.append(f"{left}={left_value} >= {right}={right_value}")
        elif operator == ">=" and not (left_value >= right_value):
            failures.append(f"{left}={left_value} < {right}={right_value}")
        elif operator == ">" and not (left_value > right_value):
            failures.append(f"{left}={left_value} <= {right}={right_value}")
    return failures

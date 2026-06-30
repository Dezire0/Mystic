from __future__ import annotations

from dataclasses import asdict, dataclass, field
from fractions import Fraction
from typing import Any

from mystic.verification.candidate_extractor import (
    extract_candidate_tuples,
    extract_equations,
    infer_variable_order,
    is_egyptian_fraction_tuple_problem,
    variables_in_expression,
)
from mystic.verification.constraint_checker import (
    check_order_constraints,
    check_positive_integer_constraints,
)
from mystic.verification.integer_bruteforce import (
    enumerate_egyptian_fraction_solutions,
)
from mystic.verification.substitution_checker import verify_equations


@dataclass(slots=True)
class VerificationResult:
    verdict: str
    first_fatal_error: str
    invalid_steps: list[str]
    valid_steps: list[str]
    repair_possible: bool
    confidence: float
    final_status: str
    valid: bool
    failed_candidates: list[str] = field(default_factory=list)
    passed_candidates: list[str] = field(default_factory=list)
    missing_candidates: list[str] = field(default_factory=list)
    constraint_failures: list[str] = field(default_factory=list)
    reasoning: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _result_from_invalid(
    *,
    invalid_steps: list[str],
    valid_steps: list[str],
    failed_candidates: list[str] | None = None,
    passed_candidates: list[str] | None = None,
    missing_candidates: list[str] | None = None,
    constraint_failures: list[str] | None = None,
    reasoning: str,
) -> VerificationResult:
    return VerificationResult(
        verdict="INVALID",
        first_fatal_error=invalid_steps[0] if invalid_steps else "Verification failed.",
        invalid_steps=invalid_steps,
        valid_steps=valid_steps,
        repair_possible=True,
        confidence=1.0,
        final_status="INVALID",
        valid=False,
        failed_candidates=failed_candidates or [],
        passed_candidates=passed_candidates or [],
        missing_candidates=missing_candidates or [],
        constraint_failures=constraint_failures or [],
        reasoning=reasoning,
    )


def _result_from_valid(
    *,
    valid_steps: list[str],
    passed_candidates: list[str] | None = None,
    reasoning: str,
) -> VerificationResult:
    return VerificationResult(
        verdict="VALID",
        first_fatal_error="",
        invalid_steps=[],
        valid_steps=valid_steps,
        repair_possible=False,
        confidence=1.0,
        final_status="VALID",
        valid=True,
        passed_candidates=passed_candidates or [],
        reasoning=reasoning,
    )


def verify_explicit_candidates(problem: str, answer_text: str) -> dict[str, Any] | None:
    candidates = extract_candidate_tuples(answer_text)
    if not candidates:
        return None
    variable_order = infer_variable_order(problem, len(candidates[0]))
    if len(variable_order) != len(candidates[0]):
        return None

    invalid_steps: list[str] = []
    valid_steps: list[str] = []
    failed_candidates: list[str] = []
    passed_candidates: list[str] = []
    constraint_failures: list[str] = []
    any_equation_checked = False
    for candidate in candidates:
        assignment = {
            variable: Fraction(value)
            for variable, value in zip(variable_order, candidate)
        }
        applicable_equations = [
            (left, right)
            for left, right in extract_equations(problem)
            if (variables_in_expression(left) | variables_in_expression(right)).issubset(set(assignment))
        ]
        if applicable_equations:
            any_equation_checked = True
        failures = [
            *check_positive_integer_constraints(problem, assignment),
            *check_order_constraints(problem, assignment),
            *verify_equations(problem, assignment),
        ]
        if failures:
            rendered = f"{candidate}: " + "; ".join(failures)
            invalid_steps.append(rendered)
            failed_candidates.append(str(candidate))
            constraint_failures.extend(failures)
        else:
            valid_steps.append(f"{candidate} passes direct substitution")
            passed_candidates.append(str(candidate))

    if not any_equation_checked:
        return None

    if invalid_steps:
        return _result_from_invalid(
            invalid_steps=invalid_steps,
            valid_steps=valid_steps,
            failed_candidates=failed_candidates,
            passed_candidates=passed_candidates,
            constraint_failures=constraint_failures,
            reasoning="Direct substitution or explicit constraints failed for at least one candidate.",
        ).to_dict()

    return _result_from_valid(
        valid_steps=valid_steps,
        passed_candidates=passed_candidates,
        reasoning="All explicit candidates satisfy direct substitution and parsed constraints.",
    ).to_dict()


def verify_egyptian_fraction_finite_case(problem: str, answer_text: str) -> dict[str, Any] | None:
    if not is_egyptian_fraction_tuple_problem(problem):
        return None
    candidates = [triple for triple in extract_candidate_tuples(answer_text) if len(triple) == 3]
    valid_solutions = enumerate_egyptian_fraction_solutions()
    valid_set = set(valid_solutions)
    candidate_set = set(candidates)
    invalid_steps: list[str] = []
    missing_candidates = sorted(valid_set - candidate_set)
    unexpected_candidates = sorted(candidate_set - valid_set)
    if unexpected_candidates:
        invalid_steps.append(
            "Unexpected invalid candidates: " + ", ".join(str(item) for item in unexpected_candidates)
        )
    if missing_candidates:
        invalid_steps.append("Missing valid solutions: " + ", ".join(str(item) for item in missing_candidates))
    if invalid_steps:
        return _result_from_invalid(
            invalid_steps=invalid_steps,
            valid_steps=[f"Finite search found: {', '.join(str(item) for item in valid_solutions)}"],
            failed_candidates=[str(item) for item in unexpected_candidates],
            passed_candidates=[str(item) for item in sorted(candidate_set & valid_set)],
            missing_candidates=[str(item) for item in missing_candidates],
            reasoning="Bounded integer search disproved completeness or found invalid explicit candidates.",
        ).to_dict()
    if candidates:
        return _result_from_valid(
            valid_steps=[f"Finite search confirmed: {', '.join(str(item) for item in valid_solutions)}"],
            passed_candidates=[str(item) for item in valid_solutions],
            reasoning="Bounded integer search confirms the explicit candidate set for this finite case.",
        ).to_dict()
    return None


def merge_verification_results(results: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not results:
        return None
    invalid_results = [result for result in results if result["verdict"] == "INVALID"]
    if invalid_results:
        invalid_steps: list[str] = []
        valid_steps: list[str] = []
        failed_candidates: list[str] = []
        passed_candidates: list[str] = []
        missing_candidates: list[str] = []
        constraint_failures: list[str] = []
        reasoning_parts: list[str] = []
        for result in invalid_results:
            invalid_steps.extend(result.get("invalid_steps", []))
            valid_steps.extend(result.get("valid_steps", []))
            failed_candidates.extend(result.get("failed_candidates", []))
            passed_candidates.extend(result.get("passed_candidates", []))
            missing_candidates.extend(result.get("missing_candidates", []))
            constraint_failures.extend(result.get("constraint_failures", []))
            if result.get("reasoning"):
                reasoning_parts.append(str(result["reasoning"]))
        return _result_from_invalid(
            invalid_steps=invalid_steps,
            valid_steps=valid_steps,
            failed_candidates=failed_candidates,
            passed_candidates=passed_candidates,
            missing_candidates=missing_candidates,
            constraint_failures=constraint_failures,
            reasoning=" ".join(reasoning_parts) or "Deterministic verification found contradictions.",
        ).to_dict()
    valid = next((result for result in results if result["verdict"] == "VALID"), None)
    if valid is not None:
        return valid
    return results[0]


def verify_final_answer(*, problem: str, answer_text: str) -> dict[str, Any] | None:
    results = [
        result
        for result in [
            verify_explicit_candidates(problem, answer_text),
            verify_egyptian_fraction_finite_case(problem, answer_text),
        ]
        if result is not None
    ]
    return merge_verification_results(results)

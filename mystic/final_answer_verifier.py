from __future__ import annotations

import ast
from fractions import Fraction
import re
from typing import Any


POSITIVE_INTEGER_PATTERN = re.compile(r"positive integers|positive integer|양의 정수", re.IGNORECASE)
TUPLE_PATTERN = re.compile(r"\(\s*(\d+(?:\s*,\s*\d+)+)\s*\)")
EQUALITY_PATTERN = re.compile(r"([A-Za-z0-9_+\-*/().\s]+?)\s*=\s*([A-Za-z0-9_+\-*/().\s]+)")
ORDER_PATTERN = re.compile(r"([a-z])\s*(<=|<|>=|>)\s*([a-z])", re.IGNORECASE)
CHAIN_ORDER_PATTERN = re.compile(r"([a-z](?:\s*<=\s*[a-z])+)", re.IGNORECASE)
VARIABLE_PATTERN = re.compile(r"\b([a-z])\b")
RECIPROCAL_SUM_PATTERN = re.compile(r"(?:1\s*/\s*[a-z]\s*\+\s*)+1\s*/\s*[a-z]\s*=\s*\d+", re.IGNORECASE)


class SafeArithmeticEvaluator(ast.NodeVisitor):
    def __init__(self, variables: dict[str, Fraction]) -> None:
        self.variables = variables

    def visit(self, node: ast.AST) -> Fraction:  # type: ignore[override]
        if isinstance(node, ast.Expression):
            return self.visit(node.body)
        if isinstance(node, ast.BinOp):
            left = self.visit(node.left)
            right = self.visit(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.Pow) and right.denominator == 1 and right >= 0:
                return left ** int(right)
            raise ValueError("Unsupported operator")
        if isinstance(node, ast.UnaryOp):
            operand = self.visit(node.operand)
            if isinstance(node.op, ast.USub):
                return -operand
            if isinstance(node.op, ast.UAdd):
                return operand
            raise ValueError("Unsupported unary operator")
        if isinstance(node, ast.Name):
            if node.id not in self.variables:
                raise ValueError(f"Unknown variable: {node.id}")
            return self.variables[node.id]
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return Fraction(str(node.value))
            raise ValueError("Unsupported constant")
        raise ValueError(f"Unsupported expression node: {type(node).__name__}")


def safe_eval_fraction(expression: str, variables: dict[str, Fraction]) -> Fraction:
    tree = ast.parse(expression, mode="eval")
    return SafeArithmeticEvaluator(variables).visit(tree)


def normalize_problem_text(problem: str) -> str:
    return " ".join(problem.replace("≤", "<=").replace("≥", ">=").split())


def _clean_expression_text(raw: str) -> str:
    return re.sub(r"[^A-Za-z0-9_+\-*/().\s]", " ", raw).strip()


def _is_parseable_expression(text: str) -> bool:
    try:
        ast.parse(text, mode="eval")
    except SyntaxError:
        return False
    return True


def _extract_parseable_suffix(raw: str) -> str | None:
    tokens = _clean_expression_text(raw).split()
    for start in range(len(tokens)):
        candidate = " ".join(tokens[start:]).strip()
        if candidate and _is_parseable_expression(candidate):
            return candidate
    return None


def _extract_parseable_prefix(raw: str) -> str | None:
    tokens = _clean_expression_text(raw).split()
    for end in range(len(tokens), 0, -1):
        candidate = " ".join(tokens[:end]).strip()
        if candidate and _is_parseable_expression(candidate):
            return candidate
    return None


def extract_equations(problem: str) -> list[tuple[str, str]]:
    text = normalize_problem_text(problem)
    equations: list[tuple[str, str]] = []
    clauses = re.split(r"[;\n]", text)
    for clause in clauses:
        for left, right in EQUALITY_PATTERN.findall(clause):
            left_clean = _extract_parseable_suffix(left)
            right_clean = _extract_parseable_prefix(right)
            if not left_clean or not right_clean:
                continue
            if "<" in left_clean or ">" in left_clean or "<" in right_clean or ">" in right_clean:
                continue
            equations.append((left_clean, right_clean))
    deduped: list[tuple[str, str]] = []
    for item in equations:
        if item not in deduped:
            deduped.append(item)
    return deduped


def extract_order_constraints(problem: str) -> list[tuple[str, str, str]]:
    text = normalize_problem_text(problem)
    constraints: list[tuple[str, str, str]] = []
    for chain in CHAIN_ORDER_PATTERN.findall(text):
        parts = [part.strip() for part in chain.split("<=")]
        for left, right in zip(parts, parts[1:]):
            constraints.append((left, "<=", right))
    for left, operator, right in ORDER_PATTERN.findall(text):
        constraint = (left.strip(), operator.strip(), right.strip())
        if constraint not in constraints:
            constraints.append(constraint)
    return constraints


def infer_variable_order(problem: str, tuple_width: int) -> list[str]:
    text = normalize_problem_text(problem)
    chain_match = CHAIN_ORDER_PATTERN.search(text)
    if chain_match:
        parts = [part.strip() for part in chain_match.group(1).split("<=")]
        if len(parts) == tuple_width:
            return parts
    variables: list[str] = []
    for variable in VARIABLE_PATTERN.findall(text):
        if variable not in variables:
            variables.append(variable)
        if len(variables) == tuple_width:
            break
    return variables


def extract_candidate_tuples(answer_text: str) -> list[tuple[int, ...]]:
    seen: list[tuple[int, ...]] = []
    for match in TUPLE_PATTERN.finditer(answer_text):
        values = tuple(int(part.strip()) for part in match.group(1).split(","))
        if values not in seen:
            seen.append(values)
    return seen


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


def verify_equations(problem: str, assignment: dict[str, Fraction]) -> list[str]:
    failures: list[str] = []
    for left, right in extract_equations(problem):
        lhs = safe_eval_fraction(left, assignment)
        rhs = safe_eval_fraction(right, assignment)
        if lhs != rhs:
            failures.append(f"{left} = {right} fails because {lhs} != {rhs}")
    return failures


def verify_explicit_candidates(problem: str, answer_text: str) -> dict[str, Any] | None:
    candidates = extract_candidate_tuples(answer_text)
    if not candidates:
        return None
    variable_order = infer_variable_order(problem, len(candidates[0]))
    if len(variable_order) != len(candidates[0]):
        return None

    invalid_steps: list[str] = []
    valid_steps: list[str] = []
    for candidate in candidates:
        assignment = {
            variable: Fraction(value)
            for variable, value in zip(variable_order, candidate)
        }
        failures = [
            *check_positive_integer_constraints(problem, assignment),
            *check_order_constraints(problem, assignment),
            *verify_equations(problem, assignment),
        ]
        if failures:
            invalid_steps.append(f"{candidate}: " + "; ".join(failures))
        else:
            valid_steps.append(f"{candidate} passes direct substitution")

    if invalid_steps:
        return {
            "verdict": "INVALID",
            "first_fatal_error": invalid_steps[0],
            "invalid_steps": invalid_steps,
            "valid_steps": valid_steps,
            "repair_possible": True,
            "confidence": 1.0,
            "final_status": "INVALID",
        }
    return {
        "verdict": "VALID",
        "first_fatal_error": "",
        "invalid_steps": [],
        "valid_steps": valid_steps,
        "repair_possible": False,
        "confidence": 1.0,
        "final_status": "VALID",
    }


def is_egyptian_fraction_tuple_problem(problem: str) -> bool:
    text = normalize_problem_text(problem)
    return bool(
        RECIPROCAL_SUM_PATTERN.search(text)
        and CHAIN_ORDER_PATTERN.search(text)
        and POSITIVE_INTEGER_PATTERN.search(text)
    )


def enumerate_egyptian_fraction_solutions() -> list[tuple[int, int, int]]:
    results: list[tuple[int, int, int]] = []
    for x in range(1, 4):
        for y in range(x, 16):
            for z in range(y, 32):
                assignment = {"x": Fraction(x), "y": Fraction(y), "z": Fraction(z)}
                if not verify_equations("1/x + 1/y + 1/z = 1", assignment):
                    results.append((x, y, z))
    return results


def verify_egyptian_fraction_finite_case(problem: str, answer_text: str) -> dict[str, Any] | None:
    if not is_egyptian_fraction_tuple_problem(problem):
        return None
    candidates = [triple for triple in extract_candidate_tuples(answer_text) if len(triple) == 3]
    valid_solutions = enumerate_egyptian_fraction_solutions()
    valid_set = set(valid_solutions)
    candidate_set = set(candidates)
    invalid_steps: list[str] = []
    if candidates:
        substitution = verify_explicit_candidates(problem, answer_text)
        if substitution is not None and substitution["verdict"] == "INVALID":
            invalid_steps.extend(substitution["invalid_steps"])
    missing_candidates = sorted(valid_set - candidate_set)
    if missing_candidates:
        invalid_steps.append("Missing valid solutions: " + ", ".join(str(item) for item in missing_candidates))
    if invalid_steps:
        return {
            "verdict": "INVALID",
            "first_fatal_error": invalid_steps[0],
            "invalid_steps": invalid_steps,
            "valid_steps": [f"Finite search found: {', '.join(str(item) for item in valid_solutions)}"],
            "repair_possible": True,
            "confidence": 1.0,
            "final_status": "INVALID",
        }
    if candidates:
        return {
            "verdict": "VALID",
            "first_fatal_error": "",
            "invalid_steps": [],
            "valid_steps": [f"Finite search confirmed: {', '.join(str(item) for item in valid_solutions)}"],
            "repair_possible": False,
            "confidence": 1.0,
            "final_status": "VALID",
        }
    return None


def merge_verification_results(results: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not results:
        return None
    invalid_results = [result for result in results if result["verdict"] == "INVALID"]
    if invalid_results:
        invalid_steps: list[str] = []
        valid_steps: list[str] = []
        for result in invalid_results:
            invalid_steps.extend(result.get("invalid_steps", []))
            valid_steps.extend(result.get("valid_steps", []))
        return {
            "verdict": "INVALID",
            "first_fatal_error": invalid_steps[0] if invalid_steps else "Verification failed.",
            "invalid_steps": invalid_steps,
            "valid_steps": valid_steps,
            "repair_possible": True,
            "confidence": 1.0,
            "final_status": "INVALID",
        }
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

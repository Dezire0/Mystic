from __future__ import annotations

import ast
import re


POSITIVE_INTEGER_PATTERN = re.compile(r"positive integers|positive integer|양의 정수", re.IGNORECASE)
TUPLE_PATTERN = re.compile(r"\(\s*(\d+(?:\s*,\s*\d+)+)\s*\)")
EQUALITY_PATTERN = re.compile(r"([A-Za-z0-9_+\-*/().\s]+?)\s*=\s*([A-Za-z0-9_+\-*/().\s]+)")
ORDER_PATTERN = re.compile(r"([a-z])\s*(<=|<|>=|>)\s*([a-z])", re.IGNORECASE)
CHAIN_ORDER_PATTERN = re.compile(r"([a-z](?:\s*<=\s*[a-z])+)", re.IGNORECASE)
VARIABLE_PATTERN = re.compile(r"\b([a-z])\b")
RECIPROCAL_SUM_PATTERN = re.compile(r"(?:1\s*/\s*[a-z]\s*\+\s*)+1\s*/\s*[a-z]\s*=\s*\d+", re.IGNORECASE)


def normalize_problem_text(problem: str) -> str:
    return " ".join(problem.replace("≤", "<=").replace("≥", ">=").split())


def clean_expression_text(raw: str) -> str:
    return re.sub(r"[^A-Za-z0-9_+\-*/().\s]", " ", raw).strip()


def is_parseable_expression(text: str) -> bool:
    try:
        ast.parse(text, mode="eval")
    except SyntaxError:
        return False
    return True


def extract_parseable_suffix(raw: str) -> str | None:
    tokens = clean_expression_text(raw).split()
    for start in range(len(tokens)):
        candidate = " ".join(tokens[start:]).strip()
        if candidate and is_parseable_expression(candidate):
            return candidate
    return None


def extract_parseable_prefix(raw: str) -> str | None:
    tokens = clean_expression_text(raw).split()
    for end in range(len(tokens), 0, -1):
        candidate = " ".join(tokens[:end]).strip()
        if candidate and is_parseable_expression(candidate):
            return candidate
    return None


def extract_equations(problem: str) -> list[tuple[str, str]]:
    text = normalize_problem_text(problem)
    equations: list[tuple[str, str]] = []
    clauses = re.split(r"[;\n]", text)
    for clause in clauses:
        for left, right in EQUALITY_PATTERN.findall(clause):
            left_clean = extract_parseable_suffix(left)
            right_clean = extract_parseable_prefix(right)
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


def variables_in_expression(expression: str) -> set[str]:
    return {match for match in VARIABLE_PATTERN.findall(expression)}


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


def is_egyptian_fraction_tuple_problem(problem: str) -> bool:
    text = normalize_problem_text(problem)
    return bool(
        RECIPROCAL_SUM_PATTERN.search(text)
        and CHAIN_ORDER_PATTERN.search(text)
        and POSITIVE_INTEGER_PATTERN.search(text)
    )

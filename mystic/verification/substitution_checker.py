from __future__ import annotations

import ast
from fractions import Fraction

from mystic.verification.candidate_extractor import extract_equations, variables_in_expression


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


def verify_equations(problem: str, assignment: dict[str, Fraction]) -> list[str]:
    failures: list[str] = []
    for left, right in extract_equations(problem):
        expression_variables = variables_in_expression(left) | variables_in_expression(right)
        if not expression_variables.issubset(set(assignment)):
            continue
        try:
            lhs = safe_eval_fraction(left, assignment)
            rhs = safe_eval_fraction(right, assignment)
        except (ValueError, ZeroDivisionError):
            continue
        if lhs != rhs:
            failures.append(f"{left} = {right} fails because {lhs} != {rhs}")
    return failures

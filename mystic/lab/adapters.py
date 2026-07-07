from __future__ import annotations

import ast
import math
from typing import Any

from mystic.lab.scene import LabSceneBundle, LabSceneObject, LabSimulation, normalize_vector

try:
    import sympy as _sympy  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - optional dependency
    _sympy = None


def engine_required(adapter_id: str, message: str, **extra: Any) -> dict[str, Any]:
    payload = {
        "status": "engine_required",
        "adapter_id": adapter_id,
        "message": message,
        "supported_in_worker": adapter_id != "math.sympy",
    }
    payload.update(extra)
    return payload


def unsupported_expression(adapter_id: str, message: str, **extra: Any) -> dict[str, Any]:
    payload = {
        "status": "unsupported_expression",
        "adapter_id": adapter_id,
        "message": message,
        "supported_in_worker": True,
    }
    payload.update(extra)
    return payload


def deferred(adapter_id: str, message: str, **extra: Any) -> dict[str, Any]:
    payload = {
        "status": "deferred",
        "adapter_id": adapter_id,
        "message": message,
    }
    payload.update(extra)
    return payload


def completed(adapter_id: str, *, inputs: dict[str, Any], outputs: dict[str, Any], evidence: dict[str, Any], warnings: list[str] | None = None) -> dict[str, Any]:
    return {
        "status": "completed",
        "adapter_id": adapter_id,
        "inputs": inputs,
        "outputs": outputs,
        "evidence": evidence,
        "warnings": warnings or [],
        "errors": [],
    }


def execute_adapter(adapter_id: str, scene_bundle: LabSceneBundle, inputs: dict[str, Any]) -> dict[str, Any]:
    if adapter_id == "math.sympy":
        return run_math_sympy(inputs)
    if adapter_id == "physics.simple_projectile":
        return run_simple_projectile(scene_bundle, inputs)
    if adapter_id == "physics.simple_collision":
        return run_simple_collision(scene_bundle, inputs)
    return engine_required(adapter_id, "The requested adapter is not registered in Mystic LAB Phase 1.")


def export_scene(adapter_id: str, scene_bundle: LabSceneBundle, *, include_simulations: bool) -> dict[str, Any]:
    if adapter_id != "scene.three_json":
        return engine_required(adapter_id, "This scene export adapter is unavailable in Mystic LAB Phase 1.")
    snapshot = {
        "metadata": {
            "adapter_id": adapter_id,
            "type": "MysticLABScene",
            "version": 1,
        },
        "scene": {
            "uuid": scene_bundle.scene.scene_id,
            "name": scene_bundle.scene.title,
            "type": "Scene",
            "userData": {
                "session_id": scene_bundle.scene.session_id,
                "domain": scene_bundle.scene.domain,
                "description": scene_bundle.scene.description,
                "parameters": scene_bundle.scene.parameters,
                "units": scene_bundle.scene.units,
                "attached_simulations": list(scene_bundle.scene.attached_simulations),
                "metadata": scene_bundle.scene.metadata,
            },
        },
        "objects": [
            {
                "uuid": item.id,
                "name": item.label,
                "type": item.type,
                "position": [item.position["x"], item.position["y"], item.position["z"]],
                "rotation": [item.rotation["x"], item.rotation["y"], item.rotation["z"]],
                "scale": [item.scale["x"], item.scale["y"], item.scale["z"]],
                "geometry": item.geometry,
                "material": item.material,
                "userData": {
                    "data": item.data,
                    "metadata": item.metadata,
                },
            }
            for item in scene_bundle.objects
        ],
    }
    if include_simulations:
        snapshot["simulations"] = [
            {
                "simulation_id": item.simulation_id,
                "adapter_id": item.adapter_id,
                "status": item.status,
                "attached_object_ids": list(item.attached_object_ids),
                "outputs": item.outputs,
            }
            for item in scene_bundle.simulations
        ]
    return completed(
        adapter_id,
        inputs={"include_simulations": include_simulations},
        outputs={"snapshot": snapshot},
        evidence={"scene_id": scene_bundle.scene.scene_id, "object_count": len(scene_bundle.objects)},
    )


def render_scene_report(scene_bundle: LabSceneBundle) -> str:
    object_lines = [
        f"- {item.label} ({item.type}) @ ({item.position['x']:.3f}, {item.position['y']:.3f}, {item.position['z']:.3f})"
        for item in scene_bundle.objects
    ] or ["- None"]
    simulation_lines = [
        f"- {item.simulation_id} [{item.adapter_id}] => {item.status}"
        for item in scene_bundle.simulations
    ] or ["- None"]
    evidence_lines = [f"- {item}" for item in scene_bundle.scene.evidence_refs] or ["- None"]
    parameter_lines = [
        f"- {key}: {value}"
        for key, value in sorted(scene_bundle.scene.parameters.items())
    ] or ["- None"]
    report_lines = [
        f"# Mystic LAB Scene Report: {scene_bundle.scene.title}",
        "",
        f"Scene ID: {scene_bundle.scene.scene_id}",
        f"Session ID: {scene_bundle.scene.session_id}",
        f"Domain: {scene_bundle.scene.domain}",
        "",
        "## Description",
        scene_bundle.scene.description or "No description.",
        "",
        "## Parameters",
        *parameter_lines,
        "",
        "## Objects",
        *object_lines,
        "",
        "## Simulations",
        *simulation_lines,
        "",
        "## Evidence Refs",
        *evidence_lines,
        "",
    ]
    return "\n".join(report_lines)


def apply_simulation_to_scene(scene_bundle: LabSceneBundle, simulation: LabSimulation, object_ids: list[str]) -> None:
    selected = [item for item in scene_bundle.objects if item.id in object_ids] if object_ids else scene_bundle.objects
    if simulation.adapter_id == "physics.simple_projectile":
        target_object_id = str(simulation.outputs.get("object_id", "")).strip()
        target = next((item for item in selected if item.id == target_object_id), None)
        if target is None:
            return
        final_position = normalize_vector(simulation.outputs.get("final_position"), default=(0.0, 0.0, 0.0))
        final_velocity = normalize_vector(simulation.outputs.get("final_velocity"), default=(0.0, 0.0, 0.0))
        target.position = final_position
        target.data["velocity"] = final_velocity
        target.data["trajectory"] = simulation.outputs.get("trajectory", [])
        target.metadata["last_simulation_id"] = simulation.simulation_id
        target.touch()
        return
    if simulation.adapter_id == "physics.simple_collision":
        updated = simulation.outputs.get("post_collision", {})
        if not isinstance(updated, dict):
            return
        for target in selected:
            velocity = updated.get(target.id)
            if not isinstance(velocity, dict):
                continue
            target.data["velocity"] = normalize_vector(velocity, default=(0.0, 0.0, 0.0))
            target.metadata["last_simulation_id"] = simulation.simulation_id
            target.touch()


def run_math_sympy(inputs: dict[str, Any]) -> dict[str, Any]:
    operation = str(inputs.get("operation", "evaluate")).strip() or "evaluate"
    warnings = ["sympy_not_installed_using_native_subset"]
    try:
        if _sympy is not None:
            return _run_math_with_sympy(operation, inputs)
        if operation == "evaluate":
            expression = str(inputs.get("expression", "")).strip()
            if not expression:
                return engine_required("math.sympy", "expression is required for math.sympy evaluate")
            variables = _numeric_variables(inputs.get("variables"))
            result = _evaluate_numeric_expression(expression, variables)
            return completed(
                "math.sympy",
                inputs=inputs,
                outputs={"operation": operation, "result": result},
                evidence={"implementation": "native_subset", "grammar": "arithmetic_v1"},
                warnings=warnings,
            )
        if operation == "substitute":
            expression = str(inputs.get("expression", "")).strip()
            if not expression:
                return engine_required("math.sympy", "expression is required for math.sympy substitute")
            variables = _numeric_variables(inputs.get("variables"))
            substituted = _substitute_math_expression(_parse_math_expression(expression), variables)
            simplified = _simplify_math_expression(substituted)
            remaining = sorted(_expression_symbols(simplified))
            outputs: dict[str, Any] = {
                "operation": operation,
                "expression": _format_math_expression(simplified),
                "remaining_variables": remaining,
            }
            if not remaining:
                outputs["result"] = _evaluate_numeric_node(simplified)
            return completed(
                "math.sympy",
                inputs=inputs,
                outputs=outputs,
                evidence={"implementation": "native_subset", "grammar": "arithmetic_v1"},
                warnings=warnings,
            )
        if operation == "simplify":
            expression = str(inputs.get("expression", "")).strip()
            if not expression:
                return engine_required("math.sympy", "expression is required for math.sympy simplify")
            simplified = _simplify_math_expression(_parse_math_expression(expression))
            return completed(
                "math.sympy",
                inputs=inputs,
                outputs={"operation": operation, "result": _format_math_expression(simplified)},
                evidence={"implementation": "native_subset", "grammar": "arithmetic_v1"},
                warnings=warnings,
            )
        if operation == "solve_linear":
            equation = str(inputs.get("equation", "")).strip()
            variable = str(inputs.get("variable", "x")).strip() or "x"
            if not equation or "=" not in equation:
                return engine_required("math.sympy", "solve_linear requires an equation string containing '='")
            solution = _solve_linear_equation(equation, variable, _numeric_variables(inputs.get("variables")))
            return completed(
                "math.sympy",
                inputs=inputs,
                outputs={"operation": operation, "variable": variable, "solution": solution},
                evidence={"implementation": "native_subset", "grammar": "arithmetic_v1"},
                warnings=warnings,
            )
        return engine_required(
            "math.sympy",
            f"operation={operation} requires a fuller sympy installation than the current environment provides.",
        )
    except (SyntaxError, ValueError, ZeroDivisionError) as exc:
        return unsupported_expression("math.sympy", str(exc), operation=operation)


def _run_math_with_sympy(operation: str, inputs: dict[str, Any]) -> dict[str, Any]:
    expression = str(inputs.get("expression", "")).strip()
    normalized_expression = _normalize_math_expression(expression)
    variables = _numeric_variables(inputs.get("variables"))
    if operation == "evaluate":
        result = _sympy.sympify(normalized_expression).evalf(subs=variables)  # type: ignore[union-attr]
        return completed(
            "math.sympy",
            inputs=inputs,
            outputs={"operation": operation, "result": float(result)},
            evidence={"implementation": "sympy"},
        )
    if operation == "solve_linear":
        equation = str(inputs.get("equation", "")).strip()
        variable_name = str(inputs.get("variable", "x")).strip() or "x"
        lhs, rhs = [_normalize_math_expression(item.strip()) for item in equation.split("=", 1)]
        symbol = _sympy.Symbol(variable_name)  # type: ignore[union-attr]
        solved = _sympy.solve(_sympy.Eq(_sympy.sympify(lhs), _sympy.sympify(rhs)), symbol)  # type: ignore[union-attr]
        if not solved:
            raise ValueError("No solution found")
        return completed(
            "math.sympy",
            inputs=inputs,
            outputs={"operation": operation, "variable": variable_name, "solution": float(solved[0])},
            evidence={"implementation": "sympy"},
        )
    if operation == "simplify":
        result = str(_sympy.simplify(normalized_expression))  # type: ignore[union-attr]
        return completed(
            "math.sympy",
            inputs=inputs,
            outputs={"operation": operation, "result": result},
            evidence={"implementation": "sympy"},
        )
    if operation == "substitute":
        result = _sympy.sympify(normalized_expression).subs(variables)  # type: ignore[union-attr]
        outputs: dict[str, Any] = {"operation": operation, "expression": str(result)}
        if not getattr(result, "free_symbols", set()):
            outputs["result"] = float(result.evalf())
        return completed(
            "math.sympy",
            inputs=inputs,
            outputs=outputs,
            evidence={"implementation": "sympy"},
        )
    return engine_required("math.sympy", f"Unsupported math.sympy operation: {operation}")


def _numeric_variables(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    return {str(key): _coerce_float(item) for key, item in value.items()}


def _coerce_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return float(default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _evaluate_numeric_expression(expression: str, variables: dict[str, float]) -> float:
    node = _substitute_math_expression(_parse_math_expression(expression), variables)
    simplified = _simplify_math_expression(node)
    remaining = sorted(_expression_symbols(simplified))
    if remaining:
        joined = ", ".join(remaining)
        raise ValueError(f"evaluate requires numeric values for all variables; unresolved: {joined}")
    return float(_evaluate_numeric_node(simplified))


def _eval_expr_node(node: ast.AST, variables: dict[str, float]) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id not in variables:
            raise ValueError(f"Unknown variable: {node.id}")
        return float(variables[node.id])
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_eval_expr_node(node.operand, variables)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd):
        return _eval_expr_node(node.operand, variables)
    if isinstance(node, ast.BinOp):
        left = _eval_expr_node(node.left, variables)
        right = _eval_expr_node(node.right, variables)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Pow):
            return left**right
    raise ValueError("Unsupported expression for math.sympy native subset")


def _solve_linear_equation(equation: str, variable: str, variables: dict[str, float]) -> float:
    lhs_text, rhs_text = [item.strip() for item in equation.split("=", 1)]
    lhs_coef, lhs_const = _linear_form(_parse_math_expression(lhs_text), variable, variables)
    rhs_coef, rhs_const = _linear_form(_parse_math_expression(rhs_text), variable, variables)
    coefficient = lhs_coef - rhs_coef
    constant = rhs_const - lhs_const
    if abs(coefficient) < 1e-12:
        raise ValueError("Equation is not solvable as a single-variable linear form")
    return constant / coefficient


def _linear_form(node: ast.AST, variable: str, variables: dict[str, float]) -> tuple[float, float]:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return 0.0, float(node.value)
    if isinstance(node, ast.Name):
        if node.id == variable:
            return 1.0, 0.0
        if node.id in variables:
            return 0.0, float(variables[node.id])
        raise ValueError(f"Unknown variable: {node.id}")
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        coef, const = _linear_form(node.operand, variable, variables)
        return -coef, -const
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd):
        return _linear_form(node.operand, variable, variables)
    if isinstance(node, ast.BinOp):
        left = _linear_form(node.left, variable, variables)
        right = _linear_form(node.right, variable, variables)
        if isinstance(node.op, ast.Add):
            return left[0] + right[0], left[1] + right[1]
        if isinstance(node.op, ast.Sub):
            return left[0] - right[0], left[1] - right[1]
        if isinstance(node.op, ast.Mult):
            if left[0] and right[0]:
                raise ValueError("Non-linear multiplication is unsupported")
            if left[0]:
                return left[0] * right[1], left[1] * right[1]
            if right[0]:
                return right[0] * left[1], right[1] * left[1]
            return 0.0, left[1] * right[1]
        if isinstance(node.op, ast.Div):
            if right[0]:
                raise ValueError("Division by a symbolic term is unsupported")
            return left[0] / right[1], left[1] / right[1]
        if isinstance(node.op, ast.Pow):
            if left[0] or right[0]:
                raise ValueError("Symbolic powers are unsupported")
            return 0.0, left[1] ** right[1]
    raise ValueError("Unsupported expression for solve_linear native subset")


def _normalize_math_expression(expression: str) -> str:
    return str(expression).replace("^", "**")


def _parse_math_expression(expression: str) -> ast.AST:
    return ast.parse(_normalize_math_expression(expression), mode="eval").body


def _number_node(value: float) -> ast.Constant:
    if abs(value) <= 1e-12:
        value = 0.0
    if abs(value - round(value)) <= 1e-12:
        value = float(round(value))
    return ast.Constant(value=value)


def _is_number_node(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, (int, float))


def _number_value(node: ast.AST) -> float:
    if not _is_number_node(node):
        raise ValueError("Expected a numeric node")
    return float(node.value)


def _is_zero_node(node: ast.AST) -> bool:
    return _is_number_node(node) and abs(_number_value(node)) <= 1e-12


def _is_one_node(node: ast.AST) -> bool:
    return _is_number_node(node) and abs(_number_value(node) - 1.0) <= 1e-12


def _substitute_math_expression(node: ast.AST, variables: dict[str, float]) -> ast.AST:
    if _is_number_node(node):
        return _number_node(_number_value(node))
    if isinstance(node, ast.Name):
        if node.id in variables:
            return _number_node(float(variables[node.id]))
        return ast.Name(id=node.id, ctx=ast.Load())
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        return ast.UnaryOp(op=node.op, operand=_substitute_math_expression(node.operand, variables))
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)):
        return ast.BinOp(
            left=_substitute_math_expression(node.left, variables),
            op=node.op,
            right=_substitute_math_expression(node.right, variables),
        )
    raise ValueError("Unsupported expression for math.sympy native subset")


def _simplify_math_expression(node: ast.AST) -> ast.AST:
    if _is_number_node(node):
        return _number_node(_number_value(node))
    if isinstance(node, ast.Name):
        return ast.Name(id=node.id, ctx=ast.Load())
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd):
        return _simplify_math_expression(node.operand)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        operand = _simplify_math_expression(node.operand)
        if _is_number_node(operand):
            return _number_node(-_number_value(operand))
        return ast.UnaryOp(op=ast.USub(), operand=operand)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)):
        left = _simplify_math_expression(node.left)
        right = _simplify_math_expression(node.right)
        if _is_number_node(left) and _is_number_node(right):
            return _number_node(_evaluate_numeric_node(ast.BinOp(left=left, op=node.op, right=right)))
        if isinstance(node.op, ast.Add):
            if _is_zero_node(left):
                return right
            if _is_zero_node(right):
                return left
        if isinstance(node.op, ast.Sub):
            if _is_zero_node(right):
                return left
        if isinstance(node.op, ast.Mult):
            if _is_zero_node(left) or _is_zero_node(right):
                return _number_node(0.0)
            if _is_one_node(left):
                return right
            if _is_one_node(right):
                return left
        if isinstance(node.op, ast.Div):
            if _is_zero_node(left) and _is_number_node(right) and abs(_number_value(right)) > 1e-12:
                return _number_node(0.0)
            if _is_one_node(right):
                return left
        if isinstance(node.op, ast.Pow):
            if _is_zero_node(right):
                return _number_node(1.0)
            if _is_one_node(right):
                return left
            if _is_one_node(left):
                return _number_node(1.0)
            if _is_zero_node(left) and _is_number_node(right) and _number_value(right) > 0.0:
                return _number_node(0.0)
        return ast.BinOp(left=left, op=node.op, right=right)
    raise ValueError("Unsupported expression for math.sympy native subset")


def _evaluate_numeric_node(node: ast.AST) -> float:
    if _is_number_node(node):
        return _number_value(node)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_evaluate_numeric_node(node.operand)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd):
        return _evaluate_numeric_node(node.operand)
    if isinstance(node, ast.BinOp):
        left = _evaluate_numeric_node(node.left)
        right = _evaluate_numeric_node(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Pow):
            return left**right
    raise ValueError("Unsupported expression for math.sympy native subset")


def _expression_symbols(node: ast.AST) -> set[str]:
    if _is_number_node(node):
        return set()
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        return _expression_symbols(node.operand)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)):
        return _expression_symbols(node.left) | _expression_symbols(node.right)
    raise ValueError("Unsupported expression for math.sympy native subset")


def _format_math_expression(node: ast.AST, *, parent_precedence: int = -1, right_child: bool = False) -> str:
    if _is_number_node(node):
        value = _number_value(node)
        if abs(value - round(value)) <= 1e-12:
            return str(int(round(value)))
        return format(value, ".12g")
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        operator = "+" if isinstance(node.op, ast.UAdd) else "-"
        text = f"{operator}{_format_math_expression(node.operand, parent_precedence=3)}"
        return f"({text})" if 3 < parent_precedence else text
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)):
        operator, precedence = _math_operator_text(node.op)
        right_precedence = precedence if operator == "^" and right_child else precedence + (0 if operator == "^" else 1)
        left_text = _format_math_expression(node.left, parent_precedence=precedence)
        right_text = _format_math_expression(node.right, parent_precedence=right_precedence, right_child=True)
        text = f"{left_text} {operator} {right_text}"
        return f"({text})" if precedence < parent_precedence else text
    raise ValueError("Unsupported expression for math.sympy native subset")


def _math_operator_text(operator: ast.operator) -> tuple[str, int]:
    if isinstance(operator, (ast.Add, ast.Sub)):
        return ("+" if isinstance(operator, ast.Add) else "-"), 1
    if isinstance(operator, (ast.Mult, ast.Div)):
        return ("*" if isinstance(operator, ast.Mult) else "/"), 2
    if isinstance(operator, ast.Pow):
        return "^", 3
    raise ValueError("Unsupported expression for math.sympy native subset")


def run_simple_projectile(scene_bundle: LabSceneBundle, inputs: dict[str, Any]) -> dict[str, Any]:
    object_id = str(inputs.get("object_id", "")).strip()
    obj = _find_object(scene_bundle, object_id)
    initial_position = normalize_vector(
        inputs.get("initial_position") if isinstance(inputs.get("initial_position"), dict) else (obj.position if obj else {}),
        default=(0.0, 0.0, 0.0),
    )
    initial_velocity = normalize_vector(
        inputs.get("initial_velocity") if isinstance(inputs.get("initial_velocity"), dict) else ((obj.data.get("velocity") if obj else {}) or {}),
        default=(0.0, 0.0, 0.0),
    )
    gravity = _gravity_vector(inputs.get("gravity"), scene_bundle.scene.parameters.get("gravity"))
    duration = max(_coerce_float(inputs.get("duration"), 2.0), 0.0)
    time_step = max(_coerce_float(inputs.get("time_step"), 0.1), 0.01)
    ground_y = _coerce_float(inputs.get("ground_y"), 0.0)
    stop_on_ground = bool(inputs.get("stop_on_ground", True))

    trajectory: list[dict[str, Any]] = []
    max_height = initial_position["y"]
    elapsed = 0.0
    while elapsed <= duration + 1e-9:
        position = {
            "x": initial_position["x"] + initial_velocity["x"] * elapsed + 0.5 * gravity["x"] * elapsed * elapsed,
            "y": initial_position["y"] + initial_velocity["y"] * elapsed + 0.5 * gravity["y"] * elapsed * elapsed,
            "z": initial_position["z"] + initial_velocity["z"] * elapsed + 0.5 * gravity["z"] * elapsed * elapsed,
        }
        velocity = {
            "x": initial_velocity["x"] + gravity["x"] * elapsed,
            "y": initial_velocity["y"] + gravity["y"] * elapsed,
            "z": initial_velocity["z"] + gravity["z"] * elapsed,
        }
        trajectory.append({"time": round(elapsed, 6), "position": position, "velocity": velocity})
        max_height = max(max_height, position["y"])
        if stop_on_ground and elapsed > 0 and position["y"] <= ground_y:
            break
        elapsed += time_step
    final_sample = trajectory[-1]
    return completed(
        "physics.simple_projectile",
        inputs=inputs,
        outputs={
            "object_id": object_id,
            "trajectory": trajectory,
            "final_position": final_sample["position"],
            "final_velocity": final_sample["velocity"],
            "max_height": max_height,
            "duration_used": final_sample["time"],
        },
        evidence={"equations": ["p = p0 + vt + 0.5at^2", "v = v0 + at"]},
    )


def run_simple_collision(scene_bundle: LabSceneBundle, inputs: dict[str, Any]) -> dict[str, Any]:
    object_ids = [
        str(item).strip()
        for item in inputs.get("object_ids", [])
        if str(item).strip()
    ]
    if len(object_ids) != 2:
        return engine_required("physics.simple_collision", "object_ids must contain exactly two scene object ids")
    object_a = _find_object(scene_bundle, object_ids[0])
    object_b = _find_object(scene_bundle, object_ids[1])
    if object_a is None or object_b is None:
        return engine_required("physics.simple_collision", "Both collision objects must exist in the scene before simulation")

    axis = _normalize_axis(inputs.get("axis"))
    mass_a = _coerce_float(inputs.get("mass_a", object_a.data.get("mass", 1.0)), 1.0)
    mass_b = _coerce_float(inputs.get("mass_b", object_b.data.get("mass", 1.0)), 1.0)
    restitution = min(max(_coerce_float(inputs.get("coefficient_of_restitution"), 1.0), 0.0), 1.0)
    velocity_a = normalize_vector(inputs.get("velocity_a") or object_a.data.get("velocity"), default=(0.0, 0.0, 0.0))
    velocity_b = normalize_vector(inputs.get("velocity_b") or object_b.data.get("velocity"), default=(0.0, 0.0, 0.0))

    scalar_a = _dot(velocity_a, axis)
    scalar_b = _dot(velocity_b, axis)
    post_a = ((mass_a * scalar_a) + (mass_b * scalar_b) - (mass_b * restitution * (scalar_a - scalar_b))) / (mass_a + mass_b)
    post_b = ((mass_a * scalar_a) + (mass_b * scalar_b) + (mass_a * restitution * (scalar_a - scalar_b))) / (mass_a + mass_b)

    updated_a = _replace_axis_component(velocity_a, axis, post_a)
    updated_b = _replace_axis_component(velocity_b, axis, post_b)
    outputs = {
        "axis": axis,
        "pre_collision": {
            object_a.id: velocity_a,
            object_b.id: velocity_b,
        },
        "post_collision": {
            object_a.id: updated_a,
            object_b.id: updated_b,
        },
        "momentum": {
            "before": mass_a * scalar_a + mass_b * scalar_b,
            "after": mass_a * post_a + mass_b * post_b,
        },
    }
    return completed(
        "physics.simple_collision",
        inputs=inputs,
        outputs=outputs,
        evidence={"equations": ["conservation_of_momentum", "coefficient_of_restitution"]},
    )


def _find_object(scene_bundle: LabSceneBundle, object_id: str) -> LabSceneObject | None:
    if not object_id:
        return scene_bundle.objects[0] if scene_bundle.objects else None
    for item in scene_bundle.objects:
        if item.id == object_id:
            return item
    return None


def _gravity_vector(primary: Any, fallback: Any) -> dict[str, float]:
    value = primary if primary is not None else fallback
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return {"x": 0.0, "y": -float(value), "z": 0.0}
    payload = normalize_vector(value, default=(0.0, -9.81, 0.0))
    if payload == {"x": 0.0, "y": 0.0, "z": 0.0}:
        return {"x": 0.0, "y": -9.81, "z": 0.0}
    return payload


def _normalize_axis(value: Any) -> dict[str, float]:
    vector = normalize_vector(value, default=(1.0, 0.0, 0.0))
    length = math.sqrt((vector["x"] ** 2) + (vector["y"] ** 2) + (vector["z"] ** 2))
    if length <= 1e-12:
        return {"x": 1.0, "y": 0.0, "z": 0.0}
    return {key: item / length for key, item in vector.items()}


def _dot(a: dict[str, float], b: dict[str, float]) -> float:
    return (a["x"] * b["x"]) + (a["y"] * b["y"]) + (a["z"] * b["z"])


def _replace_axis_component(velocity: dict[str, float], axis: dict[str, float], scalar: float) -> dict[str, float]:
    current_scalar = _dot(velocity, axis)
    delta = scalar - current_scalar
    return {
        "x": velocity["x"] + axis["x"] * delta,
        "y": velocity["y"] + axis["y"] * delta,
        "z": velocity["z"] + axis["z"] * delta,
    }

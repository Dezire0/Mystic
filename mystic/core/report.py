"""Report assembly helpers."""

from __future__ import annotations

from mystic.core.protocol import AgentOutput, CorePlan, PythonExecutionResult


def build_report(
    problem: str,
    core_plan: CorePlan,
    agent_outputs: list[AgentOutput],
    experiment_result: PythonExecutionResult | None,
    lean_summary: str,
    export_paths: list[str],
) -> str:
    lines = [
        "MYSTIC REPORT",
        "",
        f"Problem: {problem}",
        f"Restatement: {core_plan.problem_restatement}",
        f"Initial strategy: {core_plan.initial_strategy}",
        "",
        "Agent findings:",
    ]
    for output in agent_outputs:
        lines.append(f"- {output.agent}: {output.status} | {output.claim}")
    if experiment_result is not None:
        lines.extend(
            [
                "",
                "Forge experiment:",
                f"- success: {experiment_result.success}",
                f"- blocked: {experiment_result.blocked}",
                f"- stdout: {experiment_result.stdout.strip() or '(empty)'}",
                f"- stderr: {experiment_result.stderr.strip() or '(empty)'}",
            ]
        )
    if lean_summary:
        lines.extend(["", f"Lean: {lean_summary}"])
    if export_paths:
        lines.extend(["", "Dataset exports:"])
        lines.extend(f"- {path}" for path in export_paths)
    return "\n".join(lines)


"""Report synthesis agent."""

from __future__ import annotations

from mystic.agents.base import BaseAgent
from mystic.core.protocol import AgentOutput, CorePlan, PythonExecutionResult
from mystic.core.report import build_report


class ReportAgent(BaseAgent):
    agent_name = "report"
    division = "report"
    prompt_file = "report.md"
    default_status = "FORMALIZED"
    focus_areas = ["synthesis", "summary", "handoff"]
    must_check = ["claim status", "risk summary", "next steps"]

    def build(
        self,
        problem: str,
        core_plan: CorePlan,
        prior_outputs: list[AgentOutput],
        experiment_result: PythonExecutionResult | None,
        lean_summary: str,
        export_paths: list[str],
    ) -> tuple[AgentOutput, str]:
        output = self.run(problem, core_plan, prior_outputs)
        report_text = build_report(problem, core_plan, prior_outputs, experiment_result, lean_summary, export_paths)
        output.reasoning = report_text
        output.claim = "ReportAgent synthesized the current research state into a session report."
        output.next_move = "Escalate promising claims into deeper domain-specific iterations."
        return output, report_text


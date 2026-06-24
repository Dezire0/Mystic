"""Base agent primitives."""

from __future__ import annotations

from pathlib import Path

from mystic.core.model_registry import ModelRegistry
from mystic.core.protocol import AgentOutput, CorePlan


class BaseAgent:
    agent_name = "base"
    division = "core"
    prompt_file = "core.md"
    default_status = "PROMISING"
    focus_areas: list[str] = []
    must_check: list[str] = []

    def __init__(self, registry: ModelRegistry, root_path: str | Path) -> None:
        self.registry = registry
        self.root_path = Path(root_path)

    def run(
        self,
        problem: str,
        core_plan: CorePlan | None = None,
        prior_outputs: list[AgentOutput] | None = None,
    ) -> AgentOutput:
        prior_outputs = prior_outputs or []
        settings = self.registry.get_agent_settings(self.agent_name)
        provider = self.registry.get_provider(settings.provider)
        prompt = self._load_prompt()
        provider_response = provider.generate(self.agent_name, prompt, problem, settings)
        return AgentOutput(
            agent=self.agent_name,
            division=self.division,
            claim=self.make_claim(problem, core_plan, prior_outputs),
            status=self.make_status(problem, core_plan, prior_outputs),
            reasoning=self.make_reasoning(problem, core_plan, prior_outputs, provider_response.text),
            dependencies=self.make_dependencies(core_plan, prior_outputs),
            obstruction=self.make_obstruction(problem, core_plan, prior_outputs),
            experiment=self.make_experiment(problem, core_plan, prior_outputs),
            formalization=self.make_formalization(problem, core_plan, prior_outputs),
            next_move=self.make_next_move(problem, core_plan, prior_outputs),
            raw_response=provider_response.text,
            metadata={"provider_metadata": provider_response.metadata},
        )

    def _load_prompt(self) -> str:
        path = self.root_path / "mystic" / "prompts" / self.prompt_file
        return path.read_text(encoding="utf-8")

    def make_claim(
        self,
        problem: str,
        core_plan: CorePlan | None,
        prior_outputs: list[AgentOutput],
    ) -> str:
        return f"{self.agent_name} isolates a {self.division} perspective on the problem."

    def make_status(
        self,
        problem: str,
        core_plan: CorePlan | None,
        prior_outputs: list[AgentOutput],
    ) -> str:
        return self.default_status

    def make_reasoning(
        self,
        problem: str,
        core_plan: CorePlan | None,
        prior_outputs: list[AgentOutput],
        provider_text: str,
    ) -> str:
        prior_agents = ", ".join(output.agent for output in prior_outputs) or "none"
        focus = ", ".join(self.focus_areas[:3]) or "domain structure"
        checks = ", ".join(self.must_check[:3]) or "logical gaps"
        return (
            f"Focus areas: {focus}. Checks: {checks}. Prior agents: {prior_agents}. "
            f"Provider note: {provider_text}"
        )

    def make_dependencies(
        self,
        core_plan: CorePlan | None,
        prior_outputs: list[AgentOutput],
    ) -> list[str]:
        dependencies = ["core"]
        dependencies.extend(output.agent for output in prior_outputs[-2:])
        return dependencies

    def make_obstruction(
        self,
        problem: str,
        core_plan: CorePlan | None,
        prior_outputs: list[AgentOutput],
    ) -> str:
        return "No complete proof or formal verification has been established in v0.1."

    def make_experiment(
        self,
        problem: str,
        core_plan: CorePlan | None,
        prior_outputs: list[AgentOutput],
    ) -> str:
        return ""

    def make_formalization(
        self,
        problem: str,
        core_plan: CorePlan | None,
        prior_outputs: list[AgentOutput],
    ) -> str:
        return ""

    def make_next_move(
        self,
        problem: str,
        core_plan: CorePlan | None,
        prior_outputs: list[AgentOutput],
    ) -> str:
        return f"Escalate the current {self.division} lead into a sharper subproblem."


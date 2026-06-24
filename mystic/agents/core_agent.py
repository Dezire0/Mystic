"""Core planning agent."""

from __future__ import annotations

from pathlib import Path

from mystic.core.model_registry import ModelRegistry
from mystic.core.protocol import CorePlan


class CoreAgent:
    def __init__(self, registry: ModelRegistry, root_path: str | Path) -> None:
        self.registry = registry
        self.root_path = Path(root_path)

    @property
    def prompt(self) -> str:
        path = self.root_path / "mystic" / "prompts" / "core.md"
        return path.read_text(encoding="utf-8")

    def run(self, problem: str) -> CorePlan:
        settings = self.registry.get_agent_settings("core")
        provider = self.registry.get_provider(settings.provider)
        provider_response = provider.generate("core", self.prompt, problem, settings)
        domain_classification = self._classify(problem)
        agents_to_call = self._default_agents(problem)
        return CorePlan(
            problem_restatement=problem.strip(),
            formal_statement=f"Analyze and classify: {problem.strip()}",
            domain_classification=domain_classification,
            subproblems=[
                "Identify the main mathematical or scientific domain.",
                "Separate heuristic evidence from proof obligations.",
                "Check whether computation or formalization can contribute.",
            ],
            agents_to_call=agents_to_call,
            initial_strategy="Plan, route to specialist agents, run safe experiments, then subject claims to Raven review.",
            risk_factors=[
                "Computational evidence may be mistaken for proof.",
                "Selected specialists may miss edge cases without adversarial review.",
            ],
            success_criteria=[
                "Specialists remain structurally separate in code and archive records.",
                "The session produces a report plus dataset-ready archive rows.",
            ],
            raw_response=provider_response.text,
        )

    def _classify(self, problem: str) -> list[str]:
        lowered = problem.lower()
        domains = []
        if any(token in lowered for token in ["prime", "integer", "divisor", "congruence", "fraction"]):
            domains.append("pure_math:number_theory")
        if any(token in lowered for token in ["group", "ring", "field"]):
            domains.append("pure_math:algebra")
        if any(token in lowered for token in ["algorithm", "complexity", "np"]):
            domains.append("science:complexity")
        if not domains:
            domains.append("general:research")
        return domains

    def _default_agents(self, problem: str) -> list[str]:
        lowered = problem.lower()
        agents = ["forge", "raven", "lean"]
        if any(token in lowered for token in ["prime", "integer", "fraction", "congruence"]):
            agents.insert(0, "prime")
        if any(token in lowered for token in ["pattern", "residue", "4/"]):
            agents.append("pattern")
        if "conjecture" in lowered:
            agents.append("conjecture")
        return agents


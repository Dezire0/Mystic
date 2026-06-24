"""Rule-based routing for Mystic v0.1."""

from __future__ import annotations

from pathlib import Path

from mystic.utils.yamlish import load_yaml_file


class RuleRouter:
    def __init__(self, config_path: str | Path) -> None:
        raw = load_yaml_file(config_path)
        self.routes = raw.get("routes", {})

    def route(self, problem: str) -> list[str]:
        lowered = problem.lower()
        selected: list[str] = []

        for agent_name, rule in self.routes.items():
            keywords = [str(item).lower() for item in rule.get("keywords", [])]
            if any(keyword in lowered for keyword in keywords):
                selected.append(agent_name)
                continue

            if rule.get("always_if_computable") and self._looks_computable(lowered):
                selected.append(agent_name)
                continue

            if rule.get("always_if_math_claim") and self._looks_mathematical(lowered):
                selected.append(agent_name)
                continue

            if rule.get("always"):
                selected.append(agent_name)

        if "pattern" not in selected and any(token in lowered for token in ["congruence", "residue", "pattern", "4/"]):
            selected.append("pattern")
        if "conjecture" not in selected and "conjecture" in lowered:
            selected.append("conjecture")

        ordered = []
        for agent_name in selected:
            if agent_name not in ordered:
                ordered.append(agent_name)
        return ordered

    @staticmethod
    def _looks_computable(problem: str) -> bool:
        return any(token in problem for token in ["=", "<", ">", "integer", "n", "prove", "refute", "search"])

    @staticmethod
    def _looks_mathematical(problem: str) -> bool:
        math_tokens = ["prove", "refute", "integer", "equation", "prime", "theorem", "conjecture", "forall", "for every"]
        return any(token in problem for token in math_tokens)


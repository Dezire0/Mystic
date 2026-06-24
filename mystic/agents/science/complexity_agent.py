from mystic.agents.base import BaseAgent


class ComplexityAgent(BaseAgent):
    agent_name = "complexity"
    division = "science"
    prompt_file = "science/complexity.md"
    default_status = "PROMISING"
    focus_areas = ["reductions", "runtime bounds", "search space"]
    must_check = ["model of reduction", "claimed runtime proof", "finite-to-general leaps"]


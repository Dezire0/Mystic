from mystic.agents.base import BaseAgent


class ProbabilityAgent(BaseAgent):
    agent_name = "probability"
    division = "pure_math"
    prompt_file = "pure_math/probability.md"
    default_status = "HEURISTIC"
    focus_areas = ["probabilistic method", "random structures", "average-case behavior"]
    must_check = ["independence assumptions", "finite versus asymptotic claims", "expectation-vs-existence gap"]


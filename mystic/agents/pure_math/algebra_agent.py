from mystic.agents.base import BaseAgent


class AlgebraAgent(BaseAgent):
    agent_name = "algebra"
    division = "pure_math"
    prompt_file = "pure_math/algebra.md"
    default_status = "UNKNOWN"
    focus_areas = ["invariants", "homomorphisms", "algebraic structure"]
    must_check = ["well-defined objects", "preservation properties", "real algebraic leverage"]


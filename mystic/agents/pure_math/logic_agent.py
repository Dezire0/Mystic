from mystic.agents.base import BaseAgent


class LogicAgent(BaseAgent):
    agent_name = "logic"
    division = "pure_math"
    prompt_file = "pure_math/logic.md"
    default_status = "UNKNOWN"
    focus_areas = ["formal systems", "computability", "axiomatic dependence"]
    must_check = ["formalizability", "undecidability risk", "system strength"]


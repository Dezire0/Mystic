from mystic.agents.base import BaseAgent


class BioMathAgent(BaseAgent):
    agent_name = "biomath"
    division = "science"
    prompt_file = "science/biomath.md"
    default_status = "UNKNOWN"
    focus_areas = ["dynamical systems", "networks", "emergent behavior"]
    must_check = ["model assumptions", "parameter sensitivity", "simulation scope"]


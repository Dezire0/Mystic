from mystic.agents.base import BaseAgent


class ChemAgent(BaseAgent):
    agent_name = "chem"
    division = "science"
    prompt_file = "science/chem.md"
    default_status = "UNKNOWN"
    focus_areas = ["molecular graphs", "reaction models", "energy landscapes"]
    must_check = ["stated approximations", "chemical justification", "overgeneralized simulation claims"]


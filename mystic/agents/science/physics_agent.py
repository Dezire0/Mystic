from mystic.agents.base import BaseAgent


class PhysicsAgent(BaseAgent):
    agent_name = "physics"
    division = "science"
    prompt_file = "science/physics.md"
    default_status = "HEURISTIC"
    focus_areas = ["symmetry", "conservation laws", "energy principles"]
    must_check = ["units", "heuristic-only analogies", "mathematical definition"]


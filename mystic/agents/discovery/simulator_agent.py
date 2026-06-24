from mystic.agents.base import BaseAgent


class SimulatorAgent(BaseAgent):
    agent_name = "simulator"
    division = "discovery"
    prompt_file = "discovery/simulator.md"
    default_status = "UNKNOWN"
    focus_areas = ["numerical simulation", "parameter sweeps", "model comparison"]
    must_check = ["explicit assumptions", "error control", "heuristic scope only"]


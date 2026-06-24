from mystic.agents.base import BaseAgent


class PatternAgent(BaseAgent):
    agent_name = "pattern"
    division = "discovery"
    prompt_file = "discovery/pattern.md"
    default_status = "HEURISTIC"
    focus_areas = ["residue classes", "numerical patterns", "candidate invariants"]
    must_check = ["larger test stability", "coincidence risk", "actual invariance"]

    def make_claim(self, problem, core_plan, prior_outputs):
        if "4/" in problem or "erd" in problem.lower():
            return "PatternAgent expects residue-class regularities to be worth checking, but not sufficient for proof."
        return "PatternAgent isolates numerical or structural regularities worth testing further."


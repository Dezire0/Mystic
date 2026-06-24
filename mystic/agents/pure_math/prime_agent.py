from mystic.agents.base import BaseAgent


class PrimeAgent(BaseAgent):
    agent_name = "prime"
    division = "pure_math"
    prompt_file = "pure_math/prime.md"
    default_status = "PROMISING"
    focus_areas = ["divisibility", "modular arithmetic", "Diophantine structure"]
    must_check = ["integrality", "positivity", "residue-class coverage"]

    def make_claim(self, problem, core_plan, prior_outputs):
        if "4/" in problem or "erd" in problem.lower():
            return "Number-theoretic residue classes and parameterizations are the natural first line of attack."
        return "PrimeAgent identifies arithmetic structure worth isolating before broader proof attempts."


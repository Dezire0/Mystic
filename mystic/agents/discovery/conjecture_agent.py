from mystic.agents.base import BaseAgent


class ConjectureAgent(BaseAgent):
    agent_name = "conjecture"
    division = "discovery"
    prompt_file = "discovery/conjecture.md"
    default_status = "HEURISTIC"
    focus_areas = ["weak conjectures", "counterexample regions", "evidence tracking"]
    must_check = ["do not call heuristics proofs", "respect Raven objections", "evidence limits"]

    def make_claim(self, problem, core_plan, prior_outputs):
        return "ConjectureAgent proposes only evidence-backed hypotheses, not proofs."


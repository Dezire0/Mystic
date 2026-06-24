from mystic.agents.base import BaseAgent


class RavenAgent(BaseAgent):
    agent_name = "raven"
    division = "verification"
    prompt_file = "verification/raven.md"
    default_status = "GAP"
    focus_areas = ["hidden assumptions", "one-way implications", "unsupported existence claims"]
    must_check = ["proof gaps", "false equivalence", "computational evidence misuse"]

    def make_claim(self, problem, core_plan, prior_outputs):
        return "Raven does not accept the current argument as a complete proof without explicit justification of every critical step."

    def make_reasoning(self, problem, core_plan, prior_outputs, provider_text):
        prior = ", ".join(f"{item.agent}:{item.status}" for item in prior_outputs) or "none"
        return (
            "Raven review: computational evidence is not proof; heuristic pattern discovery is not proof; "
            f"current upstream outputs = {prior}. Provider note: {provider_text}"
        )

    def make_next_move(self, problem, core_plan, prior_outputs):
        return "Convert each heuristic or computational claim into an explicitly justified lemma, then re-run Raven."


from mystic.agents.base import BaseAgent


class EvolutionAgent(BaseAgent):
    agent_name = "evolution"
    division = "memory"
    prompt_file = "memory/evolution.md"
    default_status = "PROMISING"
    focus_areas = ["dataset rows", "future adapters", "training export paths"]
    must_check = ["agent separation", "archive coverage", "export compatibility"]

    def make_claim(self, problem, core_plan, prior_outputs):
        return "EvolutionAgent prepares archived specialist outputs for future LoRA or QLoRA dataset generation."


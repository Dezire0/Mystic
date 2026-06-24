from mystic.agents.base import BaseAgent


class ArchiveAgent(BaseAgent):
    agent_name = "archive"
    division = "memory"
    prompt_file = "memory/archive.md"
    default_status = "FORMALIZED"
    focus_areas = ["session storage", "structured records", "dataset traceability"]
    must_check = ["session ids", "model metadata", "structured output persistence"]

    def make_claim(self, problem, core_plan, prior_outputs):
        return "ArchiveAgent confirms the session is stored with per-agent provider, model, and adapter metadata."


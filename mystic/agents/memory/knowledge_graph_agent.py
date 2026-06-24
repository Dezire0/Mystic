from mystic.agents.base import BaseAgent


class KnowledgeGraphAgent(BaseAgent):
    agent_name = "knowledge_graph"
    division = "memory"
    prompt_file = "memory/knowledge_graph.md"
    default_status = "UNKNOWN"
    focus_areas = ["concept graph", "dependency tracking", "problem relationships"]
    must_check = ["node identity", "edge meaning", "incremental updates"]

    def make_claim(self, problem, core_plan, prior_outputs):
        return "KnowledgeGraphAgent is stubbed in v0.1 but preserves a separate update path for future graph storage."


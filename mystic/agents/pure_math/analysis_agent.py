from mystic.agents.base import BaseAgent


class AnalysisAgent(BaseAgent):
    agent_name = "analysis"
    division = "pure_math"
    prompt_file = "pure_math/analysis.md"
    default_status = "UNKNOWN"
    focus_areas = ["limits", "compactness", "functional estimates"]
    must_check = ["regularity assumptions", "boundary conditions", "justified manipulations"]


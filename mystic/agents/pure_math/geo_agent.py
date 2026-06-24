from mystic.agents.base import BaseAgent


class GeoAgent(BaseAgent):
    agent_name = "geo"
    division = "pure_math"
    prompt_file = "pure_math/geo.md"
    default_status = "UNKNOWN"
    focus_areas = ["solution spaces", "dimension arguments", "geometric reformulation"]
    must_check = ["equivalence of translation", "singular cases", "topological rigor"]


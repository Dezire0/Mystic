from mystic.agents.base import BaseAgent


class SMTAgent(BaseAgent):
    agent_name = "smt"
    division = "verification"
    prompt_file = "verification/smt.md"
    default_status = "UNKNOWN"
    focus_areas = ["constraint encoding", "finite search", "counterexample hunting"]
    must_check = ["faithful encoding", "boundedness", "SAT/UNSAT interpretation"]


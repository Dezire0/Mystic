from mystic.agents.base import BaseAgent


class LeanAgent(BaseAgent):
    agent_name = "lean"
    division = "verification"
    prompt_file = "verification/lean.md"
    default_status = "GAP"
    focus_areas = ["formal theorem statement", "imports", "proof skeleton"]
    must_check = ["mathlib dependencies", "missing lemmas", "formal blockers"]

    def make_claim(self, problem, core_plan, prior_outputs):
        return "LeanAgent can draft a formal statement and expose blockers, even when full formalization fails."

    def make_formalization(self, problem, core_plan, prior_outputs):
        if "4/" in problem or "erd" in problem.lower():
            return (
                "import Mathlib\n\n"
                "theorem erdos_straus_placeholder (n : Nat) (h : 2 <= n) :\n"
                "    ∃ x y z : Nat, 0 < x ∧ 0 < y ∧ 0 < z := by\n"
                "  sorry\n"
            )
        return (
            "import Mathlib\n\n"
            "theorem mystic_placeholder : True := by\n"
            "  trivial\n"
        )


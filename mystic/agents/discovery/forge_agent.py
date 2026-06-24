from mystic.agents.base import BaseAgent


class ForgeAgent(BaseAgent):
    agent_name = "forge"
    division = "discovery"
    prompt_file = "discovery/forge.md"
    default_status = "HEURISTIC"
    focus_areas = ["computational experiments", "counterexample search", "parameter sweeps"]
    must_check = ["safe execution", "search bounds", "evidence-vs-proof distinction"]

    def make_claim(self, problem, core_plan, prior_outputs):
        return "ForgeAgent proposes a bounded experiment to test local patterns and hunt for counterexamples."

    def make_experiment(self, problem, core_plan, prior_outputs):
        if "4/" in problem or "erd" in problem.lower():
            return (
                "from fractions import Fraction\n\n"
                "def find_representation(n: int):\n"
                "    for x in range(1, 8 * n + 1):\n"
                "        for y in range(x, 8 * n + 1):\n"
                "            remainder = Fraction(4, n) - Fraction(1, x) - Fraction(1, y)\n"
                "            if remainder > 0 and remainder.numerator == 1:\n"
                "                return (x, y, remainder.denominator)\n"
                "    return None\n\n"
                "missing = []\n"
                "for n in range(2, 21):\n"
                "    if find_representation(n) is None:\n"
                "        missing.append(n)\n"
                "print({'checked_up_to': 20, 'missing': missing})\n"
            )
        return "print({'status': 'no_special_experiment', 'note': 'bounded local test only'})\n"

    def make_next_move(self, problem, core_plan, prior_outputs):
        return "Increase the search space only after turning observed regularities into explicit conjectures."


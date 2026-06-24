from __future__ import annotations

import unittest
from pathlib import Path

from mystic.core.router import RuleRouter


class RouterTests(unittest.TestCase):
    def test_router_selects_prime_forge_raven_and_lean(self):
        router = RuleRouter(Path(__file__).resolve().parents[1] / "configs" / "router_config.yaml")
        selected = router.route("For every integer n >= 2, analyze the prime congruence structure of 4/n.")
        for agent in ["prime", "forge", "raven", "lean"]:
            self.assertIn(agent, selected)


if __name__ == "__main__":
    unittest.main()


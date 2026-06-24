from __future__ import annotations

import unittest
from pathlib import Path

from mystic.agents.pure_math.prime_agent import PrimeAgent
from mystic.agents.verification.raven_agent import RavenAgent
from mystic.core.model_registry import ModelRegistry


class AgentTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        self.registry = ModelRegistry(root / "configs" / "model_config.yaml")
        self.root = root

    def test_prime_agent_produces_promising_output(self):
        output = PrimeAgent(self.registry, self.root).run("Study 4/n over positive integers.")
        self.assertEqual(output.agent, "prime")
        self.assertEqual(output.status, "PROMISING")

    def test_raven_agent_returns_gap_status(self):
        output = RavenAgent(self.registry, self.root).run("Prove something quickly.")
        self.assertEqual(output.status, "GAP")


if __name__ == "__main__":
    unittest.main()


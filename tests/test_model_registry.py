from __future__ import annotations

import unittest
from pathlib import Path

from mystic.core.model_registry import ModelRegistry


class ModelRegistryTests(unittest.TestCase):
    def test_specialists_have_distinct_config_entries(self):
        registry = ModelRegistry(Path(__file__).resolve().parents[1] / "configs" / "model_config.yaml")
        prime = registry.get_agent_settings("prime")
        algebra = registry.get_agent_settings("algebra")
        self.assertEqual(prime.adapter, "prime_lora_v0")
        self.assertEqual(algebra.adapter, "algebra_lora_v0")
        self.assertNotEqual(prime.adapter, algebra.adapter)


if __name__ == "__main__":
    unittest.main()


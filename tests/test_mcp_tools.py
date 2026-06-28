from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from mystic.mcp.tools import MysticToolbox
from mystic.models.router import ModelRouter


TEST_CONFIG = """
models:
  local_prime:
    provider: mock
    model: mock-prime
    role_defaults:
      - draft
  local_forge:
    provider: mock
    model: mock-forge
    role_defaults:
      - draft
  local_raven:
    provider: mock
    model: mock-raven
    role_defaults:
      - critique
  local_report:
    provider: mock
    model: mock-report
    role_defaults:
      - summarize
policy:
  max_models_per_compare: 3
  timeout_per_model_seconds: 5
"""


class MCPToolsTests(unittest.TestCase):
    def _make_toolbox(self) -> MysticToolbox:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        config_path = root / "models.yaml"
        config_path.write_text(TEST_CONFIG, encoding="utf-8")
        router = ModelRouter(root_path=root, config_path=config_path)
        return MysticToolbox(root_path=root, router=router)

    def tearDown(self) -> None:
        temp_dir = getattr(self, "temp_dir", None)
        if temp_dir is not None:
            temp_dir.cleanup()

    def test_status_reports_models_and_tools(self):
        toolbox = self._make_toolbox()
        status = toolbox.mystic_status()
        self.assertIn("local_prime", status["models"])
        self.assertEqual(status["tools"]["mcp_server"], "ready")

    def test_verify_answer_flags_invalid_egyptian_fraction_set(self):
        toolbox = self._make_toolbox()
        result = toolbox.mystic_verify_answer(
            problem="1/x + 1/y + 1/z = 1",
            candidate_answer="(2,4,8), (2,3,6), (3,3,3)",
            constraints=["x <= y <= z", "positive integers"],
        )
        self.assertEqual(result["verdict"], "INVALID")
        self.assertIn("(2, 4, 4)", " ".join(result["missing_candidates"]))

    def test_bruteforce_integer_search_returns_small_solutions(self):
        toolbox = self._make_toolbox()
        result = toolbox.mystic_bruteforce_integer_search(
            equation="x + y = 5",
            variables=["x", "y"],
            constraints=["x <= y", "positive integers"],
            bounds={"x": [1, 4], "y": [1, 4]},
        )
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["solutions"], [{"x": 1, "y": 4}, {"x": 2, "y": 3}])

    def test_run_local_agent_returns_agent_status_contract(self):
        toolbox = self._make_toolbox()
        result = toolbox.mystic_run_local_agent(
            agent="raven",
            task="Critique the answer",
            problem="x + y = 5",
        )
        self.assertEqual(result["agent"], "raven")
        self.assertEqual(result["status"], "CRITIQUE_ONLY")
        self.assertEqual(result["provider"], "mock")

    def test_compare_models_returns_display_text(self):
        toolbox = self._make_toolbox()
        result = toolbox.mystic_compare_models(
            problem="x + y = 5",
            models=["local_prime", "local_forge"],
            task="Draft solutions",
            include_verifier=False,
        )
        self.assertEqual(len(result["model_outputs"]), 2)
        self.assertIn("[local_prime / mock / mock-prime / draft / DRAFT_ONLY]", result["display_text"])


if __name__ == "__main__":
    unittest.main()

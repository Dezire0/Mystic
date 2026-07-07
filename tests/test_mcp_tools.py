from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mystic.mcp.import_verification import REQUIRED_TOOLS, default_verification_artifact_path
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
  gemini_cli:
    provider: cli
    command: gemini
    auth: google_login
    role_defaults:
      - draft
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
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "sk-test-secret",
                "MYSTIC_OAUTH_ENABLED": "true",
                "MYSTIC_OAUTH_ISSUER": "https://mystic.dexproject.workers.dev",
                "MYSTIC_OAUTH_SIGNING_SECRET": "oauth-signing-secret",
            },
            clear=False,
        ):
            toolbox = self._make_toolbox()
            status = toolbox.mystic_status()
        self.assertIn("local_prime", status["models"])
        self.assertEqual(status["tools"]["mystic_status"], "ready")
        self.assertEqual(status["tools"]["health_check"], "ready")
        self.assertEqual(status["tools"]["provider_list"], "ready")
        self.assertNotIn("details", status["models"]["local_prime"]["status"])
        self.assertTrue(status["lab_core_available"])
        self.assertGreaterEqual(status["lab_tools_count"], 5)
        self.assertTrue(status["lab_storage_root"].endswith("mystic_data/lab_sessions"))
        self.assertEqual(status["storage_backend"], "local")
        self.assertEqual(status["storage_status"]["backend"], "local")
        self.assertEqual(status["remote_mcp_public_endpoint"], "https://mystic.dexproject.workers.dev/mcp")
        self.assertTrue(status["oauth_enabled"])
        self.assertTrue(status["oauth_configured"])
        self.assertTrue(status["oauth_metadata_available"])
        self.assertFalse(status["chatgpt_remote_import_ready"])
        self.assertTrue(status["chatgpt_remote_import_ready_candidate"])
        self.assertFalse(status["manual_import_verification_checked"])
        self.assertFalse(status["manual_import_verified"])
        self.assertTrue(status["manual_import_verification_path"].endswith("mystic_data/e2e/chatgpt_remote_mcp_import/verification.json"))
        self.assertIn("MANUAL_IMPORT_NOT_VERIFIED", status["blockers"])
        self.assertTrue(status["provider_registry"])
        self.assertNotIn("sk-test-secret", json.dumps(status))
        self.assertNotIn("oauth-signing-secret", json.dumps(status))

    def test_health_check_returns_minimal_local_status(self):
        toolbox = self._make_toolbox()
        result = toolbox.health_check()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["mode"], "local_backend")
        self.assertEqual(result["storage_backend"], "local")
        self.assertIn("health_check", result["phase_1_tools"])

    def test_status_reports_supabase_storage_blocker_when_unconfigured(self):
        with patch.dict(
            os.environ,
            {
                "MYSTIC_STORAGE_BACKEND": "supabase",
                "MYSTIC_OAUTH_ENABLED": "true",
                "MYSTIC_OAUTH_ISSUER": "https://mystic.dexproject.workers.dev",
                "MYSTIC_OAUTH_SIGNING_SECRET": "oauth-signing-secret",
            },
            clear=False,
        ):
            toolbox = self._make_toolbox()
            status = toolbox.mystic_status()
        self.assertEqual(status["storage_backend"], "supabase")
        self.assertFalse(status["storage_status"]["configured"])
        self.assertIn("LAB_STORAGE_NOT_CONFIGURED", status["blockers"])

    def test_status_reports_manual_import_summary_without_secrets(self):
        with patch.dict(
            os.environ,
            {
                "MYSTIC_OAUTH_ENABLED": "true",
                "MYSTIC_OAUTH_ISSUER": "https://mystic.dexproject.workers.dev",
                "MYSTIC_OAUTH_SIGNING_SECRET": "oauth-signing-secret",
            },
            clear=False,
        ):
            toolbox = self._make_toolbox()
            artifact_path = default_verification_artifact_path(toolbox.root_path)
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text(
                json.dumps(
                    {
                        "artifact_version": 1,
                        "verified_at": "2026-07-02T09:17:49+00:00",
                        "verified_by": "manual",
                        "public_endpoint": "https://mystic.dexproject.workers.dev",
                        "mcp_endpoint": "https://mystic.dexproject.workers.dev/mcp",
                        "chatgpt_developer_mode_imported": True,
                        "oauth_flow_completed": True,
                        "tools_list_visible_in_chatgpt": True,
                        "required_tools_visible": list(REQUIRED_TOOLS),
                        "manual_tool_call_results": {tool: "passed" for tool in REQUIRED_TOOLS},
                        "notes": "private operator notes",
                    }
                ),
                encoding="utf-8",
            )
            status = toolbox.mystic_status()
        self.assertTrue(status["manual_import_verification_checked"])
        self.assertTrue(status["manual_import_verified"])
        self.assertTrue(status["chatgpt_remote_import_ready"])
        self.assertNotIn("notes", json.dumps(status))
        self.assertNotIn("oauth-signing-secret", json.dumps(status))

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

    def test_python_check_task_mode_supports_safe_evaluation(self):
        toolbox = self._make_toolbox()
        result = toolbox.mystic_run_python_check(
            code_or_task="evaluate: 2 + 3 * 4",
            mode="task",
        )
        self.assertEqual(result["status"], "PASS")
        self.assertIn("14", result["stdout"])

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
        self.assertEqual(result["final_decision_source"], "model_outputs")

    def test_run_debate_creates_threaded_turns(self):
        toolbox = self._make_toolbox()
        result = toolbox.mystic_run_debate(
            problem="1/x + 1/y + 1/z = 1, x <= y <= z, positive integers",
            participants=[
                {"model_id": "local_prime", "role": "solver"},
                {"model_id": "local_raven", "role": "critic"},
            ],
            rounds=3,
            tools=["mystic_verify_answer"],
            max_turns=8,
        )
        self.assertTrue(result["turns"])
        critique_turns = [turn for turn in result["turns"] if turn["phase"] == "cross_critique"]
        self.assertTrue(critique_turns)
        self.assertTrue(critique_turns[0]["reply_to"])
        tool_turns = [turn for turn in result["turns"] if turn["speaker_type"] == "tool"]
        self.assertTrue(tool_turns)

    def test_run_research_table_extracts_discoveries(self):
        toolbox = self._make_toolbox()
        result = toolbox.mystic_run_research_table(
            problem="Investigate patterns in x + y = 5 over positive integers.",
            participants=["local_prime", "local_raven"],
            mode="discovery_debate",
            max_rounds=3,
            enable_tools=True,
            tools=["mystic_verify_answer"],
        )
        self.assertTrue(result["discoveries"])
        first = result["discoveries"][0]
        self.assertIn("claim", first)
        self.assertIn("confidence", first)
        self.assertIn("needs_verification", first)
        self.assertTrue(result["verification_requests"])
        self.assertTrue(result["saved_artifact_path"].endswith("session.json"))
        self.assertIn("mystic_data/research_table_sessions", result["saved_artifact_path"])

    def test_compare_models_uses_verifier_as_final_decision_source(self):
        toolbox = self._make_toolbox()
        result = toolbox.mystic_compare_models(
            problem="positive integers x, y satisfy x + y = 5",
            models=["local_prime", "local_forge"],
            task="Give one valid ordered pair.",
            include_verifier=True,
        )
        self.assertEqual(result["final_decision_source"], "deterministic_verifier")

    def test_provider_tools_return_safe_foundation_status(self):
        toolbox = self._make_toolbox()
        listing = toolbox.provider_list()
        status = toolbox.provider_status(provider_id="openai_compatible")
        instructions = toolbox.provider_configure_secret_instructions(provider_id="openai_compatible")
        verified = toolbox.provider_verify(provider_id="openai_compatible")
        models = toolbox.provider_model_list(provider_id="openai_compatible")
        call_test = toolbox.provider_call_test(provider_id="openai_compatible", prompt="ping")

        self.assertEqual(listing["providers"][0]["provider_id"], "openai_compatible")
        self.assertIn(status["status"], {"not_configured", "api_key_required"})
        self.assertIn("MYSTIC_PROVIDER_OPENAI_COMPAT_API_KEY", instructions["secret_names"])
        self.assertNotIn("sk-", json.dumps(instructions))
        self.assertIn(verified["status"], {"not_configured", "api_key_required"})
        self.assertEqual(models["status"], verified["status"])
        self.assertEqual(call_test["status"], "provider_required")

    def test_provider_connect_start_and_callback_status_cover_oauth_metadata_flow(self):
        toolbox = self._make_toolbox()
        started = toolbox.provider_connect_start(provider_id="future_custom", auth_method="oauth")
        callback = toolbox.provider_connect_callback_status(
            provider_id="future_custom",
            flow_id=started["flow"]["flow_id"],
        )

        self.assertEqual(started["status"], "oauth_required")
        self.assertEqual(callback["flow"]["status"], "oauth_required")
        self.assertFalse(callback["callback_received"])

    def test_provider_disconnect_preserves_disconnect_state_and_mock_test_path(self):
        toolbox = self._make_toolbox()
        disconnected = toolbox.provider_disconnect(provider_id="openai_compatible")
        verified = toolbox.provider_verify(provider_id="openai_compatible")
        mock_started = toolbox.provider_connect_start(provider_id="mock", auth_method="none/mock")
        mock_call = toolbox.provider_call_test(provider_id="mock", prompt="hello")

        self.assertEqual(disconnected["status"], "disconnected")
        self.assertEqual(verified["status"], "disconnected")
        self.assertEqual(mock_started["status"], "connected")
        self.assertEqual(mock_call["status"], "completed")
        self.assertEqual(mock_call["output"], "mock:hello")
    def test_research_table_uses_verifier_as_final_decision_source_when_enabled(self):
        toolbox = self._make_toolbox()
        result = toolbox.mystic_run_research_table(
            problem="positive integers x, y satisfy x + y = 5",
            participants=["local_prime", "local_raven"],
            mode="discovery_debate",
            max_rounds=2,
            enable_tools=True,
            tools=["mystic_verify_answer"],
        )
        self.assertEqual(result["final_decision_source"], "deterministic_verifier")
        self.assertEqual(result["final_status"], result["verification"]["verdict"])

    def test_research_table_with_unauthenticated_gemini_records_auth_required_turn(self):
        toolbox = self._make_toolbox()
        with patch("mystic.models.providers.base.shutil.which", return_value="/usr/bin/gemini"), patch(
            "mystic.models.providers.cli_provider.run_command",
            return_value=(1, "", "Login with Google", 0.01),
        ):
            result = toolbox.mystic_run_research_table(
                problem="positive integers x, y satisfy x + y = 5",
                participants=["gemini_cli", "local_prime"],
                mode="discovery_debate",
                max_rounds=2,
                enable_tools=True,
                tools=["mystic_verify_answer"],
            )
        auth_turns = [turn for turn in result["turns"] if turn["speaker_id"] == "gemini_cli" and turn["status"] == "AUTH_REQUIRED"]
        self.assertTrue(auth_turns)
        self.assertIn("Login with Google", auth_turns[0]["content"])

    def test_teacher_packet_export_and_import_persist(self):
        toolbox = self._make_toolbox()
        toolbox.mystic_call_model(
            model_id="local_prime",
            role="draft",
            task="Draft",
            problem="x + y = 5",
        )
        packet = toolbox.mystic_export_teacher_packet(limit=1, filter="mock-prime")
        self.assertEqual(len(packet["cases"]), 1)
        imported = toolbox.mystic_import_teacher_label(
            packet_id=packet["packet_id"],
            label_json={
                "verdict": "NEEDS_MORE_DETAIL",
                "first_fatal_error": "missing proof",
                "critique": "too shallow",
                "corrected_reasoning": "enumerate the integer cases",
                "training_target": "raven",
                "training_value": "medium",
            },
            source_model="gpt_controller",
            target_agent="raven",
        )
        self.assertTrue(imported["saved"])
        self.assertTrue(Path(imported["saved_path"]).exists())

    def test_lab_session_create_and_advance_persist_structured_files(self):
        toolbox = self._make_toolbox()
        created = toolbox.lab_session_create(
            problem="Find integer solutions to x + y = 5.",
            domain="math",
            goal="Build a structured research trace.",
            mode="serious",
            participants=["local_prime", "local_raven"],
        )
        self.assertEqual(created["status"], "created")
        session_id = created["session_id"]

        advanced = toolbox.lab_session_advance(
            session_id=session_id,
            max_steps=4,
            use_model_arena=False,
            use_verifier=True,
        )
        self.assertTrue(advanced["new_turns"])
        self.assertTrue((Path(self.temp_dir.name) / "mystic_data" / "lab_sessions" / session_id / "session.json").exists())
        loaded = toolbox.lab_session_get(session_id=session_id)
        self.assertEqual(loaded["session"]["session_id"], session_id)
        self.assertIn("claims", loaded)

    def test_lab_models_debate_imports_research_table_outputs(self):
        toolbox = self._make_toolbox()
        created = toolbox.lab_session_create(
            problem="Investigate positive integers x, y with x + y = 5.",
            domain="math",
            goal="Use Model Arena to gather discoveries.",
            mode="multi_model_debate",
            participants=["local_prime", "local_raven"],
        )
        result = toolbox.lab_models_debate(
            session_id=created["session_id"],
            question="Investigate positive integers x, y with x + y = 5.",
            participants=["local_prime", "local_raven"],
            rounds=["independent_discovery", "cross_critique", "revision_after_evidence", "final_synthesis"],
            use_existing_research_table=True,
        )
        self.assertIn("research_table_session_id", result)
        loaded = toolbox.lab_session_get(session_id=created["session_id"])
        self.assertTrue(loaded["claims"] or loaded["experiments"])


if __name__ == "__main__":
    unittest.main()

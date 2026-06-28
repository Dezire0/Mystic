from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from mystic.app.api import create_app


class _StubOrchestrator:
    def run_problem(self, problem: str):
        raise NotImplementedError

    def get_session(self, session_id: str):
        return {"session_id": session_id}

    def list_sessions(self):
        return []

    def available_agents(self):
        return {"prime": {"provider": "mock", "model": "mock-prime"}}

    def export_dataset(self, export_type: str):
        return [f"/tmp/{export_type}.jsonl"]


class _StubToolbox:
    def __init__(self, root_path: Path) -> None:
        self.root_path = root_path

    def mystic_status(self):
        return {
            "models": {
                "local_prime": {
                    "provider": "ollama",
                    "model_name": "deepseek-r1-distill-14b",
                    "status": {"state": "ready", "message": "ready"},
                    "role_defaults": ["draft", "revise"],
                },
                "local_qwen": {
                    "provider": "ollama",
                    "model_name": "qwen3-14b",
                    "status": {"state": "ready", "message": "ready"},
                    "role_defaults": ["draft", "summarize"],
                },
                "local_raven": {
                    "provider": "local_adapter",
                    "model_name": "Qwen/Qwen2.5-0.5B-Instruct + raven_lora_v0",
                    "status": {"state": "ready", "message": "ready"},
                    "role_defaults": ["critique"],
                },
                "gemini_cli": {
                    "provider": "cli",
                    "model_name": "gemini_cli",
                    "status": {"state": "not_authenticated", "message": "Login with Google."},
                    "role_defaults": ["draft", "critique"],
                },
                "claude_cli": {
                    "provider": "cli",
                    "model_name": "claude_cli",
                    "status": {"state": "not_authenticated", "message": "Login with Claude."},
                    "role_defaults": ["critique", "judge"],
                },
            },
            "tools": {"mcp_server": "ready"},
            "datasets": {},
            "adapter_status": {"available": []},
            "recent_runs": [],
            "recent_errors": [],
            "mcp_server_status": "ready",
        }

    def mystic_run_research_table(
        self,
        *,
        problem: str,
        participants: list[str],
        mode: str,
        max_rounds: int,
        enable_tools: bool,
        tools: list[str],
    ):
        session_id = "research-test-session"
        session_dir = self.root_path / "mystic_data" / "research_table_sessions" / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "session_id": session_id,
            "problem": problem,
            "participants": participants,
            "rounds": max_rounds,
            "turns": [],
            "discoveries": [],
            "verification_requests": [],
            "rejected_discoveries": [],
            "final_synthesis_package": {"mode": mode, "tools": tools, "enable_tools": enable_tools},
        }
        (session_dir / "session.json").write_text(json.dumps(payload), encoding="utf-8")
        return {"session_id": session_id}


class AppRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "mystic_data" / "teacher_packets").mkdir(parents=True, exist_ok=True)
        (self.root / "mystic_data" / "teacher_labels").mkdir(parents=True, exist_ok=True)
        (self.root / "mystic_data" / "debate_sessions" / "debate-test").mkdir(parents=True, exist_ok=True)
        (self.root / "mystic_data" / "research_table_sessions" / "research-existing").mkdir(parents=True, exist_ok=True)
        (self.root / "mystic_data" / "runs" / "compare-test" / "tool_checks").mkdir(parents=True, exist_ok=True)

        (self.root / "mystic_data" / "teacher_packets" / "packet.json").write_text(
            json.dumps({"packet_id": "packet-1", "target_agent": "raven", "cases": [1]}),
            encoding="utf-8",
        )
        (self.root / "mystic_data" / "teacher_labels" / "label.json").write_text(
            json.dumps({"label_id": "label-1", "target_agent": "raven", "source_model": "gpt_controller", "label": {"verdict": "INVALID"}}),
            encoding="utf-8",
        )
        (self.root / "mystic_data" / "debate_sessions" / "debate-test" / "session.json").write_text(
            json.dumps({"session_id": "debate-test", "problem": "debate", "turns": [], "final_package": "done"}),
            encoding="utf-8",
        )
        (self.root / "mystic_data" / "research_table_sessions" / "research-existing" / "session.json").write_text(
            json.dumps({"session_id": "research-existing", "problem": "research", "turns": [], "discoveries": [], "verification_requests": [], "rejected_discoveries": [], "final_synthesis_package": {}}),
            encoding="utf-8",
        )
        (self.root / "mystic_data" / "runs" / "compare-test" / "tool_checks" / "compare-abc.json").write_text(
            json.dumps({"session_id": "compare-1", "problem": "compare", "display_text": "[local_prime / mock / mock-prime / draft / DRAFT_ONLY]\ncontent"}),
            encoding="utf-8",
        )

        app = create_app(
            root_path=self.root,
            orchestrator=_StubOrchestrator(),
            toolbox=_StubToolbox(self.root),
        )
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_root_redirects_to_research_table_start(self):
        response = self.client.get("/", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["location"], "/research-table/start")

    def test_start_page_renders_participants_and_auth_cards(self):
        response = self.client.get("/research-table/start")
        self.assertEqual(response.status_code, 200)
        self.assertIn("ResearchTableStartPage", response.text)
        self.assertIn("Gemini CLI", response.text)
        self.assertIn("Login with Google", response.text)

    def test_research_table_run_redirects_to_created_session(self):
        response = self.client.get(
            "/research-table/start/run",
            params=[
                ("problem", "Test problem"),
                ("participants", "local_prime"),
                ("participants", "local_qwen"),
            ],
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["location"], "/research-table/sessions/research-test-session")

    def test_existing_research_table_session_route_renders(self):
        response = self.client.get("/research-table/sessions/research-existing")
        self.assertEqual(response.status_code, 200)
        self.assertIn("ResearchTableSessionPage", response.text)

    def test_debate_and_teacher_routes_render(self):
        debate = self.client.get("/debate/sessions/debate-test")
        teacher = self.client.get("/teacher-labels")
        compare = self.client.get("/model-compare")
        detail = self.client.get("/sessions/detail")
        auth = self.client.get("/providers/auth/gemini_cli")
        self.assertEqual(debate.status_code, 200)
        self.assertEqual(teacher.status_code, 200)
        self.assertEqual(compare.status_code, 200)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(auth.status_code, 200)
        self.assertIn("TeacherLabelsPage", teacher.text)
        self.assertIn("ModelComparePage", compare.text)
        self.assertIn("SessionDetailPage", detail.text)
        self.assertIn("ProviderAuthCard", auth.text)


if __name__ == "__main__":
    unittest.main()

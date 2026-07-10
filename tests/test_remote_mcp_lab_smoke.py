from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch

from scripts import run_remote_mcp_lab_smoke as smoke


def _mcp_success(request_id: int, result: dict[str, object]) -> dict[str, object]:
    return {"status": 200, "headers": {}, "body": {"jsonrpc": "2.0", "id": request_id, "result": result}}


def _success_tool_names() -> list[str]:
    return sorted(smoke.EXISTING_TOOLS | smoke.LAB_TOOLS | smoke.PROVIDER_CONNECT_TOOLS)


def _success_responses(persisted: dict[str, str], session_id: str) -> dict[int, dict[str, object]]:
    scene_id = "scene-1"
    return {
        1: _mcp_success(1, {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}}}),
        2: _mcp_success(2, {"tools": [{"name": name} for name in _success_tool_names()]}),
        3: _mcp_success(3, {"structuredContent": {"runtime_mode": "cloud_native_worker_lab_v0"}}),
        4: _mcp_success(4, {"structuredContent": {"status": "ok"}}),
        5: _mcp_success(5, {"structuredContent": {"session_id": session_id, "status": "created", "paths": persisted}}),
        6: _mcp_success(
            6,
            {"structuredContent": {"updated_session": {"session_id": session_id, "status": "running"}, "paths": persisted}},
        ),
        7: _mcp_success(
            7,
            {
                "structuredContent": {
                    "turn_id": "turn-1",
                    "status": "LOCAL_BACKEND_REQUIRED",
                    "provider_result": {"status": "local_backend_required"},
                }
            },
        ),
        8: _mcp_success(8, {"structuredContent": {"verdict": "DEFERRED", "deferred": {"status": "deferred"}}}),
        9: _mcp_success(9, {"structuredContent": {"written_object_id": "claim-1", "status": "written"}}),
        10: _mcp_success(
            10,
            {
                "structuredContent": {
                    "matching_sessions": [],
                    "claims": [{"claim_id": "claim-1"}],
                    "failures": [],
                    "experiments": [],
                    "memory_edges": [],
                }
            },
        ),
        11: _mcp_success(11, {"structuredContent": {"experiment_id": "exp-1", "status": "inconclusive"}}),
        12: _mcp_success(12, {"structuredContent": {"verdict": "inconclusive", "deferred": {"status": "deferred"}}}),
        13: _mcp_success(
            13,
            {
                "structuredContent": {
                    "summary": "Provider credentials are required.",
                    "provider_result": {"status": "api_key_required"},
                }
            },
        ),
        14: _mcp_success(
            14,
            {
                "structuredContent": {
                    "session": {"session_id": session_id},
                    "notebook_path": persisted["notebook_path"],
                    "report_path": persisted["report_path"],
                }
            },
        ),
        15: _mcp_success(15, {"structuredContent": {"report_path": persisted["report_path"], "status": "completed"}}),
        16: _mcp_success(
            16,
            {
                "structuredContent": {
                    "scene_id": scene_id,
                    "session_id": session_id,
                    "paths": {
                        "scene": persisted["scene_path"],
                        "objects": persisted["scene_objects_path"],
                        "simulations": persisted["scene_simulations_path"],
                        "report": persisted["scene_report_path"],
                        "snapshot": persisted["scene_snapshot_path"],
                    },
                }
            },
        ),
        17: _mcp_success(17, {"structuredContent": {"object_id": "ball-1"}}),
        18: _mcp_success(18, {"structuredContent": {"object": {"label": "Projectile A"}}}),
        19: _mcp_success(19, {"structuredContent": {"parameters": {"gravity": 9.5}}}),
        20: _mcp_success(
            20,
            {
                "structuredContent": {
                    "simulation_id": "sim-1",
                    "status": "completed",
                    "result": {"status": "completed"},
                }
            },
        ),
        21: _mcp_success(21, {"structuredContent": {"attached_object_ids": ["ball-1"], "attached_simulations": ["sim-1"]}}),
        22: _mcp_success(
            22,
            {
                "structuredContent": {
                    "status": "completed",
                    "snapshot": {"scene": {"name": "Smoke Scene"}},
                }
            },
        ),
        23: _mcp_success(
            23,
            {
                "structuredContent": {
                    "scene": {"scene_id": scene_id},
                    "report_path": persisted["scene_report_path"],
                    "snapshot_path": persisted["scene_snapshot_path"],
                }
            },
        ),
        24: _mcp_success(
            24,
            {
                "structuredContent": {
                    "report_path": persisted["scene_report_path"],
                    "markdown": "# Scene report",
                }
            },
        ),
        25: _mcp_success(25, {"structuredContent": {"removed_object_id": "ball-1"}}),
    }


class RemoteMCPLabSmokeTests(unittest.TestCase):
    def test_remote_smoke_success_creates_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = smoke.Path(temp_dir)
            session_dir = temp_root / "mystic_data" / "lab_sessions" / "lab-123"
            session_dir.mkdir(parents=True, exist_ok=True)
            persisted = {
                "session_path": str(session_dir / "session.json"),
                "notebook_path": str(session_dir / "notebook.md"),
                "report_path": str(session_dir / "report.md"),
                "scene_path": str(session_dir / "scene.json"),
                "scene_objects_path": str(session_dir / "scene-objects.json"),
                "scene_simulations_path": str(session_dir / "scene-simulations.json"),
                "scene_report_path": str(session_dir / "scene-report.md"),
                "scene_snapshot_path": str(session_dir / "scene-exports.json"),
            }
            for path_text in persisted.values():
                smoke.Path(path_text).write_text("ok", encoding="utf-8")
            output_path = temp_root / "summary.json"

            responses = _success_responses(persisted, "lab-123")

            with patch.object(smoke, "mcp_request", side_effect=lambda *args, **kwargs: responses[kwargs["request_id"]]):
                summary = smoke.run_remote_mcp_lab_smoke(
                    endpoint="http://127.0.0.1:8765/mcp",
                    session_problem="test problem",
                    domain="math",
                    mode="proof_critical",
                    timeout_seconds=5,
                    output_path=output_path,
                )

            self.assertEqual(summary["final_status"], smoke.READY_LOCAL)
            self.assertTrue(summary["session_created"])
            self.assertTrue(summary["advance_supported"])
            self.assertTrue(summary["advance_ok"])
            self.assertTrue(summary["get_ok"])
            self.assertTrue(summary["report_ok"])
            self.assertEqual(summary["session_id"], "lab-123")
            self.assertTrue(summary["tool_calls"]["lab_agent_run"]["ok"])
            self.assertTrue(summary["tool_calls"]["lab_models_debate"]["ok"])
            self.assertTrue(summary["scene_created"])
            self.assertEqual(summary["scene_id"], "scene-1")
            self.assertTrue(summary["tool_calls"]["run_lab_simulation"]["ok"])
            self.assertTrue(summary["tool_calls"]["generate_lab_report"]["ok"])
            self.assertTrue(output_path.exists())

    def test_remote_smoke_reports_missing_lab_tools(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = smoke.Path(temp_dir) / "summary.json"
            responses = {
                1: _mcp_success(1, {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}}}),
                2: _mcp_success(2, {"tools": [{"name": name} for name in sorted({"mystic_status"})]}),
            }
            with patch.object(smoke, "mcp_request", side_effect=lambda *args, **kwargs: responses[kwargs["request_id"]]):
                summary = smoke.run_remote_mcp_lab_smoke(
                    endpoint="http://127.0.0.1:8765/mcp",
                    session_problem="test problem",
                    domain="math",
                    mode="proof_critical",
                    timeout_seconds=5,
                    output_path=output_path,
                )

            self.assertEqual(summary["final_status"], smoke.MISSING_LAB_TOOLS)
            self.assertIn("lab_session_create", summary["missing_tools"])

    def test_remote_smoke_reports_oauth_required_for_chatgpt_import(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = smoke.Path(temp_dir) / "summary.json"
            response = {
                "status": 401,
                "headers": {
                    "WWW-Authenticate": (
                        'Bearer resource_metadata="https://mystic.dexproject.workers.dev/.well-known/oauth-protected-resource"'
                    )
                },
                "body": {"error": "unauthorized"},
            }
            with patch.object(smoke, "mcp_request", return_value=response):
                summary = smoke.run_remote_mcp_lab_smoke(
                    endpoint="https://mystic.dexproject.workers.dev/mcp",
                    session_problem="test problem",
                    domain="math",
                    mode="proof_critical",
                    timeout_seconds=5,
                    output_path=output_path,
                )

            self.assertEqual(summary["final_status"], smoke.OAUTH_REQUIRED)
            self.assertTrue(summary["auth_required"])
            self.assertTrue(summary["oauth_required"])

    def test_remote_smoke_passes_bearer_token_header(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = smoke.Path(temp_dir)
            session_dir = temp_root / "mystic_data" / "lab_sessions" / "lab-auth"
            session_dir.mkdir(parents=True, exist_ok=True)
            persisted = {
                "session_path": str(session_dir / "session.json"),
                "notebook_path": str(session_dir / "notebook.md"),
                "report_path": str(session_dir / "report.md"),
                "scene_path": str(session_dir / "scene.json"),
                "scene_objects_path": str(session_dir / "scene-objects.json"),
                "scene_simulations_path": str(session_dir / "scene-simulations.json"),
                "scene_report_path": str(session_dir / "scene-report.md"),
                "scene_snapshot_path": str(session_dir / "scene-exports.json"),
            }
            for path_text in persisted.values():
                smoke.Path(path_text).write_text("ok", encoding="utf-8")
            output_path = temp_root / "summary.json"
            seen_headers: list[dict[str, str] | None] = []

            responses = _success_responses(persisted, "lab-auth")

            def fake_mcp_request(*args, **kwargs):  # type: ignore[no-untyped-def]
                seen_headers.append(kwargs.get("headers"))
                return responses[kwargs["request_id"]]

            with patch.object(smoke, "mcp_request", side_effect=fake_mcp_request):
                summary = smoke.run_remote_mcp_lab_smoke(
                    endpoint="https://mystic.dexproject.workers.dev/mcp",
                    bearer_token="secret-token",
                    auth_mode="bearer",
                    session_problem="test problem",
                    domain="math",
                    mode="proof_critical",
                    timeout_seconds=5,
                    output_path=output_path,
                )

            self.assertEqual(summary["final_status"], smoke.READY_PUBLIC)
            self.assertTrue(all(headers == {"Authorization": "Bearer secret-token"} for headers in seen_headers))

    def test_remote_smoke_uses_optional_advance_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = smoke.Path(temp_dir)
            session_dir = temp_root / "mystic_data" / "lab_sessions" / "lab-advance"
            session_dir.mkdir(parents=True, exist_ok=True)
            persisted = {
                "session_path": str(session_dir / "session.json"),
                "notebook_path": str(session_dir / "notebook.md"),
                "report_path": str(session_dir / "report.md"),
                "scene_path": str(session_dir / "scene.json"),
                "scene_objects_path": str(session_dir / "scene-objects.json"),
                "scene_simulations_path": str(session_dir / "scene-simulations.json"),
                "scene_report_path": str(session_dir / "scene-report.md"),
                "scene_snapshot_path": str(session_dir / "scene-exports.json"),
            }
            for path_text in persisted.values():
                smoke.Path(path_text).write_text("ok", encoding="utf-8")
            output_path = temp_root / "summary.json"
            responses = _success_responses(persisted, "lab-advance")
            with patch.object(smoke, "mcp_request", side_effect=lambda *args, **kwargs: responses[kwargs["request_id"]]):
                summary = smoke.run_remote_mcp_lab_smoke(
                    endpoint="http://127.0.0.1:8765/mcp",
                    session_problem="test problem",
                    domain="math",
                    mode="proof_critical",
                    timeout_seconds=5,
                    output_path=output_path,
                )
            self.assertTrue(summary["advance_supported"])
            self.assertTrue(summary["advance_ok"])

    def test_remote_smoke_accepts_supabase_artifact_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = smoke.Path(temp_dir) / "summary.json"
            persisted = {
                "session_path": "supabase://public/lab_sessions/lab-cloud",
                "notebook_path": "supabase://public/lab_sessions/lab-cloud#notebook",
                "report_path": "supabase://public/reports/lab-cloud",
                "scene_path": "supabase://public/lab_scenes/scene-1",
                "scene_objects_path": "supabase://public/lab_scene_objects?scene_id=scene-1",
                "scene_simulations_path": "supabase://public/lab_simulations?scene_id=scene-1",
                "scene_report_path": "supabase://public/lab_scenes/scene-1#report",
                "scene_snapshot_path": "supabase://public/lab_scenes/scene-1#exports",
            }
            responses = _success_responses(persisted, "lab-cloud")
            with patch.object(smoke, "mcp_request", side_effect=lambda *args, **kwargs: responses[kwargs["request_id"]]):
                summary = smoke.run_remote_mcp_lab_smoke(
                    endpoint="https://mystic.dexproject.workers.dev/mcp",
                    bearer_token="secret-token",
                    auth_mode="bearer",
                    session_problem="test problem",
                    domain="math",
                    mode="proof_critical",
                    timeout_seconds=5,
                    output_path=output_path,
                )
            self.assertEqual(summary["final_status"], smoke.READY_PUBLIC)

    def test_remote_smoke_stops_after_auth_required_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = smoke.Path(temp_dir) / "summary.json"
            response = {"status": 401, "headers": {"WWW-Authenticate": "Bearer"}, "body": {"error": "unauthorized"}}
            with patch.object(smoke, "mcp_request", return_value=response) as mocked_request:
                summary = smoke.run_remote_mcp_lab_smoke(
                    endpoint="https://mystic.dexproject.workers.dev/mcp",
                    session_problem="test problem",
                    domain="math",
                    mode="proof_critical",
                    timeout_seconds=5,
                    output_path=output_path,
                )
            self.assertEqual(summary["final_status"], smoke.OAUTH_REQUIRED)
            self.assertEqual(mocked_request.call_count, 1)


if __name__ == "__main__":
    unittest.main()

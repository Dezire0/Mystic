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
        (self.root_path / "mystic_data" / "lab_sessions").mkdir(parents=True, exist_ok=True)

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
                "openai_api": {
                    "provider": "api",
                    "model_name": "gpt-4o-mini",
                    "status": {"state": "disabled", "message": "API provider is disabled by default."},
                    "role_defaults": ["judge"],
                    "enabled": False,
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
        controller: str = "gpt_controller",
    ):
        session_id = "research-test-session"
        session_dir = self.root_path / "mystic_data" / "research_table_sessions" / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        first_participant = participants[0]
        first_model = self.mystic_status()["models"][first_participant]
        payload = {
            "session_id": session_id,
            "problem": problem,
            "participants": participants,
            "participant_models": [
                {
                    "model_id": model_id,
                    "provider": self.mystic_status()["models"][model_id]["provider"],
                    "model_name": self.mystic_status()["models"][model_id]["model_name"],
                }
                for model_id in participants
            ],
            "controller": {"model_id": controller, "provider": "controller", "model_name": "GPT Controller"},
            "rounds": max_rounds,
            "turns": [
                {
                    "turn_id": "turn-1",
                    "round_index": 1,
                    "phase": "independent_discovery",
                    "speaker_type": "model",
                    "speaker_id": first_participant,
                    "provider": first_model["provider"],
                    "model_name": first_model["model_name"],
                    "role": "solver",
                    "status": "DRAFT_ONLY",
                    "content": "Discovery: candidate",
                    "reply_to": [],
                },
                {
                    "turn_id": "turn-2",
                    "round_index": 2,
                    "phase": "tool_verification",
                    "speaker_type": "tool",
                    "speaker_id": "mystic_verify_answer",
                    "provider": "tool",
                    "model_name": "deterministic_verifier",
                    "role": "verifier",
                    "status": "VERIFICATION_RESULT",
                    "content": "Verifier refuted candidate",
                    "reply_to": ["turn-1"],
                },
            ],
            "discoveries": [
                {
                    "discovery_id": "discovery-candidate",
                    "claim": "candidate",
                    "rationale": "from turn 1",
                    "confidence": "low",
                    "needs_verification": True,
                    "status": "refuted",
                    "type": "candidate_answer",
                    "source_turn_id": "turn-1",
                }
            ],
            "verification_requests": [{"tool": "brute_force", "status": "refuted", "question": "Check candidate", "target_turn_id": "turn-1"}],
            "rejected_discoveries": [{"claim": "candidate", "status": "refuted", "type": "candidate_answer", "rationale": "from turn 1"}],
            "final_synthesis_package": {
                "mode": mode,
                "tools": tools,
                "enable_tools": enable_tools,
                "accepted_discoveries": [],
                "rejected_discoveries": [{"claim": "candidate", "status": "refuted", "type": "candidate_answer", "rationale": "from turn 1"}],
                "final_status": "INVALID",
                "final_decision_source": "deterministic_verifier",
            },
        }
        (session_dir / "session.json").write_text(json.dumps(payload), encoding="utf-8")
        (session_dir / "turns.json").write_text(json.dumps(payload["turns"]), encoding="utf-8")
        (session_dir / "discoveries.json").write_text(json.dumps(payload["discoveries"]), encoding="utf-8")
        (session_dir / "verification_requests.json").write_text(json.dumps(payload["verification_requests"]), encoding="utf-8")
        (session_dir / "final_synthesis.json").write_text(json.dumps(payload["final_synthesis_package"]), encoding="utf-8")
        return {"session_id": session_id}

    def mystic_call_model(
        self,
        *,
        model_id: str,
        role: str,
        task: str,
        problem: str,
        context: str = "",
        max_tokens: int | None = None,
        temperature: float | None = None,
    ):
        if model_id == "gemini_cli":
            return {
                "output_id": "auth-required-output",
                "model_id": model_id,
                "provider": "cli",
                "model_name": "gemini_cli",
                "role": role,
                "content": "",
                "status": "AUTH_REQUIRED",
                "latency_sec": 0.01,
                "artifact_path": str(self.root_path / "mystic_data" / "runs" / "auth-required.json"),
                "auth_message": "Login with Google",
            }
        return {
            "output_id": f"{model_id}-{role}",
            "model_id": model_id,
            "provider": self.mystic_status()["models"].get(model_id, {}).get("provider", "ollama"),
            "model_name": self.mystic_status()["models"].get(model_id, {}).get("model_name", model_id),
            "role": role,
            "content": f"{role} response from {model_id}",
            "status": {"critique": "CRITIQUE_ONLY", "revise": "REVISION"}.get(role, "DRAFT_ONLY"),
            "latency_sec": 0.01,
            "artifact_path": str(self.root_path / "mystic_data" / "runs" / f"{model_id}-{role}.json"),
            "auth_message": None,
        }

    def mystic_verify_answer(self, *, problem: str, candidate_answer: str, constraints=None, bounds=None):
        verdict = "VALID" if "existing" in candidate_answer or "candidate" not in candidate_answer else "INVALID"
        reasoning = "Deterministic verifier supported the discovery." if verdict == "VALID" else "Deterministic verifier refuted the discovery."
        return {
            "valid": verdict == "VALID",
            "verdict": verdict,
            "reasoning": reasoning,
            "saved_artifact_path": str(self.root_path / "mystic_data" / "runs" / f"verify-{verdict.lower()}.json"),
        }

    def mystic_import_teacher_label(
        self,
        *,
        packet_id: str,
        label_json: dict[str, object],
        source_model: str,
        target_agent: str,
    ):
        path = self.root_path / "mystic_data" / "teacher_labels" / "saved-from-action.json"
        path.write_text(
            json.dumps(
                {
                    "packet_id": packet_id,
                    "source_model": source_model,
                    "target_agent": target_agent,
                    "label": label_json,
                }
            ),
            encoding="utf-8",
        )
        return {"saved": True, "saved_path": str(path), "label_id": "label-action"}

    def lab_session_create(
        self,
        *,
        problem: str,
        domain: str,
        goal: str,
        mode: str,
        participants: list[str],
    ):
        session_id = "lab-test-session"
        session_dir = self.root_path / "mystic_data" / "lab_sessions" / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "session": {
                "session_id": session_id,
                "problem": problem,
                "domain": domain,
                "goal": goal,
                "mode": mode,
                "status": "created",
                "current_phase": "problem_intake",
                "active_room": "Main Lab Room",
                "participants": [
                    {
                        "model_id": model_id,
                        "provider": self.mystic_status()["models"][model_id]["provider"],
                        "model_name": self.mystic_status()["models"][model_id]["model_name"],
                        "status": self.mystic_status()["models"][model_id]["status"],
                    }
                    for model_id in participants
                ],
                "next_actions": ["Advance to background_scan in Theory Room."],
                "artifact_paths": {},
            },
            "turns": [],
            "claims": [],
            "experiments": [],
            "failures": [],
            "memory_edges": [],
            "notebook_markdown": f"# Lab Notebook {session_id}\n\nProblem: {problem}\n",
            "report_markdown": "",
        }
        self._write_lab_payload(session_id, payload)
        return {"session_id": session_id, "status": "created", "current_phase": "problem_intake", "paths": {"session": str(session_dir / "session.json")}}

    def lab_session_get(self, *, session_id: str):
        payload = self._read_lab_payload(session_id)
        session = payload["session"]
        session["artifact_paths"] = {
            "session": str(self.root_path / "mystic_data" / "lab_sessions" / session_id / "session.json"),
            "turns": str(self.root_path / "mystic_data" / "lab_sessions" / session_id / "turns.json"),
            "claims": str(self.root_path / "mystic_data" / "lab_sessions" / session_id / "claims.json"),
            "experiments": str(self.root_path / "mystic_data" / "lab_sessions" / session_id / "experiments.json"),
            "failures": str(self.root_path / "mystic_data" / "lab_sessions" / session_id / "failures.json"),
            "memory_edges": str(self.root_path / "mystic_data" / "lab_sessions" / session_id / "memory_edges.json"),
            "notebook": str(self.root_path / "mystic_data" / "lab_sessions" / session_id / "notebook.md"),
            "report": str(self.root_path / "mystic_data" / "lab_sessions" / session_id / "report.md"),
        }
        return {
            "session_id": session_id,
            "session": session,
            "turns": payload["turns"],
            "latest_turns": payload["turns"][-10:],
            "claims": payload["claims"],
            "experiments": payload["experiments"],
            "failures": payload["failures"],
            "memory_edges": payload["memory_edges"],
            "next_actions": session.get("next_actions", []),
            "notebook_path": session["artifact_paths"]["notebook"],
            "report_path": session["artifact_paths"]["report"],
            "notebook_markdown": payload["notebook_markdown"],
            "report_markdown": payload["report_markdown"],
        }

    def lab_session_advance(
        self,
        *,
        session_id: str,
        max_steps: int = 1,
        target_phase: str | None = None,
        use_model_arena: bool = False,
        use_verifier: bool = True,
    ):
        payload = self._read_lab_payload(session_id)
        payload["session"]["status"] = "running"
        payload["session"]["current_phase"] = target_phase or "background_scan"
        payload["session"]["active_room"] = "Theory Room"
        payload["session"]["next_actions"] = ["Advance to hypothesis_generation in Hypothesis Chamber."]
        payload["turns"].append(
            {
                "turn_id": "lab-turn-1",
                "session_id": session_id,
                "phase": "background_scan",
                "room": "Theory Room",
                "agent_role": "Theorist",
                "provider": "ollama",
                "model_name": "deepseek-r1-distill-14b",
                "input_summary": "scan background",
                "output": "Observed a bounded integer structure.",
                "extracted_claims": [{"text": "Observed a bounded integer structure.", "claim_type": "observation", "confidence": "medium", "status": "HEURISTIC"}],
                "requested_tools": [],
                "tool_results": [],
                "status": "completed",
                "error": "",
                "reply_to": [],
            }
        )
        payload["claims"].append(
            {
                "claim_id": "lab-claim-1",
                "session_id": session_id,
                "text": "Observed a bounded integer structure.",
                "claim_type": "observation",
                "status": "HEURISTIC",
                "confidence": "medium",
                "source_turn_id": "lab-turn-1",
                "supporting_evidence": [],
                "refuting_evidence": [],
                "related_experiments": [],
                "related_failures": [],
            }
        )
        if use_verifier:
            payload["experiments"].append(
                {
                    "experiment_id": "lab-exp-1",
                    "session_id": session_id,
                    "claim_id": "lab-claim-1",
                    "question": "Test the bounded structure claim.",
                    "method": "python_bruteforce",
                    "inputs": {"candidate_answer": "(2,3,6)"},
                    "outputs": {"verdict": "VALID"},
                    "tool_name": "mystic_verify_answer",
                    "verdict": "supports",
                    "evidence_summary": "Deterministic verifier supported the candidate.",
                }
            )
        self._write_lab_payload(session_id, payload)
        return {"updated_session": payload["session"], "new_turns": payload["turns"][-1:], "new_claims": payload["claims"][-1:], "new_experiments": payload["experiments"][-1:], "new_failures": [], "next_actions": payload["session"]["next_actions"]}

    def lab_models_debate(
        self,
        *,
        session_id: str,
        question: str,
        participants: list[str],
        rounds: list[str],
        use_existing_research_table: bool,
    ):
        payload = self._read_lab_payload(session_id)
        payload["turns"].append(
            {
                "turn_id": "lab-turn-arena",
                "session_id": session_id,
                "phase": "simulation_or_execution",
                "room": "Model Arena",
                "agent_role": "ModelArena",
                "provider": "research_table",
                "model_name": "Research Table",
                "input_summary": question,
                "output": "Imported discoveries from Research Table.",
                "extracted_claims": [],
                "requested_tools": ["mystic_run_research_table"],
                "tool_results": [{"research_table_session_id": "research-test-session"}],
                "status": "completed",
                "error": "",
                "reply_to": [],
            }
        )
        payload["claims"].append(
            {
                "claim_id": "lab-claim-arena",
                "session_id": session_id,
                "text": "Imported Model Arena discovery",
                "claim_type": "result",
                "status": "TESTED",
                "confidence": "medium",
                "source_turn_id": "lab-turn-arena",
                "supporting_evidence": ["research-test-session"],
                "refuting_evidence": [],
                "related_experiments": [],
                "related_failures": [],
            }
        )
        payload["memory_edges"].append(
            {
                "edge_id": "lab-edge-1",
                "session_id": session_id,
                "from_id": "lab-claim-arena",
                "to_id": "research-test-session",
                "relation": "supports",
                "evidence": "Imported from Research Table.",
            }
        )
        payload["session"]["next_actions"] = ["Run referee review on imported claim."]
        self._write_lab_payload(session_id, payload)
        return {"research_table_session_id": "research-test-session", "imported_claims": 1, "imported_failures": 0, "summary": "Imported 1 claim."}

    def lab_report_generate(
        self,
        *,
        session_id: str,
        format: str,
        include_failures: bool,
        include_next_actions: bool,
    ):
        payload = self._read_lab_payload(session_id)
        payload["session"]["status"] = "completed"
        payload["session"]["current_phase"] = "completed"
        payload["session"]["active_room"] = "Paper Room"
        payload["session"]["next_actions"] = []
        payload["report_markdown"] = "# Mystic Lab Report\n\nStructured report generated."
        self._write_lab_payload(session_id, payload)
        report_path = self.root_path / "mystic_data" / "lab_sessions" / session_id / "report.md"
        return {"report_path": str(report_path), "markdown": payload["report_markdown"], "summary": {"surviving_claims": 1}}

    def lab_referee_review(
        self,
        *,
        session_id: str,
        claim_id: str | None,
        text: str,
        strictness: str,
    ):
        payload = self._read_lab_payload(session_id)
        payload["failures"].append(
            {
                "failure_id": "lab-failure-1",
                "session_id": session_id,
                "claim_id": claim_id or "lab-claim-1",
                "source_turn_id": "lab-turn-1",
                "first_fatal_error": "Assumption remains unproven.",
                "failure_type": "logic_gap",
                "lesson": "Referee review found a hidden gap.",
                "reusable_as_training_data": True,
            }
        )
        self._write_lab_payload(session_id, payload)
        return {"verdict": "INVALID", "first_fatal_error": "Assumption remains unproven.", "critique": "Gap found."}

    def lab_experiment_create(
        self,
        *,
        session_id: str,
        claim_id: str,
        question: str,
        method: str,
        inputs: dict[str, object],
    ):
        payload = self._read_lab_payload(session_id)
        payload["experiments"].append(
            {
                "experiment_id": "lab-exp-new",
                "session_id": session_id,
                "claim_id": claim_id,
                "question": question,
                "method": method,
                "inputs": inputs,
                "outputs": {},
                "tool_name": "mystic_verify_answer",
                "verdict": "inconclusive",
                "evidence_summary": "",
            }
        )
        self._write_lab_payload(session_id, payload)
        return {"experiment_id": "lab-exp-new", "status": "inconclusive"}

    def lab_experiment_run(self, *, session_id: str, experiment_id: str, dry_run: bool = False):
        payload = self._read_lab_payload(session_id)
        for experiment in payload["experiments"]:
            if experiment["experiment_id"] == experiment_id:
                experiment["verdict"] = "supports" if not dry_run else "inconclusive"
                experiment["outputs"] = {"verdict": "VALID"} if not dry_run else {}
                experiment["evidence_summary"] = "Deterministic verifier supported the claim." if not dry_run else "Dry-run only."
                break
        self._write_lab_payload(session_id, payload)
        return {"experiment_id": experiment_id, "verdict": "supports" if not dry_run else "inconclusive"}

    def _read_lab_payload(self, session_id: str) -> dict[str, object]:
        session_dir = self.root_path / "mystic_data" / "lab_sessions" / session_id
        return {
            "session": json.loads((session_dir / "session.json").read_text(encoding="utf-8")),
            "turns": json.loads((session_dir / "turns.json").read_text(encoding="utf-8")),
            "claims": json.loads((session_dir / "claims.json").read_text(encoding="utf-8")),
            "experiments": json.loads((session_dir / "experiments.json").read_text(encoding="utf-8")),
            "failures": json.loads((session_dir / "failures.json").read_text(encoding="utf-8")),
            "memory_edges": json.loads((session_dir / "memory_edges.json").read_text(encoding="utf-8")),
            "notebook_markdown": (session_dir / "notebook.md").read_text(encoding="utf-8"),
            "report_markdown": (session_dir / "report.md").read_text(encoding="utf-8"),
        }

    def _write_lab_payload(self, session_id: str, payload: dict[str, object]) -> None:
        session_dir = self.root_path / "mystic_data" / "lab_sessions" / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "session.json").write_text(json.dumps(payload["session"]), encoding="utf-8")
        (session_dir / "turns.json").write_text(json.dumps(payload["turns"]), encoding="utf-8")
        (session_dir / "claims.json").write_text(json.dumps(payload["claims"]), encoding="utf-8")
        (session_dir / "experiments.json").write_text(json.dumps(payload["experiments"]), encoding="utf-8")
        (session_dir / "failures.json").write_text(json.dumps(payload["failures"]), encoding="utf-8")
        (session_dir / "memory_edges.json").write_text(json.dumps(payload["memory_edges"]), encoding="utf-8")
        (session_dir / "notebook.md").write_text(str(payload["notebook_markdown"]), encoding="utf-8")
        (session_dir / "report.md").write_text(str(payload["report_markdown"]), encoding="utf-8")


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
        (self.root / "mystic_data" / "research_table_sessions" / "research-existing" / "turns.json").write_text(
            json.dumps(
                [
                    {
                        "turn_id": "turn-existing",
                        "round_index": 1,
                        "phase": "independent_discovery",
                        "speaker_type": "model",
                        "speaker_id": "claude_cli",
                        "provider": "cli",
                        "model_name": "claude_cli",
                        "role": "solver",
                        "status": "DRAFT_ONLY",
                        "content": "Discovery: existing",
                        "reply_to": [],
                    }
                ]
            ),
            encoding="utf-8",
        )
        (self.root / "mystic_data" / "research_table_sessions" / "research-existing" / "discoveries.json").write_text(
            json.dumps([{"discovery_id": "discovery-existing", "claim": "existing", "rationale": "stored", "confidence": "low", "needs_verification": False, "status": "accepted", "type": "strategy", "source_turn_id": "turn-existing"}]),
            encoding="utf-8",
        )
        (self.root / "mystic_data" / "research_table_sessions" / "research-existing" / "verification_requests.json").write_text(
            json.dumps([{"tool": "brute_force", "status": "verified", "question": "Check existing", "target_turn_id": "turn-existing"}]),
            encoding="utf-8",
        )
        (self.root / "mystic_data" / "research_table_sessions" / "research-existing" / "final_synthesis.json").write_text(
            json.dumps({"accepted_discoveries": [{"claim": "existing", "status": "accepted", "type": "strategy", "rationale": "stored"}], "rejected_discoveries": [], "final_status": "VALID", "final_decision_source": "deterministic_verifier"}),
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

    def test_root_renders_control_panel(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("MysticControlPanel", response.text)
        self.assertIn("Create Lab Session", response.text)
        self.assertIn("Open Model Arena", response.text)

    def test_health_and_mcp_routes_respond(self):
        health = self.client.get("/health")
        rejected_get = self.client.get("/mcp")
        initialize = self.client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        ping = self.client.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "ping"})
        tools = self.client.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        status_call = self.client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "mystic_status", "arguments": {}}},
        )
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "ok")
        self.assertEqual(rejected_get.status_code, 405)
        self.assertEqual(initialize.status_code, 200)
        self.assertEqual(initialize.json()["result"]["serverInfo"]["name"], "mystic-mcp")
        self.assertEqual(ping.status_code, 200)
        self.assertEqual(ping.json()["result"], {})
        self.assertEqual(tools.status_code, 200)
        self.assertIn("tools", tools.json()["result"])
        self.assertEqual(status_call.status_code, 200)
        self.assertIn("structuredContent", status_call.json()["result"])

    def test_start_page_renders_participants_and_auth_cards(self):
        response = self.client.get("/research-table/start")
        self.assertEqual(response.status_code, 200)
        self.assertIn("ResearchTableStartPage", response.text)
        self.assertIn("Gemini CLI", response.text)
        self.assertIn("Claude CLI", response.text)
        self.assertIn("local_prime", response.text)
        self.assertIn("local_raven", response.text)
        self.assertIn("Login with Google", response.text)
        self.assertIn("Login with Claude", response.text)
        self.assertIn("GPT Controller", response.text)
        self.assertNotIn("openai_api", response.text)

    def test_lab_start_page_renders_and_filters_api_provider(self):
        response = self.client.get("/lab/start")
        self.assertEqual(response.status_code, 200)
        self.assertIn("MysticLabStartPage", response.text)
        self.assertIn("Gemini CLI", response.text)
        self.assertIn("Claude CLI", response.text)
        self.assertIn("local_prime", response.text)
        self.assertNotIn("openai_api", response.text)

    def test_lab_run_redirects_to_created_session(self):
        response = self.client.get(
            "/lab/start/run",
            params=[
                ("problem", "Build a proof plan"),
                ("domain", "math"),
                ("goal", "Create a structured lab trace"),
                ("mode", "serious"),
                ("participants", "local_prime"),
                ("participants", "local_qwen"),
            ],
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["location"], "/lab/sessions/lab-test-session")

    def test_lab_session_route_renders_metadata_and_controls(self):
        self.client.get(
            "/lab/start/run",
            params=[
                ("problem", "Build a proof plan"),
                ("domain", "math"),
                ("goal", "Create a structured lab trace"),
                ("mode", "serious"),
                ("participants", "local_prime"),
            ],
            follow_redirects=False,
        )
        response = self.client.get("/lab/sessions/lab-test-session")
        self.assertEqual(response.status_code, 200)
        self.assertIn("MysticLabSessionPage", response.text)
        self.assertIn("Main Lab Room", response.text)
        self.assertIn("Control Panel", response.text)
        self.assertIn("Lab Notebook", response.text)
        self.assertIn("Run Referee Review", response.text)
        self.assertIn("Generate Report", response.text)

    def test_lab_advance_route_updates_session(self):
        self.client.get(
            "/lab/start/run",
            params=[
                ("problem", "Advance me"),
                ("domain", "math"),
                ("goal", "Move through the loop"),
                ("mode", "serious"),
                ("participants", "local_prime"),
            ],
            follow_redirects=False,
        )
        response = self.client.post("/lab/sessions/lab-test-session/advance", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        session = json.loads((self.root / "mystic_data" / "lab_sessions" / "lab-test-session" / "session.json").read_text(encoding="utf-8"))
        turns = json.loads((self.root / "mystic_data" / "lab_sessions" / "lab-test-session" / "turns.json").read_text(encoding="utf-8"))
        self.assertEqual(session["current_phase"], "background_scan")
        self.assertTrue(turns)

    def test_lab_model_arena_and_report_routes_update_artifacts(self):
        self.client.get(
            "/lab/start/run",
            params=[
                ("problem", "Arena problem"),
                ("domain", "math"),
                ("goal", "Import Research Table"),
                ("mode", "multi_model_debate"),
                ("participants", "local_prime"),
                ("participants", "local_raven"),
            ],
            follow_redirects=False,
        )
        arena = self.client.post("/lab/sessions/lab-test-session/model-arena", follow_redirects=False)
        report = self.client.post("/lab/sessions/lab-test-session/report", follow_redirects=False)
        self.assertEqual(arena.status_code, 302)
        self.assertEqual(report.status_code, 302)
        claims = json.loads((self.root / "mystic_data" / "lab_sessions" / "lab-test-session" / "claims.json").read_text(encoding="utf-8"))
        session = json.loads((self.root / "mystic_data" / "lab_sessions" / "lab-test-session" / "session.json").read_text(encoding="utf-8"))
        report_md = (self.root / "mystic_data" / "lab_sessions" / "lab-test-session" / "report.md").read_text(encoding="utf-8")
        self.assertTrue(claims)
        self.assertEqual(session["status"], "completed")
        self.assertIn("Structured report generated", report_md)

    def test_lab_referee_and_experiment_routes_update_detail_state(self):
        self.client.get(
            "/lab/start/run",
            params=[
                ("problem", "Detailed inspection"),
                ("domain", "math"),
                ("goal", "Check failure and experiment displays"),
                ("mode", "proof_critical"),
                ("participants", "local_prime"),
            ],
            follow_redirects=False,
        )
        self.client.post("/lab/sessions/lab-test-session/advance", follow_redirects=False)
        create_exp = self.client.post("/lab/sessions/lab-test-session/experiments/create", follow_redirects=False)
        run_exp = self.client.post("/lab/sessions/lab-test-session/experiments/run-latest", follow_redirects=False)
        referee = self.client.post("/lab/sessions/lab-test-session/referee-review", follow_redirects=False)
        self.assertEqual(create_exp.status_code, 302)
        self.assertEqual(run_exp.status_code, 302)
        self.assertEqual(referee.status_code, 302)
        response = self.client.get("/lab/sessions/lab-test-session")
        self.assertIn("Assumption remains unproven", response.text)
        self.assertIn("Deterministic verifier supported the claim", response.text)

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

    def test_created_research_table_session_shows_selected_participants(self):
        create = self.client.get(
            "/research-table/start/run",
            params=[
                ("problem", "Participant test"),
                ("participants", "local_prime"),
                ("participants", "gemini_cli"),
            ],
            follow_redirects=False,
        )
        self.assertEqual(create.status_code, 302)
        response = self.client.get(create.headers["location"])
        self.assertEqual(response.status_code, 200)
        self.assertIn("Selected Participants", response.text)
        self.assertIn("local_prime", response.text)
        self.assertIn("gemini_cli", response.text)
        self.assertIn("gpt_controller", response.text)

    def test_disabled_api_provider_cannot_be_selected(self):
        response = self.client.get(
            "/research-table/start/run",
            params=[
                ("problem", "Blocked provider test"),
                ("participants", "local_prime"),
                ("participants", "openai_api"),
            ],
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("unavailable", response.text)

    def test_challenge_action_creates_new_reply_turn(self):
        response = self.client.post(
            "/research-table/research-existing/discoveries/discovery-existing/challenge",
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        payload = json.loads((self.root / "mystic_data" / "research_table_sessions" / "research-existing" / "turns.json").read_text(encoding="utf-8"))
        self.assertEqual(payload[-1]["phase"], "interactive_follow_up")
        self.assertIn("turn-existing", payload[-1]["reply_to"])
        self.assertIn("discovery-existing", payload[-1]["reply_to"])

    def test_extend_action_creates_new_reply_turn(self):
        response = self.client.post(
            "/research-table/research-existing/discoveries/discovery-existing/extend",
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        payload = json.loads((self.root / "mystic_data" / "research_table_sessions" / "research-existing" / "turns.json").read_text(encoding="utf-8"))
        self.assertEqual(payload[-1]["phase"], "interactive_follow_up")
        self.assertIn("turn-existing", payload[-1]["reply_to"])

    def test_verify_action_updates_discovery_status(self):
        response = self.client.post(
            "/research-table/research-existing/discoveries/discovery-existing/verify",
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        discoveries = json.loads((self.root / "mystic_data" / "research_table_sessions" / "research-existing" / "discoveries.json").read_text(encoding="utf-8"))
        self.assertEqual(discoveries[0]["status"], "verified")
        turns = json.loads((self.root / "mystic_data" / "research_table_sessions" / "research-existing" / "turns.json").read_text(encoding="utf-8"))
        self.assertEqual(turns[-1]["speaker_type"], "tool")

    def test_save_teacher_label_writes_teacher_labels_directory(self):
        response = self.client.post(
            "/research-table/research-existing/turns/turn-existing/save-teacher-label",
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue((self.root / "mystic_data" / "teacher_labels" / "saved-from-action.json").exists())

    def test_auth_required_action_does_not_crash(self):
        create = self.client.get(
            "/research-table/start/run",
            params=[
                ("problem", "Auth required flow"),
                ("participants", "local_prime"),
                ("participants", "gemini_cli"),
            ],
            follow_redirects=False,
        )
        self.assertEqual(create.status_code, 302)
        response = self.client.post(
            "/research-table/research-test-session/discoveries/discovery-candidate/challenge",
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        turns = json.loads((self.root / "mystic_data" / "research_table_sessions" / "research-test-session" / "turns.json").read_text(encoding="utf-8"))
        self.assertEqual(turns[-1]["status"], "AUTH_REQUIRED")

    def test_existing_research_table_session_route_renders(self):
        response = self.client.get("/research-table/sessions/research-existing")
        self.assertEqual(response.status_code, 200)
        self.assertIn("ResearchTableSessionPage", response.text)
        self.assertIn("Claude CLI", response.text)
        self.assertIn("Accepted Discoveries", response.text)
        self.assertIn("Save as Forge experiment task", response.text)

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

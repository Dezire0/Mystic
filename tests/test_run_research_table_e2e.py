from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts.run_research_table_e2e import run_research_table_e2e
from mystic.research_table.runner import ResearchTableRunner


class _ScenarioRouter:
    def call_model(
        self,
        *,
        model_id: str,
        role: str,
        task: str,
        problem: str,
        context: str = "",
        session_id: str | None = None,
    ) -> dict[str, object]:
        content_map = {
            ("local_prime", "draft"): (
                "Discovery: Candidate answer (2, 3, 6) satisfies the equation.\n"
                "Discovery: Candidate answer (2, 4, 8) is a tempting but suspicious option."
            ),
            ("local_qwen", "draft"): (
                "Discovery: Candidate answer (2, 4, 4) satisfies the equation.\n"
                "Discovery: Candidate answer (3, 3, 3) satisfies the equation."
            ),
            ("local_prime", "critique"): "Critique: Candidate answer (2, 4, 8) fails because 1/2 + 1/4 + 1/8 = 7/8.",
            ("local_qwen", "critique"): "Critique: Verify the full set (2, 3, 6), (2, 4, 4), (3, 3, 3).",
            ("local_prime", "revise"): "Revision: Final candidate set (2, 3, 6), (2, 4, 4), (3, 3, 3).",
            ("local_qwen", "revise"): "Revision: Keep only (2, 3, 6), (2, 4, 4), (3, 3, 3); discard (2, 4, 8).",
        }
        content = content_map.get((model_id, role), f"{model_id} {role} fallback")
        return {
            "output_id": f"{model_id}-{role}",
            "model_id": model_id,
            "provider": "mock",
            "model_name": model_id,
            "role": role,
            "content": content,
            "status": {
                "draft": "DRAFT_ONLY",
                "critique": "CRITIQUE_ONLY",
                "revise": "REVISION",
            }.get(role, "DRAFT_ONLY"),
            "latency_sec": 0.01,
            "artifact_path": str(Path("/tmp") / f"{model_id}-{role}.json"),
        }

    def status_snapshot(self) -> dict[str, dict[str, object]]:
        return {
            "local_prime": {
                "provider": "mock",
                "model_name": "local_prime",
                "role_defaults": ["draft"],
            },
            "local_qwen": {
                "provider": "mock",
                "model_name": "local_qwen",
                "role_defaults": ["draft"],
            },
        }


class _ScenarioToolbox:
    def __init__(self, root_path: Path) -> None:
        self.root_path = Path(root_path)
        self.router = _ScenarioRouter()
        self.runner = ResearchTableRunner(root_path=str(self.root_path), router=self.router, verify_answer=self.mystic_verify_answer)

    def mystic_status(self) -> dict[str, object]:
        return {
            "models": {
                "local_prime": {
                    "provider": "ollama",
                    "model_name": "local_prime",
                    "role_defaults": ["draft"],
                    "enabled": True,
                    "status": {
                        "state": "ready",
                        "message": "ready",
                        "available": True,
                        "authenticated": True,
                    },
                },
                "local_qwen": {
                    "provider": "ollama",
                    "model_name": "local_qwen",
                    "role_defaults": ["draft"],
                    "enabled": True,
                    "status": {
                        "state": "ready",
                        "message": "ready",
                        "available": True,
                        "authenticated": True,
                    },
                },
                "openai_api": {
                    "provider": "api",
                    "model_name": "gpt-4o-mini",
                    "role_defaults": ["draft"],
                    "enabled": False,
                    "status": {
                        "state": "disabled",
                        "message": "API provider is disabled by default.",
                        "available": False,
                        "authenticated": False,
                    },
                },
            },
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
    ) -> dict[str, object]:
        return self.runner.run(
            problem=problem,
            participants=participants,
            mode=mode,
            max_rounds=max_rounds,
            enable_tools=enable_tools,
            tools=tools,
            controller=controller,
        )

    def mystic_call_model(
        self,
        *,
        model_id: str,
        role: str,
        task: str,
        problem: str,
        context: str = "",
        max_tokens=None,
        temperature=None,
    ) -> dict[str, object]:
        return self.router.call_model(
            model_id=model_id,
            role=role,
            task=task,
            problem=problem,
            context=context,
            session_id="interactive",
        )

    def mystic_verify_answer(self, *, problem: str, candidate_answer: str, constraints=None, bounds=None) -> dict[str, object]:
        verdict = "UNKNOWN"
        reasoning = "No deterministic check applied."
        failed: list[str] = []
        passed: list[str] = []
        missing: list[str] = []
        compact = candidate_answer.replace(" ", "")
        if "(2,4,8)" in compact:
            verdict = "INVALID"
            reasoning = "Candidate answer (2, 4, 8) is invalid and misses valid solutions."
            failed = ["(2, 4, 8)"]
            passed = [item for item in ["(2, 3, 6)", "(2, 4, 4)", "(3, 3, 3)"] if item.replace(" ", "") in compact]
            missing = [item for item in ["(2, 3, 6)", "(2, 4, 4)", "(3, 3, 3)"] if item.replace(" ", "") not in compact]
        elif all(item in compact for item in ["(2,3,6)", "(2,4,4)", "(3,3,3)"]):
            verdict = "VALID"
            reasoning = "The complete finite candidate set is correct."
            passed = ["(2, 3, 6)", "(2, 4, 4)", "(3, 3, 3)"]
        elif any(item in compact for item in ["(2,3,6)", "(2,4,4)", "(3,3,3)"]):
            verdict = "UNKNOWN"
            reasoning = "The candidate looks plausible but is not a complete final set."
        artifact = self.root_path / "mystic_data" / "runs" / f"verify-{verdict.lower()}.json"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(json.dumps({"verdict": verdict, "candidate_answer": candidate_answer}, indent=2), encoding="utf-8")
        return {
            "valid": verdict == "VALID",
            "verdict": verdict,
            "failed_candidates": failed,
            "passed_candidates": passed,
            "missing_candidates": missing,
            "constraint_failures": [],
            "reasoning": reasoning,
            "saved_artifact_path": str(artifact),
        }

    def mystic_import_teacher_label(
        self,
        *,
        packet_id: str,
        label_json: dict[str, object],
        source_model: str,
        target_agent: str,
    ) -> dict[str, object]:
        path = self.root_path / "mystic_data" / "teacher_labels" / "label-e2e.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "packet_id": packet_id,
                    "label": label_json,
                    "source_model": source_model,
                    "target_agent": target_agent,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return {
            "saved": True,
            "saved_path": str(path),
            "label_id": "label-e2e",
        }


class RunResearchTableE2ETests(unittest.TestCase):
    def test_e2e_runner_creates_session_files_and_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            summary = run_research_table_e2e(
                root_path=root,
                toolbox=_ScenarioToolbox(root),
                run_id="scenario-one",
            )

            scenario_dir = root / "mystic_data" / "e2e" / "research_table" / "scenario-one"
            self.assertTrue((scenario_dir / "summary.json").exists())
            self.assertTrue((scenario_dir / "session" / "session.json").exists())
            self.assertTrue((scenario_dir / "session" / "turns.json").exists())
            self.assertEqual(summary["session_id"], json.loads((scenario_dir / "session" / "session.json").read_text(encoding="utf-8"))["session_id"])

    def test_expected_candidate_checks_are_recorded(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            summary = run_research_table_e2e(
                root_path=root,
                toolbox=_ScenarioToolbox(root),
                run_id="candidate-checks",
            )

            expected = summary["expected_candidates_found"]
            self.assertEqual(sorted(expected["found_in_session"]), ["(2, 3, 6)", "(2, 4, 4)", "(3, 3, 3)"])
            self.assertEqual(expected["missing_from_session"], [])
            self.assertEqual(summary["final_status"], "VALID")

    def test_bad_candidate_refutation_is_reported(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            summary = run_research_table_e2e(
                root_path=root,
                toolbox=_ScenarioToolbox(root),
                run_id="bad-candidate",
            )

            payload = summary["bad_candidates_refuted"]
            self.assertTrue(payload["appeared_in_session"])
            self.assertTrue(payload["refuted"])
            self.assertGreaterEqual(summary["refuted_discoveries_count"], 1)

    def test_teacher_label_and_training_item_files_are_created(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            summary = run_research_table_e2e(
                root_path=root,
                toolbox=_ScenarioToolbox(root),
                run_id="saved-artifacts",
            )

            self.assertTrue(summary["teacher_labels_created"])
            self.assertTrue(summary["training_items_created"])
            for relative_path in [*summary["teacher_labels_created"], *summary["training_items_created"]]:
                self.assertTrue((root / relative_path).exists())

    def test_unknown_verifier_result_does_not_mark_discovery_verified_or_refuted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            summary = run_research_table_e2e(
                root_path=root,
                toolbox=_ScenarioToolbox(root),
                run_id="unknown-safe",
            )

            self.assertTrue(summary["quality_checks"]["unknown_verifier_does_not_change_status"])


if __name__ == "__main__":
    unittest.main()

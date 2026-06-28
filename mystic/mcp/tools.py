from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import re
import uuid
from typing import Any

from mystic.debate.runner import DebateRunner
from mystic.final_answer_verifier import extract_candidate_tuples, verify_final_answer
from mystic.models.router import ModelRouter
from mystic.research_table.runner import ResearchTableRunner
from mystic.tools.python_runner import PythonRunner
from mystic.verification.integer_bruteforce import search_integer_solutions


ROLE_BY_AGENT = {
    "prime": "draft",
    "forge": "draft",
    "raven": "critique",
    "report": "summarize",
}

DEFAULT_MODEL_BY_AGENT = {
    "prime": "local_prime",
    "forge": "local_forge",
    "raven": "local_raven",
    "report": "local_report",
}


class MysticToolbox:
    def __init__(
        self,
        *,
        root_path: str | Path | None = None,
        router: ModelRouter | None = None,
    ) -> None:
        self.root_path = Path(root_path or Path(__file__).resolve().parents[2])
        self.data_root = self.root_path / "mystic_data"
        self.router = router or ModelRouter(root_path=self.root_path)
        self.python_runner = PythonRunner()
        self.debate_runner = DebateRunner(
            root_path=str(self.root_path),
            router=self.router,
            verify_answer=self.mystic_verify_answer,
        )
        self.research_table_runner = ResearchTableRunner(
            root_path=str(self.root_path),
            router=self.router,
            verify_answer=self.mystic_verify_answer,
        )
        self._ensure_data_dirs()

    def mystic_status(self) -> dict[str, Any]:
        adapters_dir = self.data_root / "adapters"
        datasets = self._dataset_counts()
        recent_runs = self._recent_run_ids(limit=5)
        return {
            "models": self._public_model_status_snapshot(),
            "tools": {
                "mystic_status": "ready",
                "mystic_verify_answer": "ready",
                "mystic_call_model": "ready",
                "mystic_compare_models": "ready",
                "mystic_run_research_table": "ready",
            },
            "datasets": datasets,
            "adapter_status": {
                "available": sorted(path.name for path in adapters_dir.iterdir()) if adapters_dir.exists() else [],
            },
            "recent_runs": recent_runs,
            "recent_errors": [],
            "mcp_server_status": "ready",
        }

    def mystic_verify_answer(
        self,
        *,
        problem: str,
        candidate_answer: str,
        constraints: list[str] | None = None,
        bounds: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        full_problem = problem
        if constraints:
            full_problem = f"{problem}, " + ", ".join(constraints)
        verification = verify_final_answer(problem=full_problem, answer_text=candidate_answer)
        if verification is None and bounds:
            verification = self._bounded_candidate_check(
                problem=full_problem,
                candidate_answer=candidate_answer,
                bounds=bounds,
            )
        if verification is None:
            result = {
                "valid": False,
                "verdict": "UNKNOWN",
                "failed_candidates": [],
                "passed_candidates": [],
                "missing_candidates": [],
                "constraint_failures": [],
                "reasoning": "Mystic could not derive a deterministic verification path from the provided problem.",
            }
        else:
            result = {
                "valid": bool(verification.get("valid", verification.get("verdict") == "VALID")),
                "verdict": verification.get("verdict", "UNKNOWN"),
                "failed_candidates": verification.get("failed_candidates", []),
                "passed_candidates": verification.get("passed_candidates", []),
                "missing_candidates": verification.get("missing_candidates", []),
                "constraint_failures": verification.get("constraint_failures", []),
                "reasoning": verification.get("reasoning", ""),
            }
        artifact_path = self._write_artifact("verification", result)
        result["saved_artifact_path"] = str(artifact_path)
        return result

    def mystic_bruteforce_integer_search(
        self,
        *,
        equation: str,
        variables: list[str],
        constraints: list[str],
        bounds: dict[str, Any],
    ) -> dict[str, Any]:
        problem = ", ".join([equation, *constraints])
        parsed_bounds = {
            variable: self._parse_bounds(bounds.get(variable))
            for variable in variables
        }
        search = search_integer_solutions(
            problem=problem,
            variable_order=variables,
            bounds=parsed_bounds,
        )
        solutions = [
            {variable: value for variable, value in zip(search.variable_order, solution)}
            for solution in search.solutions
        ]
        result = {
            "solutions": solutions,
            "searched_bounds": {key: list(value) for key, value in parsed_bounds.items()},
            "count": search.count,
            "warnings": search.warnings,
        }
        artifact_path = self._write_artifact("integer_search", result)
        result["saved_artifact_path"] = str(artifact_path)
        return result

    def mystic_run_python_check(
        self,
        *,
        code_or_task: str,
        mode: str,
        timeout_seconds: int | None = None,
    ) -> dict[str, Any]:
        timeout = timeout_seconds or 10
        if mode == "task":
            code = self._build_python_task(code_or_task)
            if code is None:
                return {
                    "status": "ERROR",
                    "stdout": "",
                    "stderr": "",
                    "result_summary": (
                        "Task mode supports `evaluate:`, `simplify:`, `factor:`, `expand:`, and "
                        "`solve: <equation> for <variable>`."
                    ),
                    "saved_artifact_path": str(
                        self._write_artifact("python_check", {"mode": mode, "status": "ERROR", "task": code_or_task})
                    ),
                }
        else:
            code = code_or_task
        result = self.python_runner.run(code, timeout_seconds=timeout)
        status = "PASS" if result.success else "FAILED"
        if result.blocked or result.timeout:
            status = "ERROR"
        payload = {
            "status": status,
            "stdout": result.stdout,
            "stderr": result.stderr or result.blocked_reason,
            "result_summary": self._summarize_python_result(result),
        }
        artifact_path = self._write_artifact("python_check", payload)
        payload["saved_artifact_path"] = str(artifact_path)
        return payload

    def mystic_run_local_agent(
        self,
        *,
        agent: str,
        task: str,
        problem: str,
        model: str | None = None,
        context: str = "",
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        if agent not in ROLE_BY_AGENT:
            raise ValueError(f"Unsupported local agent: {agent}")
        model_id = model or DEFAULT_MODEL_BY_AGENT[agent]
        result = self.router.call_model(
            model_id=model_id,
            role=ROLE_BY_AGENT[agent],
            task=task,
            problem=problem,
            context=context,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return {
            "output_id": result["output_id"],
            "agent": agent,
            "provider": result["provider"],
            "model_name": result["model_name"],
            "role": result["role"],
            "output": result["content"],
            "status": result["status"],
            "warnings": [result["auth_message"]] if result.get("auth_message") else [],
            "latency_sec": result["latency_sec"],
            "artifact_path": result["artifact_path"],
        }

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
    ) -> dict[str, Any]:
        return self.router.call_model(
            model_id=model_id,
            role=role,
            task=task,
            problem=problem,
            context=context,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def mystic_compare_models(
        self,
        *,
        problem: str,
        models: list[str],
        task: str,
        include_verifier: bool,
        max_output_chars_per_model: int | None = None,
    ) -> dict[str, Any]:
        session_id = f"compare-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
        selected_models = models[: self.router.policy.max_models_per_compare]
        model_outputs = [
            self.router.call_model(
                model_id=model_id,
                role="draft",
                task=task,
                problem=problem,
                session_id=session_id,
            )
            for model_id in selected_models
        ]
        if max_output_chars_per_model is not None:
            for output in model_outputs:
                if len(output["content"]) > max_output_chars_per_model:
                    output["content"] = output["content"][:max_output_chars_per_model]
        tool_checks: list[dict[str, Any]] = []
        if include_verifier:
            verification = self.mystic_verify_answer(
                problem=problem,
                candidate_answer="\n\n".join(output["content"] for output in model_outputs),
            )
            tool_checks.append(
                {
                    "tool_name": "python_verifier",
                    "status": verification["verdict"],
                    "content": verification["reasoning"],
                    "structured_result": verification,
                }
            )
            final_status = verification["verdict"]
            final_decision_source = "deterministic_verifier"
        else:
            verification = None
            final_status = "MODEL_OUTPUTS_ONLY"
            final_decision_source = "model_outputs"
        display_blocks = []
        for output in model_outputs:
            display_blocks.append(
                "\n".join(
                    [
                        f"[{output['model_id']} / {output['provider']} / {output['model_name']} / {output['role']} / {output['status']}]",
                        output["content"],
                    ]
                )
            )
        for check in tool_checks:
            display_blocks.append(
                "\n".join(
                    [
                        f"[{check['tool_name']} / tool / deterministic_check / verifier / {check['status']}]",
                        check["content"],
                    ]
                )
            )
        result = {
            "session_id": session_id,
            "problem": problem,
            "model_outputs": model_outputs,
            "tool_checks": tool_checks,
            "verification": verification,
            "final_status": final_status,
            "final_decision_source": final_decision_source,
            "display_text": "\n\n".join(display_blocks),
        }
        artifact_path = self._write_artifact("compare", result, session_id=session_id)
        result["saved_artifact_path"] = str(artifact_path)
        return result

    def mystic_run_debate(
        self,
        *,
        problem: str,
        participants: list[dict[str, Any]],
        rounds: int,
        tools: list[str],
        judge: str = "gpt_controller",
        max_turns: int | None = None,
    ) -> dict[str, Any]:
        return self.debate_runner.run(
            problem=problem,
            participants=participants,
            rounds=rounds,
            tools=tools,
            judge=judge,
            max_turns=max_turns or self.router.policy.max_turns_per_debate,
        )

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
    ) -> dict[str, Any]:
        return self.research_table_runner.run(
            problem=problem,
            participants=participants,
            mode=mode,
            max_rounds=max_rounds,
            enable_tools=enable_tools,
            tools=tools,
            controller=controller,
        )

    def mystic_export_teacher_packet(
        self,
        *,
        limit: int,
        filter: str,
        target_agent: str | None = None,
    ) -> dict[str, Any]:
        cases = self._collect_teacher_cases(limit=limit, filter_text=filter, target_agent=target_agent)
        packet_id = f"packet-{uuid.uuid4().hex[:10]}"
        payload = {
            "packet_id": packet_id,
            "filter": filter,
            "target_agent": target_agent,
            "cases": cases,
            "requested_strict_json_label_schema": {
                "verdict": [
                    "VALID_COMPLETE_PROOF",
                    "INVALID",
                    "PARTIAL_RESULT_ONLY",
                    "INTERESTING_BUT_UNPROVEN_FRAMEWORK",
                    "UNCLEAR",
                    "NEEDS_MORE_DETAIL",
                ],
                "first_fatal_error": "string",
                "critique": "string",
                "corrected_reasoning": "string",
                "training_target": "string",
                "training_value": ["high", "medium", "low"],
            },
        }
        path = self.data_root / "teacher_packets" / f"{packet_id}.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return {
            "packet_id": packet_id,
            "content": json.dumps(payload, indent=2),
            "cases": cases,
            "saved_path": str(path),
        }

    def mystic_import_teacher_label(
        self,
        *,
        packet_id: str,
        label_json: dict[str, Any],
        source_model: str,
        target_agent: str,
    ) -> dict[str, Any]:
        label_id = f"label-{uuid.uuid4().hex[:10]}"
        payload = {
            "label_id": label_id,
            "packet_id": packet_id,
            "source_model": source_model,
            "target_agent": target_agent,
            "label": label_json,
            "created_at": datetime.now(UTC).isoformat(),
        }
        path = self.data_root / "teacher_labels" / f"{label_id}.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return {
            "saved": True,
            "saved_path": str(path),
            "label_id": label_id,
        }

    def _bounded_candidate_check(
        self,
        *,
        problem: str,
        candidate_answer: str,
        bounds: dict[str, Any],
    ) -> dict[str, Any] | None:
        candidates = extract_candidate_tuples(candidate_answer)
        if not candidates:
            return None
        variable_order = self._infer_variable_order_from_bounds(bounds, len(candidates[0]))
        if len(variable_order) != len(candidates[0]):
            return None
        search = search_integer_solutions(
            problem=problem,
            variable_order=variable_order,
            bounds={name: self._parse_bounds(bounds[name]) for name in variable_order},
        )
        valid_set = set(search.solutions)
        candidate_set = set(candidates)
        invalid = sorted(candidate_set - valid_set)
        missing = sorted(valid_set - candidate_set)
        if not invalid and not missing:
            return {
                "valid": True,
                "verdict": "VALID",
                "failed_candidates": [],
                "passed_candidates": [str(item) for item in sorted(candidate_set)],
                "missing_candidates": [],
                "constraint_failures": [],
                "reasoning": "Bounded integer search confirmed the candidate set within supplied bounds.",
            }
        return {
            "valid": False,
            "verdict": "INVALID",
            "failed_candidates": [str(item) for item in invalid],
            "passed_candidates": [str(item) for item in sorted(candidate_set & valid_set)],
            "missing_candidates": [str(item) for item in missing],
            "constraint_failures": [],
            "reasoning": "Bounded integer search found missing or invalid candidates within supplied bounds.",
        }

    @staticmethod
    def _infer_variable_order_from_bounds(bounds: dict[str, Any], tuple_width: int) -> list[str]:
        variables = [str(key) for key in bounds.keys()]
        return variables[:tuple_width]

    def _public_model_status_snapshot(self) -> dict[str, Any]:
        snapshot = self.router.status_snapshot()
        sanitized: dict[str, Any] = {}
        for model_id, payload in snapshot.items():
            status = payload.get("status", {})
            sanitized[model_id] = {
                "provider": payload.get("provider", ""),
                "model_name": payload.get("model_name", model_id),
                "status": {
                    "state": status.get("state", "unknown"),
                    "message": status.get("message", ""),
                    "available": bool(status.get("available", False)),
                    "authenticated": bool(status.get("authenticated", False)),
                },
                "role_defaults": payload.get("role_defaults", []),
                "enabled": bool(payload.get("enabled", True)),
            }
        return sanitized

    @staticmethod
    def _parse_bounds(raw: Any) -> tuple[int, int]:
        if isinstance(raw, list) and len(raw) == 2:
            return int(raw[0]), int(raw[1])
        if isinstance(raw, dict):
            if "min" in raw and "max" in raw:
                return int(raw["min"]), int(raw["max"])
            if "lower" in raw and "upper" in raw:
                return int(raw["lower"]), int(raw["upper"])
        raise ValueError(f"Unsupported bounds shape: {raw}")

    def _dataset_counts(self) -> dict[str, int]:
        internal_dir = self.data_root / "internal"
        counts: dict[str, int] = {}
        if not internal_dir.exists():
            return counts
        for path in internal_dir.glob("*.jsonl"):
            counts[path.stem] = self._count_lines(path)
        return counts

    def _recent_run_ids(self, *, limit: int) -> list[str]:
        runs_dir = self.data_root / "runs"
        if not runs_dir.exists():
            return []
        recent = sorted((path.name for path in runs_dir.iterdir() if path.is_dir()), reverse=True)
        return recent[:limit]

    @staticmethod
    def _count_lines(path: Path) -> int:
        return sum(1 for _ in path.open("r", encoding="utf-8"))

    @staticmethod
    def _summarize_python_result(result: Any) -> str:
        if result.blocked:
            return f"Blocked: {result.blocked_reason}"
        if result.timeout:
            return "Timed out."
        if result.success:
            return "Python check passed."
        return f"Python check failed with code {result.returncode}."

    def _write_artifact(
        self,
        artifact_type: str,
        payload: dict[str, Any],
        *,
        session_id: str | None = None,
    ) -> Path:
        session = session_id or f"{artifact_type}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
        artifact_dir = self.data_root / "runs" / session / "tool_checks"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = artifact_dir / f"{artifact_type}-{uuid.uuid4().hex[:8]}.json"
        artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return artifact_path

    def _ensure_data_dirs(self) -> None:
        for relative in [
            "runs",
            "debate_sessions",
            "research_table_sessions",
            "teacher_packets",
            "teacher_labels",
            "adapters",
            "cycles",
            "archive",
        ]:
            (self.data_root / relative).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _build_python_task(task: str) -> str | None:
        stripped = task.strip()
        lowered = stripped.lower()
        if lowered.startswith("simplify:"):
            expr = stripped.split(":", 1)[1].strip()
            return (
                "from sympy import sympify, simplify\n"
                f"expr = sympify({expr!r})\n"
                "print(simplify(expr))\n"
            )
        if lowered.startswith("factor:"):
            expr = stripped.split(":", 1)[1].strip()
            return (
                "from sympy import sympify, factor\n"
                f"expr = sympify({expr!r})\n"
                "print(factor(expr))\n"
            )
        if lowered.startswith("expand:"):
            expr = stripped.split(":", 1)[1].strip()
            return (
                "from sympy import sympify, expand\n"
                f"expr = sympify({expr!r})\n"
                "print(expand(expr))\n"
            )
        if lowered.startswith("evaluate:"):
            expr = stripped.split(":", 1)[1].strip()
            return f"print({expr})\n"
        solve_match = re.match(r"solve:\s*(.+?)\s+for\s+([A-Za-z_][A-Za-z0-9_]*)\s*$", stripped, re.IGNORECASE)
        if solve_match:
            equation = solve_match.group(1).strip()
            variable = solve_match.group(2).strip()
            if "=" in equation:
                left, right = equation.split("=", 1)
                return (
                    "from sympy import Eq, Symbol, solve, sympify\n"
                    f"{variable} = Symbol({variable!r})\n"
                    f"equation = Eq(sympify({left.strip()!r}), sympify({right.strip()!r}))\n"
                    f"print(solve(equation, {variable}))\n"
                )
        return None

    def _collect_teacher_cases(self, *, limit: int, filter_text: str, target_agent: str | None) -> list[dict[str, Any]]:
        runs_dir = self.data_root / "runs"
        cases: list[dict[str, Any]] = []
        if not runs_dir.exists():
            return cases
        for path in sorted(runs_dir.rglob("*.json"), reverse=True):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            serialized = json.dumps(payload, ensure_ascii=False)
            if filter_text and filter_text.lower() not in serialized.lower():
                continue
            model_id = str(payload.get("model_id", ""))
            if target_agent and target_agent not in model_id and target_agent not in serialized:
                continue
            cases.append(
                {
                    "problem": payload.get("problem", payload.get("task", "")),
                    "local_model_output": payload.get("content", ""),
                    "verifier_result": payload.get("status", ""),
                    "critique_result": payload.get("summary", ""),
                    "known_failure": payload.get("auth_message", ""),
                    "source_path": str(path),
                }
            )
            if len(cases) >= limit:
                break
        return cases

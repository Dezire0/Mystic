"""Mystic orchestration flow."""

from __future__ import annotations

import os
from pathlib import Path

from mystic.agents import AGENT_TYPES, CoreAgent, ReportAgent
from mystic.core.model_registry import ModelRegistry
from mystic.core.protocol import AgentOutput, SessionRunResult
from mystic.core.router import RuleRouter
from mystic.memory.archive import ArchiveStore
from mystic.tools.lean_runner import LeanRunner
from mystic.tools.python_runner import PythonRunner


class MysticOrchestrator:
    def __init__(self, root_path: str | Path | None = None) -> None:
        self.root_path = Path(root_path or Path(__file__).resolve().parents[2])
        data_dir = Path(os.getenv("MYSTIC_DATA_DIR", self.root_path / "data"))
        db_path = Path(os.getenv("MYSTIC_DB_PATH", data_dir / "mystic.sqlite3"))
        self.registry = ModelRegistry(self.root_path / "configs" / "model_config.yaml")
        self.router = RuleRouter(self.root_path / "configs" / "router_config.yaml")
        self.archive = ArchiveStore(db_path)
        self.python_runner = PythonRunner()
        self.lean_runner = LeanRunner()
        self.core_agent = CoreAgent(self.registry, self.root_path)
        self.report_agent = ReportAgent(self.registry, self.root_path)

    def init_workspace(self) -> str:
        self.archive.db._initialize()
        return str(self.archive.db.path)

    def run_problem(self, problem: str) -> SessionRunResult:
        session_id = self.archive.create_session(problem)
        core_plan = self.core_agent.run(problem)
        core_settings = self.registry.get_agent_settings("core")
        self.archive.record_core_plan(session_id, core_plan, core_settings, problem)

        selected_agents = self._merge_agents(core_plan.agents_to_call, self.router.route(problem))
        outputs: list[AgentOutput] = []
        experiment_result = None
        lean_summary = ""

        for agent_name in selected_agents:
            agent = AGENT_TYPES[agent_name](self.registry, self.root_path)
            output = agent.run(problem, core_plan, outputs)
            settings = self.registry.get_agent_settings(agent_name)
            self.archive.record_agent_output(session_id, problem, output, settings)
            outputs.append(output)

            if agent_name == "forge" and output.experiment:
                experiment_result = self.python_runner.run(output.experiment)
                self.archive.record_experiment(session_id, agent_name, output.experiment, experiment_result)

            if agent_name == "lean" and output.formalization:
                lean_summary = self.lean_runner.run(output.formalization)
                self.archive.record_lean_attempt(session_id, output.formalization, lean_summary)

        for support_agent_name in ["archive", "knowledge_graph", "evolution"]:
            agent = AGENT_TYPES[support_agent_name](self.registry, self.root_path)
            output = agent.run(problem, core_plan, outputs)
            settings = self.registry.get_agent_settings(support_agent_name)
            self.archive.record_agent_output(session_id, problem, output, settings)
            outputs.append(output)

        export_paths = self.archive.export_dataset("all")
        report_output, report_text = self.report_agent.build(
            problem,
            core_plan,
            outputs,
            experiment_result,
            lean_summary,
            export_paths,
        )
        report_settings = self.registry.get_agent_settings("report")
        self.archive.record_agent_output(session_id, problem, report_output, report_settings)
        self.archive.record_report(session_id, report_text)
        self.archive.mark_session_complete(session_id)
        outputs.append(report_output)

        return SessionRunResult(
            session_id=session_id,
            core_plan=core_plan,
            selected_agents=selected_agents,
            agent_outputs=outputs,
            report_text=report_text,
            export_paths=export_paths,
        )

    def list_sessions(self) -> list[dict]:
        return self.archive.list_sessions()

    def get_session(self, session_id: str) -> dict:
        return self.archive.get_session(session_id)

    def export_dataset(self, export_type: str) -> list[str]:
        return self.archive.export_dataset(export_type)

    def available_agents(self) -> dict[str, dict]:
        agents = {}
        for name, settings in self.registry.list_agents().items():
            agents[name] = {
                "provider": settings.provider,
                "model": settings.model,
                "adapter": settings.adapter,
                "temperature": settings.temperature,
            }
        return agents

    def config_snapshot(self) -> dict:
        return {
            "model_config": self.available_agents(),
            "router_configured_agents": list(self.router.routes.keys()),
            "database_path": str(self.archive.db.path),
        }

    @staticmethod
    def _merge_agents(primary: list[str], secondary: list[str]) -> list[str]:
        ordered = []
        for agent_name in primary + secondary:
            if agent_name in AGENT_TYPES and agent_name not in ordered:
                ordered.append(agent_name)
        return ordered


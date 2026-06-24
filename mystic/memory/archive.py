"""Archive storage for Mystic sessions and agent outputs."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4
from datetime import UTC, datetime

from mystic.core.protocol import AgentOutput, CorePlan, ModelSettings, PythonExecutionResult
from mystic.memory.db import Database


class ArchiveStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db = Database(db_path)
        self.data_dir = Path(db_path).resolve().parent
        self.export_dir = self.data_dir / "exports"
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def create_session(self, problem: str) -> str:
        session_id = uuid4().hex[:12]
        with self.db.session() as connection:
            connection.execute(
                "INSERT INTO research_sessions (session_id, problem, status, created_at) VALUES (?, ?, ?, ?)",
                (session_id, problem, "created", _now()),
            )
            connection.commit()
        return session_id

    def mark_session_complete(self, session_id: str) -> None:
        with self.db.session() as connection:
            connection.execute(
                "UPDATE research_sessions SET status = ? WHERE session_id = ?",
                ("completed", session_id),
            )
            connection.commit()

    def record_core_plan(self, session_id: str, plan: CorePlan, settings: ModelSettings, problem: str) -> None:
        payload = plan.to_dict()
        with self.db.session() as connection:
            connection.execute(
                """
                INSERT INTO agent_messages (
                    session_id, agent_name, division, model_provider, model_name, adapter_name,
                    input_text, output_text, structured_output, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    "core",
                    "core",
                    settings.provider,
                    settings.model,
                    settings.adapter,
                    problem,
                    plan.to_archive_text(),
                    json.dumps(payload),
                    _now(),
                ),
            )
            connection.commit()

    def record_agent_output(self, session_id: str, problem: str, output: AgentOutput, settings: ModelSettings) -> None:
        structured = output.to_structured_dict()
        with self.db.session() as connection:
            connection.execute(
                """
                INSERT INTO agent_messages (
                    session_id, agent_name, division, model_provider, model_name, adapter_name,
                    input_text, output_text, structured_output, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    output.agent,
                    output.division,
                    settings.provider,
                    settings.model,
                    settings.adapter,
                    problem,
                    output.to_archive_text(),
                    json.dumps(structured),
                    _now(),
                ),
            )
            connection.execute(
                "INSERT INTO claims (session_id, agent_name, status, claim_text, created_at) VALUES (?, ?, ?, ?, ?)",
                (session_id, output.agent, output.status, output.claim, _now()),
            )
            if output.agent == "raven":
                connection.execute(
                    "INSERT INTO raven_critiques (session_id, critique_text, created_at) VALUES (?, ?, ?)",
                    (session_id, output.reasoning, _now()),
                )
            connection.commit()

    def record_experiment(
        self,
        session_id: str,
        agent_name: str,
        code: str,
        result: PythonExecutionResult,
    ) -> None:
        with self.db.session() as connection:
            connection.execute(
                "INSERT INTO experiments (session_id, agent_name, code, result_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (session_id, agent_name, code, json.dumps(result.to_dict()), _now()),
            )
            connection.commit()

    def record_lean_attempt(self, session_id: str, attempt_text: str, result_text: str) -> None:
        with self.db.session() as connection:
            connection.execute(
                "INSERT INTO lean_attempts (session_id, attempt_text, result_text, created_at) VALUES (?, ?, ?, ?)",
                (session_id, attempt_text, result_text, _now()),
            )
            connection.commit()

    def record_report(self, session_id: str, report_text: str) -> None:
        with self.db.session() as connection:
            connection.execute(
                "INSERT INTO reports (session_id, report_text, created_at) VALUES (?, ?, ?)",
                (session_id, report_text, _now()),
            )
            connection.commit()

    def list_sessions(self) -> list[dict]:
        with self.db.session() as connection:
            rows = connection.execute(
                "SELECT session_id, problem, status, created_at FROM research_sessions ORDER BY created_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_session(self, session_id: str) -> dict:
        with self.db.session() as connection:
            session = connection.execute(
                "SELECT session_id, problem, status, created_at FROM research_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if session is None:
                raise KeyError(f"Unknown session: {session_id}")
            messages = connection.execute(
                """
                SELECT agent_name, division, model_provider, model_name, adapter_name, output_text, created_at
                FROM agent_messages
                WHERE session_id = ?
                ORDER BY id ASC
                """,
                (session_id,),
            ).fetchall()
            reports = connection.execute(
                "SELECT report_text, created_at FROM reports WHERE session_id = ? ORDER BY id DESC",
                (session_id,),
            ).fetchall()
        return {
            "session": dict(session),
            "messages": [dict(row) for row in messages],
            "reports": [dict(row) for row in reports],
        }

    def export_dataset(self, export_type: str) -> list[str]:
        with self.db.session() as connection:
            rows = connection.execute(
                """
                SELECT session_id, agent_name, division, model_name, adapter_name, input_text, output_text, structured_output
                FROM agent_messages
                ORDER BY id ASC
                """
            ).fetchall()

        grouped: dict[str, list[dict]] = {}
        for row in rows:
            agent_name = row["agent_name"]
            if export_type != "all" and agent_name != export_type:
                continue
            grouped.setdefault(agent_name, []).append(
                {
                    "agent": agent_name,
                    "division": row["division"],
                    "instruction": f"{agent_name} dataset export",
                    "input": row["input_text"],
                    "output": row["output_text"],
                    "status": _extract_status(row["structured_output"]),
                    "metadata": {
                        "session_id": row["session_id"],
                        "model": row["model_name"],
                        "adapter": row["adapter_name"],
                    },
                }
            )

        paths: list[str] = []
        for agent_name, items in grouped.items():
            path = self.export_dir / f"{agent_name}_dataset.jsonl"
            path.write_text(
                "\n".join(json.dumps(item, ensure_ascii=True) for item in items) + ("\n" if items else ""),
                encoding="utf-8",
            )
            paths.append(str(path))
            with self.db.session() as connection:
                connection.execute(
                    "INSERT INTO dataset_exports (session_id, export_type, export_path, created_at) VALUES (?, ?, ?, ?)",
                    (None, agent_name, str(path), _now()),
                )
                connection.commit()
        return paths


def _extract_status(raw_structured_output: str) -> str:
    try:
        payload = json.loads(raw_structured_output)
    except json.JSONDecodeError:
        return "UNKNOWN"
    return str(payload.get("STATUS", "UNKNOWN"))


def _now() -> str:
    return datetime.now(UTC).isoformat()

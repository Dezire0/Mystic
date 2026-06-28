"""FastAPI endpoints for Mystic."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil

try:
    from fastapi import FastAPI, HTTPException, Request, Response
    from fastapi.responses import HTMLResponse, RedirectResponse
except ImportError:  # pragma: no cover
    FastAPI = None
    HTTPException = RuntimeError
    Request = RuntimeError
    Response = RuntimeError
    HTMLResponse = None
    RedirectResponse = None

from mystic.app.pages import (
    DebateSessionPage,
    ModelComparePage,
    ResearchTableSessionPage,
    ResearchTableStartPage,
    SessionDetailPage,
    TeacherLabelsPage,
)
from mystic.app.components import ProviderAuthCard
from mystic.mcp.tools import MysticToolbox
from mystic.mcp.server import MysticMCPServer
from mystic.core.orchestrator import MysticOrchestrator


def create_app(
    *,
    root_path: Path | None = None,
    orchestrator: MysticOrchestrator | None = None,
    toolbox: MysticToolbox | None = None,
):
    if FastAPI is None:  # pragma: no cover
        raise RuntimeError("fastapi is not installed; install mystic[api] to use the API")

    app = FastAPI(title="Mystic API", version="0.1.0")
    source_root = Path(root_path or Path(__file__).resolve().parents[2])
    root_path = _resolve_runtime_root(source_root)
    orchestrator = orchestrator or MysticOrchestrator(root_path=root_path)
    toolbox = toolbox or MysticToolbox(root_path=root_path)
    mcp_server = MysticMCPServer(toolbox=toolbox)

    @app.get("/", response_class=HTMLResponse)
    def home():
        return RedirectResponse(url="/research-table/start", status_code=302)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/mcp")
    def mcp_http(payload: dict):
        response = mcp_server.handle_request(payload)
        if response is None:
            return Response(status_code=202)
        return response

    @app.get("/research-table/start", response_class=HTMLResponse)
    def research_table_start():
        status = toolbox.mystic_status()
        participants = _participant_options(status)
        auth_cards = [
            ProviderAuthCard(
                model_id=model_id,
                status=model_status["status"],
                action_href=f"/providers/auth/{model_id}",
            )
            for model_id, model_status in status["models"].items()
            if model_status["provider"] == "cli" and model_status["status"]["state"] == "not_authenticated"
        ]
        return ResearchTableStartPage(participants=participants, auth_cards=auth_cards)

    @app.get("/research-table/start/run", response_class=HTMLResponse)
    def research_table_run(
        request: Request,
        problem: str,
        mode: str = "discovery_debate",
        max_rounds: int = 3,
        num_models: int = 3,
    ):
        selected = request.query_params.getlist("participants")[: max(2, min(num_models, 4))]
        if not problem.strip():
            raise HTTPException(status_code=400, detail="problem is required")
        if len(selected) < 2:
            raise HTTPException(status_code=400, detail="at least two participants are required")
        session = toolbox.mystic_run_research_table(
            problem=problem,
            participants=selected,
            mode=mode,
            max_rounds=max_rounds,
            enable_tools=True,
            tools=["mystic_verify_answer"],
        )
        return RedirectResponse(url=f"/research-table/sessions/{session['session_id']}", status_code=302)

    @app.get("/research-table/sessions/{session_id}", response_class=HTMLResponse)
    def research_table_session(session_id: str):
        session = _load_json(root_path / "mystic_data/research_table_sessions" / session_id / "session.json")
        return ResearchTableSessionPage(session=session)

    @app.get("/debate/sessions/{session_id}", response_class=HTMLResponse)
    def debate_session(session_id: str):
        session = _load_json(root_path / "mystic_data/debate_sessions" / session_id / "session.json")
        return DebateSessionPage(session=session)

    @app.get("/model-compare", response_class=HTMLResponse)
    def model_compare():
        comparisons = _load_tool_results(root_path / "mystic_data/runs", prefix="compare")
        return ModelComparePage(comparisons=comparisons)

    @app.get("/teacher-labels", response_class=HTMLResponse)
    def teacher_labels():
        packets = _load_json_dir(root_path / "mystic_data/teacher_packets")
        labels = _load_json_dir(root_path / "mystic_data/teacher_labels")
        return TeacherLabelsPage(packets=packets, labels=labels)

    @app.get("/sessions/detail", response_class=HTMLResponse)
    def session_detail():
        sessions = _collect_session_index(root_path)
        return SessionDetailPage(sessions=sessions)

    @app.post("/sessions")
    def create_session(payload: dict):
        problem = str(payload.get("problem", "")).strip()
        if not problem:
            raise HTTPException(status_code=400, detail="problem is required")
        result = orchestrator.run_problem(problem)
        return {"session_id": result.session_id, "selected_agents": result.selected_agents}

    @app.post("/sessions/{session_id}/run")
    def rerun_session(session_id: str, payload: dict):
        problem = str(payload.get("problem", "")).strip()
        if not problem:
            raise HTTPException(status_code=400, detail="problem is required")
        result = orchestrator.run_problem(problem)
        return {"requested_session_id": session_id, "new_session_id": result.session_id}

    @app.get("/sessions")
    def list_sessions():
        return orchestrator.list_sessions()

    @app.get("/agents")
    def list_agents():
        return orchestrator.available_agents()

    @app.get("/config/models")
    def get_model_config():
        return orchestrator.available_agents()

    @app.post("/datasets/export")
    def export_datasets(payload: dict):
        kind = str(payload.get("kind", "all"))
        return {"paths": orchestrator.export_dataset(kind)}

    @app.get("/sessions/{session_id}")
    def get_session(session_id: str):
        try:
            return orchestrator.get_session(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/providers/auth/{model_id}", response_class=HTMLResponse)
    def provider_auth(model_id: str):
        status = toolbox.mystic_status()["models"].get(model_id)
        if status is None:
            raise HTTPException(status_code=404, detail=f"unknown model: {model_id}")
        from mystic.app.pages import ProviderAuthPage

        return ProviderAuthPage(model_id=model_id, status=status["status"])

    return app


def _participant_options(status: dict) -> list[dict]:
    options = []
    preferred = ["local_prime", "local_qwen", "local_raven", "gemini_cli", "claude_cli"]
    for model_id in preferred:
        model = status["models"].get(model_id)
        if model is None:
            continue
        options.append(
            {
                "model_id": model_id,
                "label": _participant_label(model_id),
                "provider": model["provider"],
                "model_name": model["model_name"],
                "roles": model.get("role_defaults", []),
                "auth_state": model["status"]["state"],
                "checked": model_id in {"local_prime", "local_qwen", "local_raven"},
            }
        )
    return options


def _participant_label(model_id: str) -> str:
    labels = {
        "local_prime": "Local DeepSeek-R1-Distill-14B",
        "local_qwen": "Local Qwen3-14B",
        "local_raven": "Local Raven LoRA",
        "gemini_cli": "Gemini CLI",
        "claude_cli": "Claude CLI",
    }
    return labels.get(model_id, model_id)


def _resolve_runtime_root(source_root: Path) -> Path:
    if not os.getenv("VERCEL"):
        return source_root

    runtime_root = Path(os.getenv("MYSTIC_RUNTIME_ROOT", "/tmp/mystic_runtime"))
    shutil.copytree(source_root / "configs", runtime_root / "configs", dirs_exist_ok=True)
    if (source_root / "mystic_data").exists():
        shutil.copytree(source_root / "mystic_data", runtime_root / "mystic_data", dirs_exist_ok=True)
    else:
        (runtime_root / "mystic_data").mkdir(parents=True, exist_ok=True)

    data_root = runtime_root / "data"
    data_root.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MYSTIC_DATA_DIR", str(data_root))
    os.environ.setdefault("MYSTIC_DB_PATH", str(data_root / "mystic.sqlite3"))
    return runtime_root


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"session file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_json_dir(path: Path) -> list[dict]:
    if not path.exists():
        return []
    payloads = []
    for item in sorted(path.glob("*.json"), reverse=True):
        try:
            payload = json.loads(item.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        payloads.append(payload)
    return payloads


def _load_tool_results(path: Path, *, prefix: str) -> list[dict]:
    if not path.exists():
        return []
    payloads = []
    for item in sorted(path.rglob(f"{prefix}-*.json"), reverse=True):
        try:
            payload = json.loads(item.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        payloads.append(payload)
    return payloads[:10]


def _collect_session_index(root_path: Path) -> list[dict]:
    sessions: list[dict] = []
    for session_type, base in [
        ("research_table", root_path / "mystic_data/research_table_sessions"),
        ("debate", root_path / "mystic_data/debate_sessions"),
    ]:
        if not base.exists():
            continue
        for item in sorted(base.iterdir(), reverse=True):
            session_path = item / "session.json"
            if not session_path.exists():
                continue
            try:
                payload = json.loads(session_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            sessions.append(
                {
                    "type": session_type,
                    "session_id": payload.get("session_id", item.name),
                    "problem": payload.get("problem", ""),
                    "path": str(session_path),
                }
            )
    return sessions

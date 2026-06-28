"""FastAPI endpoints for Mystic."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
from typing import Any

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
        controller = _controller_option()
        auth_cards = [
            ProviderAuthCard(
                model_id=model_id,
                status=model_status["status"],
                action_href=f"/providers/auth/{model_id}",
            )
            for model_id, model_status in status["models"].items()
            if model_status["provider"] == "cli" and model_status["status"]["state"] == "not_authenticated"
        ]
        return ResearchTableStartPage(participants=participants, auth_cards=auth_cards, controller=controller)

    @app.get("/research-table/start/run", response_class=HTMLResponse)
    def research_table_run(
        request: Request,
        problem: str,
        mode: str = "discovery_debate",
        max_rounds: int = 3,
        controller: str = "gpt_controller",
    ):
        status = toolbox.mystic_status()
        allowed_options = _participant_options(status)
        allowed_ids = {item["model_id"] for item in allowed_options}
        selected = _dedupe_preserving_order(request.query_params.getlist("participants"))
        if not problem.strip():
            raise HTTPException(status_code=400, detail="problem is required")
        if len(selected) < 2 or len(selected) > 3:
            raise HTTPException(status_code=400, detail="select two or three participants")
        if any(model_id not in allowed_ids for model_id in selected):
            raise HTTPException(status_code=400, detail="one or more selected participants are unavailable")
        session = toolbox.mystic_run_research_table(
            problem=problem,
            participants=selected,
            mode=mode,
            max_rounds=max_rounds,
            enable_tools=True,
            tools=["mystic_verify_answer"],
            controller=controller,
        )
        _persist_research_table_selection(
            session_dir=root_path / "mystic_data" / "research_table_sessions" / session["session_id"],
            participant_models=[
                next(item for item in allowed_options if item["model_id"] == model_id)
                for model_id in selected
            ],
            controller=_controller_option(controller),
        )
        return RedirectResponse(url=f"/research-table/sessions/{session['session_id']}", status_code=302)

    @app.get("/research-table/sessions/{session_id}", response_class=HTMLResponse)
    def research_table_session(session_id: str):
        session = _load_research_table_session(root_path / "mystic_data/research_table_sessions" / session_id)
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
    models = status.get("models", {})
    ranked: list[tuple[int, str, dict[str, Any]]] = []
    for model_id, model in models.items():
        provider = str(model.get("provider", ""))
        enabled = bool(model.get("enabled", True))
        if provider == "api" and not enabled:
            continue
        if provider not in {"ollama", "local_adapter", "cli"}:
            continue
        ranked.append((_participant_rank(model_id, provider), model_id, model))
    selected_defaults = 0
    options = []
    for _, model_id, model in sorted(ranked):
        checked = False
        if str(model.get("provider", "")) != "cli" and selected_defaults < 2:
            checked = True
            selected_defaults += 1
        options.append(
            {
                "model_id": model_id,
                "label": _participant_label(model_id, model),
                "provider": model["provider"],
                "model_name": model["model_name"],
                "roles": model.get("role_defaults", []),
                "auth_state": model["status"]["state"],
                "checked": checked,
            }
        )
    return options


def _participant_label(model_id: str, model: dict[str, Any]) -> str:
    if model_id == "gemini_cli":
        return "Gemini CLI"
    if model_id == "claude_cli":
        return "Claude CLI"
    return f"{model_id} ({model.get('model_name', model_id)})"


def _participant_rank(model_id: str, provider: str) -> int:
    if provider in {"ollama", "local_adapter"}:
        return 0
    if model_id == "gemini_cli":
        return 1
    if model_id == "claude_cli":
        return 2
    return 3


def _controller_option(model_id: str = "gpt_controller") -> dict[str, str]:
    return {
        "model_id": model_id,
        "provider": "controller",
        "model_name": "GPT Controller" if model_id == "gpt_controller" else model_id,
    }


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        item = str(value).strip()
        if not item or item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def _persist_research_table_selection(
    *,
    session_dir: Path,
    participant_models: list[dict[str, Any]],
    controller: dict[str, str],
) -> None:
    if not session_dir.exists():
        return
    session_path = session_dir / "session.json"
    session = _load_optional_json(session_path, {})
    if not isinstance(session, dict):
        return
    session["participant_models"] = [
        {
            "model_id": item["model_id"],
            "provider": item["provider"],
            "model_name": item["model_name"],
        }
        for item in participant_models
    ]
    session["controller"] = controller
    session_path.write_text(json.dumps(session, indent=2), encoding="utf-8")


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


def _load_optional_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _load_research_table_session(session_dir: Path) -> dict[str, Any]:
    session = _load_json(session_dir / "session.json")
    session["turns"] = _load_optional_json(session_dir / "turns.json", session.get("turns", []))
    session["discoveries"] = _load_optional_json(session_dir / "discoveries.json", session.get("discoveries", []))
    session["verification_requests"] = _load_optional_json(
        session_dir / "verification_requests.json",
        session.get("verification_requests", []),
    )
    session["final_synthesis_package"] = _load_optional_json(
        session_dir / "final_synthesis.json",
        session.get("final_synthesis_package", {}),
    )
    session["accepted_discoveries"] = session["final_synthesis_package"].get(
        "accepted_discoveries",
        session.get("accepted_discoveries", []),
    )
    session["rejected_discoveries"] = session["final_synthesis_package"].get(
        "rejected_discoveries",
        session.get("rejected_discoveries", []),
    )
    return session


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

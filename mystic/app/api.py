"""FastAPI endpoints for Mystic."""

from __future__ import annotations

try:
    from fastapi import FastAPI, HTTPException
except ImportError:  # pragma: no cover
    FastAPI = None
    HTTPException = RuntimeError

from mystic.core.orchestrator import MysticOrchestrator


def create_app():
    if FastAPI is None:  # pragma: no cover
        raise RuntimeError("fastapi is not installed; install mystic[api] to use the API")

    app = FastAPI(title="Mystic API", version="0.1.0")
    orchestrator = MysticOrchestrator()

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

    @app.get("/sessions/{session_id}")
    def get_session(session_id: str):
        try:
            return orchestrator.get_session(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

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

    return app


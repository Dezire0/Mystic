"""FastAPI endpoints for Mystic."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import os
from pathlib import Path
import shutil
from typing import Any
from urllib.parse import quote
import uuid

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
    ControlPanelPage,
    DebateSessionPage,
    LabSessionPage,
    LabStartPage,
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
from mystic.research_table.discovery import VerificationRequest
from mystic.research_table.session import ResearchTurn
from mystic.research_table.storage import ResearchTableStorage


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
    research_storage = ResearchTableStorage(root_path)

    @app.get("/", response_class=HTMLResponse)
    def home():
        status = toolbox.mystic_status()
        sessions = _collect_session_index(root_path)
        lab_sessions = [item for item in sessions if item.get("type") == "lab"]
        return ControlPanelPage(
            status=status,
            sessions=sessions,
            lab_sessions=lab_sessions,
            warnings=_control_panel_warnings(status),
        )

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
            if model_status["provider"] == "cli"
        ]
        return ResearchTableStartPage(participants=participants, auth_cards=auth_cards, controller=controller)

    @app.get("/lab/start", response_class=HTMLResponse)
    def lab_start():
        status = toolbox.mystic_status()
        participants = _participant_options(status)
        auth_cards = [
            ProviderAuthCard(
                model_id=model_id,
                status=model_status["status"],
                action_href=f"/providers/auth/{model_id}",
            )
            for model_id, model_status in status["models"].items()
            if model_status["provider"] == "cli"
        ]
        return LabStartPage(participants=participants, auth_cards=auth_cards)

    @app.get("/lab/start/run", response_class=HTMLResponse)
    def lab_run(
        request: Request,
        problem: str,
        domain: str = "math",
        goal: str = "",
        mode: str = "serious",
    ):
        status = toolbox.mystic_status()
        allowed_options = _participant_options(status)
        allowed_ids = {item["model_id"] for item in allowed_options}
        selected = _dedupe_preserving_order(request.query_params.getlist("participants"))
        if not problem.strip():
            raise HTTPException(status_code=400, detail="problem is required")
        if not goal.strip():
            raise HTTPException(status_code=400, detail="goal is required")
        if len(selected) < 1 or len(selected) > 4:
            raise HTTPException(status_code=400, detail="select one to four participants")
        if any(model_id not in allowed_ids for model_id in selected):
            raise HTTPException(status_code=400, detail="one or more selected participants are unavailable")
        session = toolbox.lab_session_create(
            problem=problem,
            domain=domain,
            goal=goal,
            mode=mode,
            participants=selected,
        )
        return RedirectResponse(url=f"/lab/sessions/{session['session_id']}", status_code=302)

    @app.get("/lab/sessions/{session_id}", response_class=HTMLResponse)
    def lab_session(
        session_id: str,
        message: str = "",
        level: str = "info",
        claim_status: str = "",
        claim_type: str = "",
        relation_filter: str = "",
    ):
        session = toolbox.lab_session_get(session_id=session_id)
        if message:
            session["flash_message"] = message
            session["flash_level"] = level
        session["claim_status_filter"] = claim_status
        session["claim_type_filter"] = claim_type
        session["relation_filter"] = relation_filter
        return LabSessionPage(session=session)

    @app.post("/lab/sessions/{session_id}/advance")
    def lab_advance(session_id: str, max_steps: int = 1, target_phase: str | None = None, use_model_arena: bool = False):
        return _run_lab_action_redirect(
            session_id=session_id,
            action=lambda: toolbox.lab_session_advance(
                session_id=session_id,
                max_steps=max_steps,
                target_phase=target_phase,
                use_model_arena=use_model_arena,
                use_verifier=True,
            ),
            success_message="Lab session advanced.",
            error_prefix="Advance failed",
        )

    @app.post("/lab/sessions/{session_id}/model-arena")
    def lab_model_arena(session_id: str):
        session = toolbox.lab_session_get(session_id=session_id)
        participant_models = [str(item.get("model_id", "")) for item in session.get("session", {}).get("participants", [])]
        return _run_lab_action_redirect(
            session_id=session_id,
            action=lambda: toolbox.lab_models_debate(
                session_id=session_id,
                question=str(session.get("session", {}).get("problem", "")),
                participants=[item for item in participant_models if item],
                rounds=["independent_discovery", "cross_critique", "revision_after_evidence", "final_synthesis"],
                use_existing_research_table=True,
            ),
            success_message="Model Arena run completed.",
            error_prefix="Model Arena failed",
        )

    @app.post("/lab/sessions/{session_id}/report")
    def lab_report(session_id: str):
        return _run_lab_action_redirect(
            session_id=session_id,
            action=lambda: toolbox.lab_report_generate(
                session_id=session_id,
                format="markdown",
                include_failures=True,
                include_next_actions=True,
            ),
            success_message="Lab report generated.",
            error_prefix="Report generation failed",
        )

    @app.post("/lab/sessions/{session_id}/referee-review")
    def lab_referee_review(session_id: str):
        session = toolbox.lab_session_get(session_id=session_id)
        claims = session.get("claims", [])
        if not claims:
            return _lab_session_redirect(session_id, message="Referee review unavailable: no claims yet.", level="error")
        latest_claim = claims[-1]
        return _run_lab_action_redirect(
            session_id=session_id,
            action=lambda: toolbox.lab_referee_review(
                session_id=session_id,
                claim_id=str(latest_claim.get("claim_id", "")),
                text=str(latest_claim.get("text", "")),
                strictness="hostile",
            ),
            success_message="Referee review completed.",
            error_prefix="Referee review failed",
        )

    @app.post("/lab/sessions/{session_id}/experiments/create")
    def lab_create_experiment(session_id: str):
        session = toolbox.lab_session_get(session_id=session_id)
        claims = session.get("claims", [])
        if not claims:
            return _lab_session_redirect(session_id, message="Experiment creation unavailable: no claims yet.", level="error")
        latest_claim = claims[-1]
        return _run_lab_action_redirect(
            session_id=session_id,
            action=lambda: toolbox.lab_experiment_create(
                session_id=session_id,
                claim_id=str(latest_claim.get("claim_id", "")),
                question=f"Test claim: {latest_claim.get('text', '')}",
                method="python_bruteforce",
                inputs={"candidate_answer": str(latest_claim.get("text", ""))},
            ),
            success_message="Experiment created.",
            error_prefix="Experiment creation failed",
        )

    @app.post("/lab/sessions/{session_id}/experiments/{experiment_id}/run")
    def lab_run_experiment(session_id: str, experiment_id: str, dry_run: bool = False):
        return _run_lab_action_redirect(
            session_id=session_id,
            action=lambda: toolbox.lab_experiment_run(
                session_id=session_id,
                experiment_id=experiment_id,
                dry_run=dry_run,
            ),
            success_message="Experiment executed." if not dry_run else "Experiment dry-run completed.",
            error_prefix="Experiment run failed",
        )

    @app.post("/lab/sessions/{session_id}/experiments/run-latest")
    def lab_run_latest_experiment(session_id: str):
        session = toolbox.lab_session_get(session_id=session_id)
        experiments = session.get("experiments", [])
        if not experiments:
            return _lab_session_redirect(session_id, message="Experiment run unavailable: no experiments yet.", level="error")
        latest = experiments[-1]
        return _run_lab_action_redirect(
            session_id=session_id,
            action=lambda: toolbox.lab_experiment_run(
                session_id=session_id,
                experiment_id=str(latest.get("experiment_id", "")),
                dry_run=False,
            ),
            success_message="Latest experiment executed.",
            error_prefix="Experiment run failed",
        )

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
    def research_table_session(session_id: str, message: str = "", level: str = "info"):
        session = _load_research_table_session(root_path / "mystic_data/research_table_sessions" / session_id)
        if message:
            session["flash_message"] = message
            session["flash_level"] = level
        return ResearchTableSessionPage(session=session)

    @app.post("/research-table/{session_id}/discoveries/{discovery_id}/challenge")
    def challenge_discovery(session_id: str, discovery_id: str):
        return _run_action_redirect(
            session_id=session_id,
            action=lambda: _interactive_discovery_action(
                session_id=session_id,
                discovery_id=discovery_id,
                action="challenge",
                toolbox=toolbox,
                research_storage=research_storage,
            ),
            error_prefix="Challenge failed",
        )

    @app.post("/research-table/{session_id}/discoveries/{discovery_id}/extend")
    def extend_discovery(session_id: str, discovery_id: str):
        return _run_action_redirect(
            session_id=session_id,
            action=lambda: _interactive_discovery_action(
                session_id=session_id,
                discovery_id=discovery_id,
                action="extend",
                toolbox=toolbox,
                research_storage=research_storage,
            ),
            error_prefix="Extend failed",
        )

    @app.post("/research-table/{session_id}/discoveries/{discovery_id}/formalize")
    def formalize_discovery(session_id: str, discovery_id: str):
        return _run_action_redirect(
            session_id=session_id,
            action=lambda: _interactive_discovery_action(
                session_id=session_id,
                discovery_id=discovery_id,
                action="formalize",
                toolbox=toolbox,
                research_storage=research_storage,
            ),
            error_prefix="Formalize failed",
        )

    @app.post("/research-table/{session_id}/discoveries/{discovery_id}/verify")
    def verify_discovery(session_id: str, discovery_id: str):
        return _run_action_redirect(
            session_id=session_id,
            action=lambda: _interactive_discovery_action(
                session_id=session_id,
                discovery_id=discovery_id,
                action="verify",
                toolbox=toolbox,
                research_storage=research_storage,
            ),
            error_prefix="Verify failed",
        )

    @app.post("/research-table/{session_id}/turns/{turn_id}/revise")
    def revise_turn_after_evidence(session_id: str, turn_id: str):
        return _run_action_redirect(
            session_id=session_id,
            action=lambda: _interactive_turn_action(
                session_id=session_id,
                turn_id=turn_id,
                action="revise",
                toolbox=toolbox,
                research_storage=research_storage,
            ),
            error_prefix="Revise failed",
        )

    @app.post("/research-table/{session_id}/turns/{turn_id}/save-teacher-label")
    def save_turn_as_teacher_label(session_id: str, turn_id: str):
        return _run_action_redirect(
            session_id=session_id,
            action=lambda: _interactive_turn_action(
                session_id=session_id,
                turn_id=turn_id,
                action="save_teacher_label",
                toolbox=toolbox,
                research_storage=research_storage,
            ),
            error_prefix="Save teacher label failed",
        )

    @app.post("/research-table/{session_id}/discoveries/{discovery_id}/save-training-item")
    def save_discovery_as_training_item(session_id: str, discovery_id: str, target_agent: str = "raven"):
        return _run_action_redirect(
            session_id=session_id,
            action=lambda: _interactive_discovery_action(
                session_id=session_id,
                discovery_id=discovery_id,
                action="save_training_item",
                toolbox=toolbox,
                research_storage=research_storage,
                target_agent=target_agent,
            ),
            error_prefix="Save training item failed",
        )

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


def _run_action_redirect(*, session_id: str, action: Any, error_prefix: str) -> RedirectResponse:
    try:
        message = str(action())
        return _session_redirect(session_id, message=message, level="success")
    except Exception as exc:
        return _session_redirect(session_id, message=f"{error_prefix}: {exc}", level="error")


def _session_redirect(session_id: str, *, message: str, level: str) -> RedirectResponse:
    return RedirectResponse(
        url=f"/research-table/sessions/{session_id}?message={quote(message)}&level={quote(level)}",
        status_code=302,
    )


def _run_lab_action_redirect(*, session_id: str, action: Any, success_message: str, error_prefix: str) -> RedirectResponse:
    try:
        action()
        return _lab_session_redirect(session_id, message=success_message, level="success")
    except Exception as exc:
        return _lab_session_redirect(session_id, message=f"{error_prefix}: {exc}", level="error")


def _lab_session_redirect(session_id: str, *, message: str, level: str) -> RedirectResponse:
    return RedirectResponse(
        url=f"/lab/sessions/{session_id}?message={quote(message)}&level={quote(level)}",
        status_code=302,
    )


def _interactive_discovery_action(
    *,
    session_id: str,
    discovery_id: str,
    action: str,
    toolbox: MysticToolbox,
    research_storage: ResearchTableStorage,
    target_agent: str = "",
) -> str:
    session = research_storage.load_session(session_id)
    discovery = _find_by_id(session.get("discoveries", []), "discovery_id", discovery_id)
    source_turn = _find_optional_by_id(session.get("turns", []), "turn_id", str(discovery.get("source_turn_id", "")))
    reply_to = _interactive_reply_targets(
        turn_id=str(discovery.get("source_turn_id", "")),
        discovery_id=discovery_id,
    )
    if action == "verify":
        turn = _verify_discovery_turn(
            session=session,
            discovery=discovery,
            discovery_id=discovery_id,
            reply_to=reply_to,
            toolbox=toolbox,
        )
        session.setdefault("turns", []).append(turn.to_dict())
        _refresh_session_discovery_summary(session)
        research_storage.save_session(session_id, session)
        return f"Verifier added for discovery {discovery_id}."
    if action == "save_training_item":
        turn = _save_training_item_turn(
            session=session,
            discovery=discovery,
            discovery_id=discovery_id,
            reply_to=reply_to,
            target_agent=target_agent or "raven",
            root_path=toolbox.root_path,
        )
        session.setdefault("turns", []).append(turn.to_dict())
        research_storage.save_session(session_id, session)
        return f"Saved {target_agent or 'raven'} training item for discovery {discovery_id}."

    prompt, role = _discovery_follow_up_prompt(
        action=action,
        problem=str(session.get("problem", "")),
        discovery=discovery,
        source_turn=source_turn,
    )
    target_model = _select_follow_up_model(
        session=session,
        toolbox=toolbox,
        exclude_model_ids=[str(source_turn.get("speaker_id", ""))] if source_turn else [],
    )
    result = toolbox.mystic_call_model(
        model_id=target_model,
        role=role,
        task=action.replace("_", " "),
        problem=str(session.get("problem", "")),
        context=prompt,
    )
    turn = _model_result_turn(
        session_id=session_id,
        round_index=_next_interactive_round_index(session),
        phase="interactive_follow_up",
        role="critic" if action == "challenge" else "solver",
        reply_to=reply_to,
        result=result,
    )
    session.setdefault("turns", []).append(turn.to_dict())
    if action == "challenge" and str(discovery.get("status", "")).lower() not in {"verified", "refuted", "accepted"}:
        discovery["status"] = "challenged"
    _refresh_session_discovery_summary(session)
    research_storage.save_session(session_id, session)
    if result["status"] == "AUTH_REQUIRED":
        return f"Action created AUTH_REQUIRED turn for {target_model}."
    return f"Interactive {action} turn added with {target_model}."


def _interactive_turn_action(
    *,
    session_id: str,
    turn_id: str,
    action: str,
    toolbox: MysticToolbox,
    research_storage: ResearchTableStorage,
) -> str:
    session = research_storage.load_session(session_id)
    turn = _find_by_id(session.get("turns", []), "turn_id", turn_id)
    if action == "save_teacher_label":
        saved_turn = _save_teacher_label_turn(
            session=session,
            source_turn=turn,
            root_path=toolbox.root_path,
            toolbox=toolbox,
        )
        session.setdefault("turns", []).append(saved_turn.to_dict())
        research_storage.save_session(session_id, session)
        return f"Teacher label saved for turn {turn_id}."

    prompt = (
        "Revise this prior turn after evidence. Preserve supported claims, remove refuted claims, "
        "and sharpen the reasoning.\n\n"
        f"Problem:\n{session.get('problem', '')}\n\nPrior turn:\n{turn.get('content', '')}"
    )
    target_model = _select_turn_revision_model(turn=turn, session=session, toolbox=toolbox)
    result = toolbox.mystic_call_model(
        model_id=target_model,
        role="revise",
        task="revise turn after evidence",
        problem=str(session.get("problem", "")),
        context=prompt,
    )
    new_turn = _model_result_turn(
        session_id=session_id,
        round_index=_next_interactive_round_index(session),
        phase="interactive_follow_up",
        role="revise",
        reply_to=[turn_id],
        result=result,
    )
    session.setdefault("turns", []).append(new_turn.to_dict())
    research_storage.save_session(session_id, session)
    if result["status"] == "AUTH_REQUIRED":
        return f"Revision created AUTH_REQUIRED turn for {target_model}."
    return f"Revision turn added with {target_model}."


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
                "auth_message": model["status"].get("message", ""),
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


def _find_by_id(items: list[dict[str, Any]], key: str, value: str) -> dict[str, Any]:
    for item in items:
        if str(item.get(key, "")) == value:
            return item
    raise KeyError(f"{key} not found: {value}")


def _find_optional_by_id(items: list[dict[str, Any]], key: str, value: str) -> dict[str, Any] | None:
    for item in items:
        if str(item.get(key, "")) == value:
            return item
    return None


def _interactive_reply_targets(*, turn_id: str, discovery_id: str) -> list[str]:
    values = [item for item in [turn_id, discovery_id] if item]
    seen: set[str] = set()
    ordered: list[str] = []
    for item in values:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def _select_follow_up_model(*, session: dict[str, Any], toolbox: MysticToolbox, exclude_model_ids: list[str]) -> str:
    participants = [str(item.get("model_id", "")) for item in session.get("participant_models", [])]
    candidates = [model_id for model_id in participants if model_id and model_id not in exclude_model_ids]
    if candidates:
        return candidates[0]
    status = toolbox.mystic_status()
    for model_id, payload in status.get("models", {}).items():
        if str(payload.get("provider", "")) == "api" and not bool(payload.get("enabled", True)):
            continue
        if model_id not in exclude_model_ids:
            return model_id
    raise ValueError("no eligible follow-up model available")


def _select_turn_revision_model(*, turn: dict[str, Any], session: dict[str, Any], toolbox: MysticToolbox) -> str:
    speaker_id = str(turn.get("speaker_id", ""))
    participants = {str(item.get("model_id", "")) for item in session.get("participant_models", [])}
    if speaker_id and speaker_id in participants:
        return speaker_id
    return _select_follow_up_model(session=session, toolbox=toolbox, exclude_model_ids=[])


def _next_interactive_round_index(session: dict[str, Any]) -> int:
    turns = session.get("turns", [])
    values = [int(turn.get("round_index", 0)) for turn in turns if str(turn.get("phase", ""))]
    return (max(values) if values else 0) + 1


def _model_result_turn(
    *,
    session_id: str,
    round_index: int,
    phase: str,
    role: str,
    reply_to: list[str],
    result: dict[str, Any],
) -> ResearchTurn:
    content = str(result.get("content") or result.get("auth_message") or "")
    return ResearchTurn(
        session_id=session_id,
        round_index=round_index,
        phase=phase,
        speaker_type="model",
        speaker_id=str(result.get("model_id", "")),
        provider=str(result.get("provider", "")),
        model_name=str(result.get("model_name", "")),
        role=role,
        status=str(result.get("status", "")),
        content=content,
        reply_to=reply_to,
        summary=content[:240],
        latency_sec=float(result.get("latency_sec", 0.0)),
        artifact_path=str(result.get("artifact_path", "")),
    )


def _verify_discovery_turn(
    *,
    session: dict[str, Any],
    discovery: dict[str, Any],
    discovery_id: str,
    reply_to: list[str],
    toolbox: MysticToolbox,
) -> ResearchTurn:
    verification = toolbox.mystic_verify_answer(
        problem=str(session.get("problem", "")),
        candidate_answer=str(discovery.get("claim", "")),
    )
    request = VerificationRequest(
        target_discovery_id=discovery_id,
        target_turn_id=str(discovery.get("source_turn_id", "")),
        target_candidate_answer=str(discovery.get("claim", "")),
        tool="mystic_verify_answer",
        question=f"Verify discovery: {discovery.get('claim', '')}",
        status="pending",
    ).to_dict()
    verdict = str(verification.get("verdict", "UNKNOWN")).upper()
    mapped_status = _discovery_status_from_verdict(verdict)
    if mapped_status:
        discovery["status"] = mapped_status
        discovery["needs_verification"] = False
    request["status"] = mapped_status or "pending"
    request["result_verdict"] = verdict
    request["result_reasoning"] = str(verification.get("reasoning", ""))
    turn = ResearchTurn(
        session_id=str(session.get("session_id", "")),
        round_index=_next_interactive_round_index(session),
        phase="interactive_follow_up",
        speaker_type="tool",
        speaker_id="mystic_verify_answer",
        provider="tool",
        model_name="deterministic_verifier",
        role="verifier",
        status="VERIFICATION_RESULT",
        content=str(verification.get("reasoning", "")),
        reply_to=reply_to,
        summary=verdict,
        claims=[verdict],
        artifact_path=str(verification.get("saved_artifact_path", "")),
        target_discovery_id=discovery_id,
        verification_request_id=str(request.get("request_id", "")),
    )
    request["tool_turn_id"] = turn.turn_id
    session.setdefault("verification_requests", []).append(request)
    return turn


def _save_teacher_label_turn(
    *,
    session: dict[str, Any],
    source_turn: dict[str, Any],
    root_path: Path,
    toolbox: MysticToolbox,
) -> ResearchTurn:
    imported = toolbox.mystic_import_teacher_label(
        packet_id=str(session.get("session_id", "")),
        label_json={
            "verdict": str(source_turn.get("status", "UNCLEAR")),
            "first_fatal_error": "",
            "critique": str(source_turn.get("content", ""))[:500],
            "corrected_reasoning": str(source_turn.get("content", ""))[:500],
            "training_target": "raven",
            "training_value": "medium",
        },
        source_model=str(source_turn.get("speaker_id", "unknown")),
        target_agent="raven",
    )
    return ResearchTurn(
        session_id=str(session.get("session_id", "")),
        round_index=_next_interactive_round_index(session),
        phase="interactive_follow_up",
        speaker_type="tool",
        speaker_id="save_turn_as_teacher_label",
        provider="tool",
        model_name="teacher_label_writer",
        role="save",
        status="SAVED",
        content=f"Teacher label saved to {imported['saved_path']}",
        reply_to=[str(source_turn.get("turn_id", ""))],
        summary="teacher label saved",
        artifact_path=str(imported["saved_path"]),
    )


def _save_training_item_turn(
    *,
    session: dict[str, Any],
    discovery: dict[str, Any],
    discovery_id: str,
    reply_to: list[str],
    target_agent: str,
    root_path: Path,
) -> ResearchTurn:
    item_id = f"training-{uuid.uuid4().hex[:10]}"
    path = root_path / "mystic_data" / "training_items" / f"{item_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "item_id": item_id,
        "session_id": session.get("session_id", ""),
        "discovery_id": discovery_id,
        "target_agent": target_agent,
        "claim": discovery.get("claim", ""),
        "rationale": discovery.get("rationale", ""),
        "type": discovery.get("type", "strategy"),
        "status": discovery.get("status", "proposed"),
        "created_at": datetime.now(UTC).isoformat(),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return ResearchTurn(
        session_id=str(session.get("session_id", "")),
        round_index=_next_interactive_round_index(session),
        phase="interactive_follow_up",
        speaker_type="tool",
        speaker_id="save_discovery_as_training_item",
        provider="tool",
        model_name=f"{target_agent}_training_writer",
        role="save",
        status="SAVED",
        content=f"Training item saved to {path}",
        reply_to=reply_to,
        summary="training item saved",
        artifact_path=str(path),
    )


def _discovery_follow_up_prompt(
    *,
    action: str,
    problem: str,
    discovery: dict[str, Any],
    source_turn: dict[str, Any] | None,
) -> tuple[str, str]:
    claim = str(discovery.get("claim", ""))
    rationale = str(discovery.get("rationale", ""))
    source_content = str(source_turn.get("content", "")) if source_turn else ""
    if action == "challenge":
        return (
            f"Challenge this discovery. Point out weaknesses, hidden assumptions, or counterarguments.\n\nProblem:\n{problem}\n\nDiscovery:\n{claim}\n\nRationale:\n{rationale}\n\nSource turn:\n{source_content}",
            "critique",
        )
    if action == "extend":
        return (
            f"Extend this discovery with stronger implications, next steps, or sharper structure.\n\nProblem:\n{problem}\n\nDiscovery:\n{claim}\n\nRationale:\n{rationale}\n\nSource turn:\n{source_content}",
            "draft",
        )
    if action == "formalize":
        return (
            f"Formalize this discovery as a lemma, invariant, or proof subgoal.\n\nProblem:\n{problem}\n\nDiscovery:\n{claim}\n\nRationale:\n{rationale}\n\nSource turn:\n{source_content}",
            "draft",
        )
    raise ValueError(f"unsupported discovery action: {action}")


def _discovery_status_from_verdict(verdict: str) -> str | None:
    if verdict == "VALID":
        return "verified"
    if verdict == "INVALID":
        return "refuted"
    return None


def _refresh_session_discovery_summary(session: dict[str, Any]) -> None:
    discoveries = session.get("discoveries", [])
    session["accepted_discoveries"] = [
        item for item in discoveries if str(item.get("status", "")).lower() in {"verified", "accepted"}
    ]
    session["rejected_discoveries"] = [
        item for item in discoveries if str(item.get("status", "")).lower() in {"refuted", "rejected"}
    ]


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
        ("lab", root_path / "mystic_data/lab_sessions"),
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
                    "session_id": payload.get("session_id", payload.get("session", {}).get("session_id", item.name)),
                    "problem": payload.get("problem", payload.get("session", {}).get("problem", "")),
                    "path": str(session_path),
                }
            )
    return sessions


def _control_panel_warnings(status: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if str(status.get("mcp_server_status", "")).lower() != "ready":
        warnings.append("MCP server is not reporting READY.")
    for model_id, payload in status.get("models", {}).items():
        state = str(payload.get("status", {}).get("state", "unknown"))
        message = str(payload.get("status", {}).get("message", "")).strip()
        if state in {"not_authenticated", "auth_required"}:
            warnings.append(f"{model_id} requires login. {message}".strip())
        elif state in {"missing", "error", "disabled"}:
            warnings.append(f"{model_id} is {state}. {message}".strip())
    if not warnings:
        recent_errors = status.get("recent_errors", [])
        warnings.extend(str(item) for item in recent_errors[:3])
    return warnings[:8]

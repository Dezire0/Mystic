from __future__ import annotations

from html import escape
import json
from typing import Any

from mystic.app.components import (
    AgentTurnCard,
    ClaimCard,
    DebateTimeline,
    DiscoveryCard,
    DisagreementPanel,
    ExperimentCard,
    FailureCard,
    FinalJudgePanel,
    FinalSynthesisPanel,
    LabActionBar,
    MemoryEdgeList,
    ParticipantSelector,
    PhaseStepper,
    ProviderAuthCard,
    ProviderStatusPanel,
    ReportPreview,
    ResearchPhaseSection,
    StatusBadge,
    ToolEvidenceCard,
    VerificationRequestCard,
    WarningBanner,
    layout,
)


def ControlPanelPage(*, status: dict[str, Any], sessions: list[dict[str, Any]], lab_sessions: list[dict[str, Any]], warnings: list[str]) -> str:
    quick_actions = (
        "<div class='action-row'>"
        "<a class='action primary' href='/lab/start'>Create Lab Session</a>"
        "<a class='action' href='/research-table/start'>Open Model Arena</a>"
        "<a class='action' href='/sessions/detail'>Search Memory</a>"
        "<a class='action' href='/sessions/detail'>View Failures</a>"
        "<a class='action' href='/teacher-labels'>Generate Report Data</a>"
        "</div>"
    )
    session_cards = "".join(_session_index_card(item) for item in lab_sessions[:8]) or WarningBanner(
        message="No lab sessions yet. Start a new session from the quick actions.",
        level="info",
    )
    recent_cards = "".join(_session_index_card(item) for item in sessions[:8]) or WarningBanner(
        message="No recent stored sessions found.",
        level="info",
    )
    warning_block = "".join(
        WarningBanner(message=message, level="warning", title="Operator Warning")
        for message in warnings
    ) or WarningBanner(message="No provider auth or backend warnings are currently visible.", level="success", title="Warnings")
    body = (
        "<section class='grid'>"
        "<section class='panel'>"
        "<h2>Control Panel</h2>"
        "<p class='muted'>System status, active lab sessions, provider readiness, and quick actions for the full research loop.</p>"
        f"{quick_actions}"
        "</section>"
        f"{ProviderStatusPanel(status=status)}"
        "</section>"
        "<section class='grid'>"
        f"<section class='panel'><h2>Active Lab Sessions</h2><div class='stack'>{session_cards}</div></section>"
        f"<section class='panel'><h2>Recent Sessions</h2><div class='stack'>{recent_cards}</div></section>"
        f"<section class='panel'><h2>Failed Training Runs / Warnings</h2><div class='stack'>{warning_block}</div></section>"
        "</section>"
    )
    return layout(
        title="MysticControlPanel",
        subtitle="Serious AI research operating system. Monitor provider state, active lab sessions, failures, and next actions before you launch work.",
        body=body,
        nav="<div class='page-nav'><a class='action' href='/lab/start'>Create Lab Session</a><a class='action' href='/research-table/start'>Model Arena</a><a class='action' href='/teacher-labels'>Dataset Room</a><a class='action' href='/providers/auth/gemini_cli'>Provider / MCP Settings</a></div>",
    )


def ResearchTableStartPage(*, participants: list[dict[str, Any]], auth_cards: list[str], controller: dict[str, Any]) -> str:
    body = (
        "<section class='grid'>"
        "<article class='panel'>"
        "<h2>Model Arena</h2>"
        "<p class='muted'>Multi-model discovery debate with explicit provenance, tool verification, and final synthesis import into lab sessions.</p>"
        "<form action='/research-table/start/run' method='get' class='stack'>"
        "<div><label class='field-label'>Problem</label><textarea name='problem' placeholder='State the problem or research question.'></textarea></div>"
        f"<div><label class='field-label'>Participants</label>{ParticipantSelector(participants=participants)}</div>"
        "<div class='split'>"
        "<div><label class='field-label'>Mode</label><select name='mode'>"
        "<option value='discovery_debate' selected>discovery_debate</option>"
        "<option value='discovery_only'>discovery_only</option>"
        "</select></div>"
        "<div><label class='field-label'>Rounds</label><select name='max_rounds'>"
        "<option value='2'>2</option><option value='3' selected>3</option><option value='4'>4</option>"
        "</select></div></div>"
        f"<input type='hidden' name='controller' value='{escape(str(controller.get('model_id', 'gpt_controller')))}'>"
        "<div class='panel'>"
        "<h3>Controller / Judge</h3>"
        f"<div class='meta-row'><span class='badge arena'>{escape(str(controller.get('model_name', 'GPT Controller')))}</span><span class='badge'>{escape(str(controller.get('model_id', 'gpt_controller')))}</span></div>"
        "<p class='small muted'>GPT Controller coordinates final synthesis. Deterministic verifier evidence is shown separately from model output.</p>"
        "</div>"
        "<div class='action-row'><button class='action primary' type='submit'>Start Research Table</button></div>"
        "</form></article>"
        "<article class='panel'><h2>Provider / MCP Settings</h2>"
        "<p class='muted'>CLI auth issues remain visible but do not collapse the overall workflow.</p>"
        f"<div class='stack'>{''.join(auth_cards) if auth_cards else WarningBanner(message='All login-backed providers look ready.', level='success')}</div>"
        "</article></section>"
    )
    return layout(
        title="ResearchTableStartPage",
        subtitle="Model Arena runs independent discovery, critique, tool verification, revision, and final synthesis without pretending heuristic output is proven.",
        body=body,
        nav="<div class='page-nav'><a class='action' href='/'>Control Panel</a><a class='action' href='/lab/start'>Create Lab Session</a><a class='action' href='/teacher-labels'>Dataset Room</a></div>",
    )


def ResearchTableSessionPage(*, session: dict[str, Any]) -> str:
    session_id = str(session.get("session_id", ""))
    turns = session.get("turns", [])
    discoveries = session.get("discoveries", [])
    discoveries_by_turn = _discoveries_by_turn(discoveries)
    grouped = _group_turns_by_phase(turns)
    tool_evidence = [
        turn for turn in turns if str(turn.get("speaker_type", "")) == "tool"
    ]
    flash_panel = _flash_panel(session)
    participant_models = session.get("participant_models", [])
    controller = session.get("controller", {})
    participant_cards = "".join(
        "<article class='object-card'>"
        f"<div class='meta-row'><span class='badge'>{escape(str(item.get('model_id', '')))}</span><span class='badge'>{escape(str(item.get('provider', '')))}</span><span class='badge arena'>{escape(str(item.get('model_name', '')))}</span></div>"
        "</article>"
        for item in participant_models
    )
    phase_sections = "".join(
        ResearchPhaseSection(phase=phase, turns=phase_turns, discoveries_by_turn=discoveries_by_turn, session_id=session_id)
        for phase, phase_turns in grouped
    )
    body = (
        "<section class='workspace-grid'>"
        "<aside class='workspace-left'>"
        "<section class='panel'><h2>Model Arena</h2>"
        f"<p class='small muted'>{escape(str(session.get('problem', '')))}</p>"
        f"<div class='meta-row'>{StatusBadge(str(session.get('final_status', session.get('final_synthesis_package', {}).get('final_status', 'UNKNOWN'))))}<span class='badge arena'>{escape(str(session.get('final_decision_source', session.get('final_synthesis_package', {}).get('final_decision_source', 'model_outputs'))))}</span></div>"
        "</section>"
        "<section class='panel'><h2>Selected Participants</h2>"
        f"<div class='stack'>{participant_cards or WarningBanner(message='No participant metadata recorded.', level='info')}</div>"
        f"<div class='section-sep'><div class='meta-row'><span class='badge'>controller</span><span class='badge arena'>{escape(str(controller.get('model_name', 'GPT Controller')))}</span><span class='badge'>{escape(str(controller.get('model_id', 'gpt_controller')))}</span></div></div>"
        "</section>"
        "</aside>"
        "<section class='workspace-center'>"
        f"{flash_panel}"
        "<section class='panel'><h2>Research Timeline</h2>"
        f"<div class='stack'>{phase_sections or WarningBanner(message='No turns recorded yet.', level='info')}</div></section>"
        "</section>"
        "<aside class='workspace-right'>"
        "<section class='panel'><h2>Discoveries / New Discovery Feed</h2>"
        f"<div class='discovery-grid'>{''.join(DiscoveryCard(discovery=item, session_id=session_id) for item in discoveries) or WarningBanner(message='No discoveries recorded yet.', level='info')}</div></section>"
        "<section class='panel'><h2>Verification Requests</h2>"
        f"<div class='stack'>{''.join(VerificationRequestCard(request=item) for item in session.get('verification_requests', [])) or WarningBanner(message='No verification requests recorded.', level='info')}</div></section>"
        "<section class='panel'><h2>Tool Evidence</h2>"
        f"<div class='stack'>{''.join(ToolEvidenceCard(turn=turn, session_id=session_id) for turn in tool_evidence) or WarningBanner(message='No tool evidence recorded yet.', level='info')}</div></section>"
        f"{FinalSynthesisPanel(synthesis=session.get('final_synthesis_package', {}), session_id=session_id)}"
        f"{DisagreementPanel(rejected_discoveries=session.get('rejected_discoveries', []))}"
        "</aside></section>"
    )
    return layout(
        title="ResearchTableSessionPage",
        subtitle="Model output, deterministic tool evidence, rejected discoveries, and final synthesis are separated so unverified claims never look proven.",
        body=body,
        nav="<div class='page-nav'><a class='action' href='/'>Control Panel</a><a class='action' href='/lab/start'>Create Lab Session</a><a class='action' href='/research-table/start'>Start Another Arena Session</a></div>",
    )


def LabStartPage(*, participants: list[dict[str, Any]], auth_cards: list[str]) -> str:
    body = (
        "<section class='grid'>"
        "<article class='panel'>"
        "<h2>Create Lab Session</h2>"
        "<p class='muted'>Problem intake, scope, participants, and mode selection for a structured research session.</p>"
        "<form action='/lab/start/run' method='get' class='stack'>"
        "<div><label class='field-label'>Problem Statement</label><textarea name='problem' placeholder='State the research problem.'></textarea></div>"
        "<div class='split'>"
        "<div><label class='field-label'>Domain</label><select name='domain'>"
        "<option value='math' selected>math</option><option value='physics'>physics</option><option value='chemistry'>chemistry</option>"
        "<option value='biology'>biology</option><option value='engineering'>engineering</option><option value='software'>software</option>"
        "<option value='invention'>invention</option><option value='ai'>ai</option><option value='general'>general</option>"
        "</select></div>"
        "<div><label class='field-label'>Mode</label><select name='mode'>"
        "<option value='serious' selected>serious</option><option value='cheap'>cheap</option>"
        "<option value='proof_critical'>proof_critical</option><option value='single_session_subagents'>single_session_subagents</option>"
        "<option value='multi_model_debate'>multi_model_debate</option>"
        "</select></div></div>"
        "<div><label class='field-label'>Goal</label><textarea name='goal' placeholder='What should this session deliver?'></textarea></div>"
        f"<div><label class='field-label'>Participants</label>{ParticipantSelector(participants=participants)}</div>"
        "<div class='action-row'><button class='action primary' type='submit'>Start Lab Session</button></div>"
        "</form></article>"
        "<article class='panel'><h2>Safety / Scope Note</h2>"
        "<div class='stack'>"
        + WarningBanner(message="No hidden shell execution. Experiments must route through explicit backend tools.", level="info")
        + WarningBanner(message="Proof-critical mode is stricter: heuristic claims are not promoted without referee or verifier support.", level="warning")
        + WarningBanner(message="Provider auth issues remain visible but should not crash session creation.", level="info")
        + f"{''.join(auth_cards) if auth_cards else ''}"
        + "</div></article></section>"
    )
    return layout(
        title="MysticLabStartPage",
        subtitle="Create a serious Virtual Research Lab session with explicit scope, mode, provenance, and participant readiness.",
        body=body,
        nav="<div class='page-nav'><a class='action' href='/'>Control Panel</a><a class='action' href='/research-table/start'>Model Arena</a><a class='action' href='/teacher-labels'>Dataset Room</a></div>",
    )


def LabSessionPage(*, session: dict[str, Any]) -> str:
    session_meta = session.get("session", {})
    session_id = str(session_meta.get("session_id", session.get("session_id", "")))
    claim_status = str(session.get("claim_status_filter", "")).strip()
    claim_type = str(session.get("claim_type_filter", "")).strip()
    relation_filter = str(session.get("relation_filter", "")).strip()
    turns = session.get("turns", [])
    claims = _filter_claims(session.get("claims", []), claim_status=claim_status, claim_type=claim_type)
    experiments = session.get("experiments", [])
    failures = session.get("failures", [])
    memory_edges = _filter_memory_edges(session.get("memory_edges", []), relation_filter=relation_filter)
    grouped_turns = _group_lab_turns_by_phase(turns)
    flash_panel = _flash_panel(session)
    phase_sections = "".join(
        _lab_phase_section(phase=phase, turns=phase_turns, session_id=session_id)
        for phase, phase_turns in grouped_turns
    )
    participant_cards = "".join(
        "<article class='object-card'>"
        f"<div class='meta-row'><span class='badge'>{escape(str(item.get('model_id', '')))}</span><span class='badge'>{escape(str(item.get('provider', '')))}</span><span class='badge arena'>{escape(str(item.get('model_name', '')))}</span>{StatusBadge(str(item.get('status', {}).get('state', 'unknown')))}</div>"
        "</article>"
        for item in session_meta.get("participants", [])
    )
    warnings = _lab_session_warnings(session=session)
    body = (
        "<section class='workspace-grid'>"
        "<aside class='workspace-left'>"
        f"{PhaseStepper(current_phase=str(session_meta.get('current_phase', 'problem_intake')), mode=str(session_meta.get('mode', '')), active_room=str(session_meta.get('active_room', '')))}"
        "<section class='panel'><h2>Session Metadata</h2>"
        "<div class='kv-list'>"
        + _safe_kv("Session", f"<code>{escape(session_id)}</code>")
        + _safe_kv("Mode", StatusBadge(str(session_meta.get("mode", "")), label=str(session_meta.get("mode", ""))))
        + _safe_kv("Current Phase", escape(_phase_title(str(session_meta.get("current_phase", "")))))
        + _safe_kv("Active Room", escape(str(session_meta.get("active_room", ""))))
        + _safe_kv("Status", StatusBadge(str(session_meta.get("status", "UNKNOWN"))))
        + _safe_kv("Domain", escape(str(session_meta.get("domain", ""))))
        + "</div></section>"
        "<section class='panel'><h2>Room Shortcuts</h2>"
        f"<div class='meta-row'>{''.join(f'<span class=\"chip\">{escape(item)}</span>' for item in _lab_room_shortcuts())}</div>"
        "</section>"
        "<section class='panel'><h2>Participants</h2>"
        f"<div class='stack'>{participant_cards or WarningBanner(message='No participant metadata recorded.', level='info')}</div>"
        "</section>"
        "</aside>"
        "<section class='workspace-center'>"
        f"{flash_panel}"
        f"{''.join(warnings)}"
        f"{LabActionBar(session_id=session_id, has_claims=bool(session.get('claims')), has_experiments=bool(experiments), model_arena_available=True, report_available=True, referee_available=True)}"
        "<section class='panel'><h2>Main Lab Room</h2>"
        f"<p class='muted'>{escape(str(session_meta.get('problem', '')))}</p>"
        f"<div class='stack'>{phase_sections or WarningBanner(message='Session created. No research steps have run yet.', level='info')}</div>"
        "</section>"
        "<section class='panel'><h2>Lab Notebook</h2>"
        f"<div class='notebook-markdown'>{escape(str(session.get('notebook_markdown', '')) or 'No notebook content yet.')}</div>"
        "</section>"
        "</section>"
        "<aside class='workspace-right'>"
        "<section class='panel'><h2>Claims Board</h2>"
        f"{_claim_filter_form(session_id=session_id, claim_status=claim_status, claim_type=claim_type)}"
        f"<div class='discovery-grid section-sep'>{''.join(ClaimCard(claim=item) for item in claims) or WarningBanner(message='No claims yet. Advance the session or run a role.', level='info')}</div>"
        "</section>"
        "<section class='panel'><h2>Experiment Room / Simulation Tank</h2>"
        f"<div class='stack'>{''.join(ExperimentCard(experiment=item, session_id=session_id, enable_actions=True) for item in experiments) or WarningBanner(message='No experiments yet.', level='info')}</div>"
        "</section>"
        "<section class='panel'><h2>Failure Museum / Referee Court</h2>"
        f"<div class='stack'>{''.join(FailureCard(failure=item, enable_export=False) for item in failures) or WarningBanner(message='No failures archived yet.', level='info')}</div>"
        "</section>"
        "<section class='panel'><h2>Research Memory Graph</h2>"
        f"{_memory_filter_form(session_id=session_id, relation_filter=relation_filter)}"
        f"<div class='section-sep'>{MemoryEdgeList(edges=memory_edges)}</div>"
        "</section>"
        f"{ReportPreview(session=session, report_markdown=str(session.get('report_markdown', '')))}"
        "<section class='panel'><h2>Next Actions</h2>"
        f"<div class='meta-row'>{''.join(f'<span class=\"chip\">{escape(str(item))}</span>' for item in session.get('next_actions', [])) or '<span class=\"chip\">No next action recorded</span>'}</div>"
        "</section>"
        "</aside></section>"
    )
    return layout(
        title="MysticLabSessionPage",
        subtitle="Three-column research workspace with phase navigation, agent turns, claims, experiments, failures, memory links, report preview, and explicit next actions.",
        body=body,
        nav="<div class='page-nav'><a class='action' href='/'>Control Panel</a><a class='action' href='/lab/start'>Create Lab Session</a><a class='action' href='/research-table/start'>Model Arena</a><a class='action' href='/teacher-labels'>Dataset Room</a></div>",
    )


def DebateSessionPage(*, session: dict[str, Any]) -> str:
    body = (
        "<section class='grid'>"
        "<article class='panel'><h2>Debate Timeline</h2>"
        f"<p class='muted'>{escape(str(session.get('problem', '')))}</p>"
        f"{DebateTimeline(turns=session.get('turns', []))}"
        "</article>"
        f"{FinalJudgePanel(content=str(session.get('final_package', '')))}"
        "</section>"
    )
    return layout(
        title="DebateSessionPage",
        subtitle="Threaded debate with explicit turn provenance and final judgment output.",
        body=body,
        nav="<div class='page-nav'><a class='action' href='/'>Control Panel</a><a class='action' href='/research-table/start'>Model Arena</a></div>",
    )


def ModelComparePage(*, comparisons: list[dict[str, Any]]) -> str:
    cards = "".join(
        "<article class='panel'>"
        f"<div class='meta-row'><span class='badge arena'>{escape(str(comparison.get('session_id', 'compare')))}</span>{StatusBadge(str(comparison.get('final_status', comparison.get('verification', {}).get('verdict', 'UNKNOWN'))))}</div>"
        f"<p class='small muted'>{escape(str(comparison.get('problem', '')))}</p>"
        f"<pre class='report-markdown'>{escape(str(comparison.get('display_text', '')))}</pre>"
        "</article>"
        for comparison in comparisons
    )
    body = "<section class='stack'>" + (cards or WarningBanner(message="No compare sessions recorded yet.", level="info")) + "</section>"
    return layout(
        title="ModelComparePage",
        subtitle="Cross-model output inspection with deterministic verifier results separated from raw model responses.",
        body=body,
        nav="<div class='page-nav'><a class='action' href='/'>Control Panel</a><a class='action' href='/research-table/start'>Model Arena</a></div>",
    )


def TeacherLabelsPage(*, packets: list[dict[str, Any]], labels: list[dict[str, Any]]) -> str:
    packet_cards = "".join(
        "<article class='object-card'>"
        f"<div class='meta-row'><span class='badge'>{escape(str(packet.get('packet_id', '')))}</span><span class='badge arena'>{escape(str(packet.get('target_agent', '') or 'teacher packet'))}</span></div>"
        f"<p class='small muted'>Cases: <code>{len(packet.get('cases', []))}</code></p>"
        "</article>"
        for packet in packets
    )
    label_cards = "".join(
        "<article class='object-card'>"
        f"<div class='meta-row'><span class='badge'>{escape(str(label.get('label_id', '')))}</span><span class='badge'>{escape(str(label.get('target_agent', '')))}</span><span class='badge arena'>{escape(str(label.get('source_model', '')))}</span></div>"
        f"<pre class='report-markdown'>{escape(json.dumps(label.get('label', {}), ensure_ascii=False, indent=2))}</pre>"
        "</article>"
        for label in labels
    )
    body = (
        "<section class='grid'>"
        f"<section class='panel'><h2>Dataset Room / Teacher Packets</h2><div class='stack'>{packet_cards or WarningBanner(message='No packets exported yet.', level='info')}</div></section>"
        f"<section class='panel'><h2>Teacher Labels</h2><div class='stack'>{label_cards or WarningBanner(message='No labels imported yet.', level='info')}</div></section>"
        "</section>"
    )
    return layout(
        title="TeacherLabelsPage",
        subtitle="Dataset room for recent teacher packets and imported labels feeding Raven, Prime, Forge, and report training loops.",
        body=body,
        nav="<div class='page-nav'><a class='action' href='/'>Control Panel</a><a class='action' href='/lab/start'>Create Lab Session</a><a class='action' href='/research-table/start'>Model Arena</a></div>",
    )


def SessionDetailPage(*, sessions: list[dict[str, Any]]) -> str:
    cards = "".join(_session_index_card(session) for session in sessions)
    body = "<section class='stack'>" + (cards or WarningBanner(message="No stored sessions found.", level="info")) + "</section>"
    return layout(
        title="SessionDetailPage",
        subtitle="Cross-session index for lab, Research Table, and debate artifacts stored under mystic_data.",
        body=body,
        nav="<div class='page-nav'><a class='action' href='/'>Control Panel</a><a class='action' href='/lab/start'>Create Lab Session</a><a class='action' href='/research-table/start'>Model Arena</a></div>",
    )


def ProviderAuthPage(*, model_id: str, status: dict[str, Any]) -> str:
    body = (
        "<section class='grid'>"
        f"{ProviderAuthCard(model_id=model_id, status=status, action_href='/providers/auth/' + escape(str(model_id)))}"
        "<article class='panel'><h2>Provider / MCP Settings</h2>"
        f"<p class='muted'>{escape(str(status.get('message', '')))}</p>"
        "<p class='small'>Run the matching CLI login flow in your shell, then return here or to the start pages and refresh provider status.</p>"
        "</article></section>"
    )
    return layout(
        title="ProviderAuthCard",
        subtitle="Provider auth errors should stay visible but not catastrophic. This page isolates login state and next action.",
        body=body,
        nav="<div class='page-nav'><a class='action' href='/'>Control Panel</a><a class='action' href='/lab/start'>Create Lab Session</a><a class='action' href='/research-table/start'>Model Arena</a></div>",
    )


def escape_path_label(value: Any) -> str:
    return str(value)


def _group_turns_by_phase(turns: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for turn in turns:
        grouped.setdefault(str(turn.get("phase", "")), []).append(turn)
    ordered: list[tuple[str, list[dict[str, Any]]]] = []
    seen: set[str] = set()
    for turn in turns:
        phase = str(turn.get("phase", ""))
        if phase in seen:
            continue
        seen.add(phase)
        ordered.append((phase, grouped.get(phase, [])))
    return ordered


def _discoveries_by_turn(discoveries: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    mapping: dict[str, list[dict[str, Any]]] = {}
    for item in discoveries:
        source = str(item.get("source_turn_id", ""))
        if source:
            mapping.setdefault(source, []).append(item)
    return mapping


def _group_lab_turns_by_phase(turns: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    return _group_turns_by_phase(turns)


def _lab_phase_section(*, phase: str, turns: list[dict[str, Any]], session_id: str) -> str:
    cards = "".join(AgentTurnCard(turn=turn, session_id=session_id) for turn in turns)
    return (
        "<section class='phase-section'>"
        f"<div class='phase-header'><h3>{escape(_phase_title(phase))}</h3><span class='small muted'>{len(turns)} turns</span></div>"
        f"<div class='stack'>{cards}</div></section>"
    )


def _flash_panel(session: dict[str, Any]) -> str:
    flash_message = str(session.get("flash_message", "")).strip()
    flash_level = str(session.get("flash_level", "info")).strip()
    if not flash_message:
        return ""
    level = "success" if flash_level == "success" else "error" if flash_level == "error" else "info"
    return WarningBanner(message=flash_message, level=level, title="Session Message")


def _session_index_card(session: dict[str, Any]) -> str:
    session_type = str(session.get("type", "session"))
    route = _session_route(session_type=session_type, session_id=str(session.get("session_id", "")))
    return (
        "<article class='object-card'>"
        f"<div class='meta-row'><span class='badge'>{escape(session_type)}</span><span class='badge arena'>{escape(str(session.get('session_id', '')))}</span></div>"
        f"<p class='small muted'>{escape(str(session.get('problem', '')))}</p>"
        f"<p class='small mono'>{escape(str(session.get('path', '')))}</p>"
        f"<div class='action-row'><a class='action' href='{escape(route)}'>Open</a></div>"
        "</article>"
    )


def _session_route(*, session_type: str, session_id: str) -> str:
    if session_type == "lab":
        return f"/lab/sessions/{session_id}"
    if session_type == "debate":
        return f"/debate/sessions/{session_id}"
    return f"/research-table/sessions/{session_id}"


def _lab_room_shortcuts() -> list[str]:
    return [
        "Control Panel",
        "Main Lab Room",
        "Theory Room",
        "Hypothesis Chamber",
        "Experiment Room",
        "Simulation Tank",
        "Proof Forge",
        "Referee Court",
        "Failure Museum",
        "Dataset Room",
        "Lab Notebook",
        "Paper Room",
        "Research Memory Graph",
        "Model Arena",
    ]


def _safe_kv(label: str, value_html: str) -> str:
    return f"<div class='kv'><div class='kv-label'>{escape(label)}</div><div class='kv-value'>{value_html}</div></div>"


def _phase_title(value: str) -> str:
    return value.replace("_", " ").title()


def _claim_filter_form(*, session_id: str, claim_status: str, claim_type: str) -> str:
    return (
        "<div class='filter-row'>"
        f"<form method='get' action='/lab/sessions/{escape(session_id)}'>"
        "<select name='claim_status'>"
        f"<option value='' {'selected' if not claim_status else ''}>all statuses</option>"
        + "".join(
            f"<option value='{item}' {'selected' if claim_status == item else ''}>{item}</option>"
            for item in ["PROVED", "TESTED", "HEURISTIC", "FAILED", "UNKNOWN", "NEEDS_MORE_DETAIL", "REFUTED"]
        )
        + "</select>"
        "<select name='claim_type'>"
        f"<option value='' {'selected' if not claim_type else ''}>all types</option>"
        + "".join(
            f"<option value='{item}' {'selected' if claim_type == item else ''}>{item}</option>"
            for item in ["theorem", "lemma", "hypothesis", "observation", "design", "bug", "result", "question", "assumption"]
        )
        + "</select><button class='action' type='submit'>Filter</button></form></div>"
    )


def _memory_filter_form(*, session_id: str, relation_filter: str) -> str:
    return (
        "<div class='filter-row'>"
        f"<form method='get' action='/lab/sessions/{escape(session_id)}'>"
        "<select name='relation_filter'>"
        f"<option value='' {'selected' if not relation_filter else ''}>all relations</option>"
        + "".join(
            f"<option value='{item}' {'selected' if relation_filter == item else ''}>{item}</option>"
            for item in ["supports", "refutes", "depends_on", "contradicts", "caused_failure", "generated_experiment", "generated_training_data"]
        )
        + "</select><button class='action' type='submit'>Filter</button></form></div>"
    )


def _filter_claims(claims: list[dict[str, Any]], *, claim_status: str, claim_type: str) -> list[dict[str, Any]]:
    filtered = []
    for claim in claims:
        if claim_status and str(claim.get("status", "")) != claim_status:
            continue
        if claim_type and str(claim.get("claim_type", "")) != claim_type:
            continue
        filtered.append(claim)
    return filtered


def _filter_memory_edges(edges: list[dict[str, Any]], *, relation_filter: str) -> list[dict[str, Any]]:
    if not relation_filter:
        return edges
    return [item for item in edges if str(item.get("relation", "")) == relation_filter]


def _lab_session_warnings(*, session: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    session_meta = session.get("session", {})
    mode = str(session_meta.get("mode", ""))
    if mode == "proof_critical":
        warnings.append(
            WarningBanner(
                message="Proof-critical mode is active. Heuristic claims must not be treated as final without referee or verifier support.",
                level="warning",
                title="Strictness",
            )
        )
    if not session.get("claims"):
        warnings.append(WarningBanner(message="No claims yet. Advance the session or run a role.", level="info", title="Claims"))
    if not session.get("report_markdown", "").strip():
        warnings.append(WarningBanner(message="No report generated yet.", level="info", title="Paper Room"))
    return warnings

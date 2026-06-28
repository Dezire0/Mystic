from __future__ import annotations

from html import escape
import json
from pathlib import Path
from typing import Any

from mystic.app.components import (
    AskAnotherModelToCritiqueButton,
    AskModelToReviseAfterEvidenceButton,
    DebateTimeline,
    DiscoveryCard,
    DisagreementPanel,
    FinalJudgePanel,
    FinalSynthesisPanel,
    ParticipantSelector,
    ProviderAuthCard,
    ResearchPhaseSection,
    RunVerifierButton,
    ToolEvidenceCard,
    VerificationRequestCard,
    layout,
)


def ResearchTableStartPage(*, participants: list[dict[str, Any]], auth_cards: list[str], controller: dict[str, Any]) -> str:
    body = (
        "<section class='grid'>"
        "<article class='panel'>"
        "<h2>Start Mystic Research Table</h2>"
        "<form action='/research-table/start/run' method='get' class='stack'>"
        "<div><label class='field-label'>Problem</label><textarea name='problem' placeholder='State the problem or research question.'></textarea></div>"
        f"<div><label class='field-label'>Choose participants</label>{ParticipantSelector(participants=participants)}</div>"
        "<div class='grid'>"
        "<div><label class='field-label'>Mode</label><select name='mode'>"
        "<option value='discovery_debate' selected>Discovery Debate Mode / Research Table</option>"
        "<option value='discovery_only'>Discovery Only</option>"
        "</select></div></div>"
        "<div><label class='field-label'>Rounds</label><select name='max_rounds'>"
        "<option value='2'>2</option><option value='3' selected>3</option><option value='4'>4</option></select></div>"
        f"<input type='hidden' name='controller' value='{escape(str(controller.get('model_id', 'gpt_controller')))}'>"
        "<div class='panel'>"
        "<h3>Controller / Judge</h3>"
        f"<p><strong>{escape(str(controller.get('model_name', 'GPT Controller')))}</strong></p>"
        f"<p class='small muted'>{escape(str(controller.get('provider', 'controller')))} / {escape(str(controller.get('model_id', 'gpt_controller')))}</p>"
        "<p class='small muted'>Select exactly 2 or 3 participant models. GPT Controller coordinates synthesis and judgment but is not counted as a local participant.</p>"
        "</div>"
        "<div class='action-row'><button class='action primary' type='submit'>Start Research Table</button></div>"
        "</form></article>"
        "<article class='panel'><h2>Auth & Policy</h2><p class='muted'>Local models are preferred. API providers remain disabled by default. CLI providers can participate once logged in.</p>"
        f"<div class='stack'>{''.join(auth_cards) if auth_cards else '<p class=\"muted\">All login-based providers look ready.</p>'}</div></article>"
        "</section>"
    )
    return layout(
        title="ResearchTableStartPage",
        subtitle="Choose participants, confirm login-backed providers, and launch a local multi-model discovery session.",
        body=body,
        nav="<div class='page-nav'><a class='action' href='/teacher-labels'>Teacher Labels</a><a class='action' href='/model-compare'>Model Compare</a></div>",
    )


def ResearchTableSessionPage(*, session: dict[str, Any]) -> str:
    session_id = str(session.get("session_id", ""))
    turns = session.get("turns", [])
    discoveries = session.get("discoveries", [])
    discoveries_by_turn = _discoveries_by_turn(discoveries)
    grouped = _group_turns_by_phase(turns)
    discoveries = "".join(DiscoveryCard(discovery=item, session_id=session_id) for item in session.get("discoveries", []))
    verification_requests = "".join(
        VerificationRequestCard(request=request)
        for request in session.get("verification_requests", [])
    )
    phase_sections = "".join(
        ResearchPhaseSection(phase=phase, turns=phase_turns, discoveries_by_turn=discoveries_by_turn, session_id=session_id)
        for phase, phase_turns in grouped
    )
    tool_evidence_cards = "".join(
        ToolEvidenceCard(turn=turn, session_id=session_id)
        for turn in turns
        if str(turn.get("speaker_type", "")) == "tool"
    )
    flash_message = str(session.get("flash_message", "")).strip()
    flash_level = str(session.get("flash_level", "info")).strip()
    flash_panel = (
        f"<section class='panel'><div class='meta-row'><span class='badge'>{escape(flash_level)}</span></div><p>{escape(flash_message)}</p></section>"
        if flash_message
        else ""
    )
    participant_models = session.get("participant_models", [])
    participant_cards = "".join(
        (
            "<article class='turn'>"
            f"<div class='meta-row'><span class='badge'>{escape(str(item.get('model_id', '')))}</span>"
            f"<span class='badge'>{escape(str(item.get('provider', '')))}</span>"
            f"<span class='badge'>{escape(str(item.get('model_name', '')))}</span></div>"
            "</article>"
        )
        for item in participant_models
    )
    controller = session.get("controller", {})
    body = (
        "<section class='grid'>"
        "<article class='panel'>"
        "<h2>Research Table Timeline</h2>"
        f"<p class='muted'>{session.get('problem', '')}</p>"
        f"<div class='stack'>{phase_sections}</div>"
        "</article>"
        "<div class='stack'>"
        f"{flash_panel}"
        "<section class='panel'><h2>Selected Participants</h2>"
        f"<div class='stack'>{participant_cards or '<p class=\"muted\">No participant metadata recorded.</p>'}</div>"
        f"<div class='meta-row'><span class='badge'>controller</span><span class='badge'>{escape(str(controller.get('model_name', 'GPT Controller')))}</span><span class='badge'>{escape(str(controller.get('model_id', 'gpt_controller')))}</span></div>"
        "</section>"
        "<section class='panel'><h2>Discoveries</h2>"
        f"<div class='discovery-grid'>{discoveries or '<p class=\"muted\">No discoveries recorded.</p>'}</div></section>"
        "<section class='panel'><h2>Verification Requests</h2>"
        f"<div class='stack'>{verification_requests or '<p class=\"muted\">No verification requests recorded.</p>'}</div></section>"
        "<section class='panel'><h2>Tool Evidence</h2>"
        f"<div class='stack'>{tool_evidence_cards or '<p class=\"muted\">No tool evidence recorded.</p>'}</div></section>"
        f"{FinalSynthesisPanel(synthesis=session.get('final_synthesis_package', {}), session_id=session_id)}"
        f"{DisagreementPanel(rejected_discoveries=session.get('rejected_discoveries', []))}"
        "</div></section>"
    )
    return layout(
        title="ResearchTableSessionPage",
        subtitle="Independent discovery, sharing, critique, verification, and synthesis are grouped by round with exact model metadata.",
        body=body,
        nav="<div class='page-nav'><a class='action' href='/research-table/start'>Start Another Session</a><a class='action' href='/teacher-labels'>Teacher Labels</a></div>",
    )


def DebateSessionPage(*, session: dict[str, Any]) -> str:
    body = (
        "<section class='grid'>"
        "<article class='panel'><h2>Debate Timeline</h2>"
        f"<p class='muted'>{session.get('problem', '')}</p>"
        f"{DebateTimeline(turns=session.get('turns', []))}"
        "</article>"
        "<div class='stack'>"
        f"{FinalJudgePanel(content=str(session.get('final_package', '')))}"
        "<section class='panel'><h2>Actions</h2>"
        f"<div class='action-row'>{RunVerifierButton()} {AskAnotherModelToCritiqueButton()} {AskModelToReviseAfterEvidenceButton()}</div>"
        "</section></div></section>"
    )
    return layout(
        title="DebateSessionPage",
        subtitle="Threaded debate with explicit reply links, tool evidence, revisions, and final judgment.",
        body=body,
        nav="<div class='page-nav'><a class='action' href='/research-table/start'>Research Table</a><a class='action' href='/model-compare'>Model Compare</a></div>",
    )


def ModelComparePage(*, comparisons: list[dict[str, Any]]) -> str:
    cards = []
    for comparison in comparisons:
        cards.append(
            "<article class='panel'>"
            f"<h2>{comparison.get('session_id', 'compare')}</h2>"
            f"<p class='muted'>{comparison.get('problem', '')}</p>"
            f"<pre class='content'>{comparison.get('display_text', '')}</pre>"
            "</article>"
        )
    body = "<section class='stack'>" + "".join(cards or ["<article class='panel'><p class='muted'>No compare sessions recorded.</p></article>"]) + "</section>"
    return layout(
        title="ModelComparePage",
        subtitle="Structured compare sessions keep exact model/provider/model_name metadata and separate verifier evidence.",
        body=body,
        nav="<div class='page-nav'><a class='action' href='/research-table/start'>Research Table</a></div>",
    )


def TeacherLabelsPage(*, packets: list[dict[str, Any]], labels: list[dict[str, Any]]) -> str:
    packet_cards = "".join(
        "<article class='panel'>"
        f"<h3>{packet.get('packet_id', '')}</h3><p class='muted'>{packet.get('target_agent', '') or 'teacher packet'}</p>"
        f"<p class='small'>Cases: {len(packet.get('cases', []))}</p></article>"
        for packet in packets
    )
    label_cards = "".join(
        "<article class='panel'>"
        f"<h3>{label.get('label_id', '')}</h3><p class='muted'>{label.get('target_agent', '')} / {label.get('source_model', '')}</p>"
        f"<pre class='content'>{json.dumps(label.get('label', {}), ensure_ascii=False, indent=2)}</pre></article>"
        for label in labels
    )
    body = (
        "<section class='grid'>"
        f"<div class='stack'><section class='panel'><h2>Teacher Packets</h2>{packet_cards or '<p class=\"muted\">No packets exported yet.</p>'}</section></div>"
        f"<div class='stack'><section class='panel'><h2>Teacher Labels</h2>{label_cards or '<p class=\"muted\">No labels imported yet.</p>'}</section></div>"
        "</section>"
    )
    return layout(
        title="TeacherLabelsPage",
        subtitle="Review exported teacher packets and imported labels used to train local Prime, Forge, Raven, and Report adapters.",
        body=body,
        nav="<div class='page-nav'><a class='action' href='/research-table/start'>Research Table</a><a class='action' href='/sessions/detail'>Session Detail</a></div>",
    )


def SessionDetailPage(*, sessions: list[dict[str, Any]]) -> str:
    body = "<section class='stack'>" + "".join(
        "<article class='panel'>"
        f"<h2>{escape_path_label(session.get('type', 'session'))} · {escape_path_label(session.get('session_id', ''))}</h2>"
        f"<p class='muted'>{escape_path_label(session.get('problem', ''))}</p>"
        f"<p class='small'><code>{escape_path_label(session.get('path', ''))}</code></p>"
        "</article>"
        for session in sessions
    ) + "</section>"
    if not sessions:
        body = "<section class='panel'><p class='muted'>No stored sessions found.</p></section>"
    return layout(
        title="SessionDetailPage",
        subtitle="Stored debate and Research Table sessions saved under mystic_data are indexed here for inspection.",
        body=body,
        nav="<div class='page-nav'><a class='action' href='/research-table/start'>Research Table</a></div>",
    )


def ProviderAuthPage(*, model_id: str, status: dict[str, Any]) -> str:
    body = (
        "<section class='grid'>"
        f"{ProviderAuthCard(model_id=model_id, status=status, action_href='/research-table/start')}"
        "<article class='panel'><h2>Manual Login Guidance</h2>"
        f"<p class='muted'>{status.get('message', '')}</p>"
        f"<p class='small'>Run the matching CLI login flow in your shell, then return to the start page and refresh provider status.</p>"
        "</article></section>"
    )
    return layout(
        title="ProviderAuthCard",
        subtitle="Login-backed providers are optional but supported. Mystic keeps API usage disabled by default.",
        body=body,
    )


def escape_path_label(value: Any) -> str:
    return str(value)


def _group_turns_by_phase(turns: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for turn in turns:
        phase = str(turn.get("phase", ""))
        grouped.setdefault(phase, []).append(turn)
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
        if not source:
            continue
        mapping.setdefault(source, []).append(item)
    return mapping

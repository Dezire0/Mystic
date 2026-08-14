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


def SpecialistsPage(*, specialists: list[dict[str, Any]]) -> str:
    cards = []
    for item in specialists:
        usage = item.get("usage", {})
        specialist_id = str(item.get("specialist_id", ""))
        cards.append(
            "<article class='panel'>"
            f"<h2><a href='/specialists/{escape(specialist_id)}'>{escape(specialist_id)}</a></h2>"
            "<div class='meta-row'>"
            f"<span class='badge'>{escape(str(item.get('role', '')))}</span>"
            f"<span class='badge'>{escape(str(item.get('provider', '')))}</span>"
            f"<span class='badge'>{escape(str(item.get('health', '')))}</span>"
            f"<span class='badge'>{escape(str(item.get('benchmark_status', '')))}</span>"
            f"<span class='badge'>{escape(str(item.get('classification', '')))}</span>"
            "</div>"
            f"<p class='small muted'>Latency class: {escape(str(item.get('expected_latency_class', 'unknown')))} · Cost class: {escape(str(item.get('expected_cost_class', 'unknown')))}</p>"
            f"<p class='small'>Usage: {escape(str(usage.get('calls', 0)))} calls · observed average latency: {float(usage.get('average_latency_ms', 0.0)):.1f} ms · fallback rate: {float(usage.get('fallback_rate', 0.0)):.0%}</p>"
            f"<p class='small muted'>{escape('; '.join(str(value) for value in item.get('limitations', [])))}</p>"
            "</article>"
        )
    body = "<section class='grid'>" + "".join(cards or ["<article class='panel'><p class='muted'>No specialist registry entries are available.</p></article>"]) + "</section>"
    return layout(
        title="Specialists",
        subtitle="Bounded evidence instruments. GPT remains the research controller; no unverified specialist is treated as live or superior.",
        body=body,
        nav="<div class='page-nav'><a class='action' href='/evidence'>Evidence Provenance</a><a class='action' href='/research-table/start'>Research Table</a></div>",
    )


def SpecialistDetailPage(*, specialist: dict[str, Any], usage: dict[str, Any]) -> str:
    capability_chips = "".join(f"<span class='chip'>{escape(str(value))}</span>" for value in specialist.get("capabilities", []))
    fallback_chips = "".join(f"<span class='chip'>{escape(str(value))}</span>" for value in specialist.get("fallback_ids", []))
    limitations = "".join(f"<li>{escape(str(value))}</li>" for value in specialist.get("limitations", []))
    fallback_content = fallback_chips or "<span class='muted'>No approved fallback.</span>"
    recent = "".join(
        "<li>"
        f"{escape(str(item.get('created_at', '')))} · {escape(str(item.get('operation', '')))} · {escape(str(item.get('status', '')))}"
        "</li>"
        for item in usage.get("recent", [])
    )
    recent_content = recent or "<li class='muted'>No calls recorded.</li>"
    body = (
        "<section class='grid'>"
        "<article class='panel'>"
        f"<h2>{escape(str(specialist.get('specialist_id', '')))}</h2>"
        "<div class='meta-row'>"
        f"<span class='badge'>{escape(str(specialist.get('role', '')))}</span>"
        f"<span class='badge'>{escape(str(specialist.get('provider', '')))}</span>"
        f"<span class='badge'>{escape(str(specialist.get('health', '')))}</span>"
        f"<span class='badge'>{escape(str(specialist.get('benchmark_status', '')))}</span>"
        f"<span class='badge'>{escape(str(specialist.get('classification', '')))}</span>"
        "</div>"
        f"<p class='small muted'>Model: {escape(str(specialist.get('model_id', '')))} · version: {escape(str(specialist.get('version', '')))}</p>"
        "<h3>Capabilities</h3>"
        f"<div class='meta-row'>{capability_chips or '<span class="muted">No capability metadata.</span>'}</div>"
        "<h3>Routing status</h3>"
        f"<p>Enabled: {escape(str(specialist.get('enabled', False)))} · trust: {escape(str(specialist.get('trust_level', '')))} · last verified: {escape(str(specialist.get('last_verified_at', 'not verified')))}</p>"
        "<h3>Limitations</h3>"
        f"<ul>{limitations or '<li>No limitations recorded.</li>'}</ul>"
        "</article>"
        "<div class='stack'>"
        "<section class='panel'><h2>Benchmark evidence</h2>"
        f"<p>Quality: {float(specialist.get('benchmark_quality', 0.0)):.3f} · reliability: {float(specialist.get('reliability', 0.0)):.3f}</p>"
        f"<p class='muted'>Status: {escape(str(specialist.get('benchmark_status', '')))}. Fixture results do not approve a named candidate.</p></section>"
        "<section class='panel'><h2>Fallbacks</h2>"
        f"<div class='meta-row'>{fallback_content}</div></section>"
        "<section class='panel'><h2>Recent safe usage</h2>"
        f"<p>Calls: {escape(str(usage.get('calls', 0)))} · failures: {escape(str(usage.get('failures', 0)))} · observed average latency: {float(usage.get('average_latency_ms', 0.0)):.1f} ms · fallback rate: {float(usage.get('fallback_rate', 0.0)):.0%}</p>"
        f"<ul class='small'>{recent_content}</ul></section>"
        "</div></section>"
    )
    return layout(
        title="Specialist Detail",
        subtitle="Safe registry metadata and usage only. This page cannot configure credentials or invoke a model.",
        body=body,
        nav="<div class='page-nav'><a class='action' href='/specialists'>All Specialists</a><a class='action' href='/evidence'>Evidence Provenance</a></div>",
    )


def EvidencePage(*, evidence: list[dict[str, Any]]) -> str:
    cards = []
    for item in evidence:
        def provenance_label(step: dict[str, Any]) -> str:
            specialist = str(step.get("specialist_id", ""))
            suffix = f" · {escape(specialist)}" if specialist else ""
            return f"<li>{escape(str(step.get('stage', '')))} · {escape(str(step.get('location', '')))}{suffix}</li>"

        path = "".join(
            provenance_label(step)
            for step in item.get("provenance", [])
            if isinstance(step, dict)
        )
        provenance_content = path or "<li class='muted'>No provenance steps recorded.</li>"
        cards.append(
            "<article class='panel'>"
            f"<h2>{escape(str(item.get('title', 'Untitled evidence')))}</h2>"
            "<div class='meta-row'>"
            f"<span class='badge'>{escape(str(item.get('source_type', '')))}</span>"
            f"<span class='badge'>{escape(str(item.get('location', '')))}</span>"
            f"<span class='badge'>retrieval: {escape(str(item.get('retrieval_score', 'not searched')))}</span>"
            f"<span class='badge'>rerank: {escape(str(item.get('rerank_score', 'not reranked')))}</span>"
            "</div>"
            f"<p class='small muted'>Source: {escape(str(item.get('source_id', '')))} · document: {escape(str(item.get('document_id', '')))}</p>"
            "<h3>Provenance path</h3>"
            f"<ol class='small'>{provenance_content}</ol>"
            "</article>"
        )
    body = "<section class='stack'>" + "".join(cards or ["<article class='panel'><p class='muted'>No indexed evidence is available. Ingested document bodies are intentionally not shown here.</p></article>"]) + "</section>"
    return layout(
        title="Evidence Provenance",
        subtitle="Source → parser/OCR when required → chunk → embedding → retrieval → rerank → ResearchCampaign reference.",
        body=body,
        nav="<div class='page-nav'><a class='action' href='/specialists'>Specialists</a><a class='action' href='/research-table/start'>Research Table</a></div>",
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

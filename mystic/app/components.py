from __future__ import annotations

from html import escape
import json
import re
from typing import Any
from urllib.parse import urlencode


BASE_CSS = """
<style>
:root {
  --bg-0: #0b1020;
  --bg-1: #111827;
  --bg-2: #162033;
  --bg-3: #1b2638;
  --panel: rgba(17, 24, 39, 0.88);
  --panel-strong: #111827;
  --panel-soft: rgba(22, 32, 51, 0.72);
  --line: rgba(148, 163, 184, 0.18);
  --line-strong: rgba(148, 163, 184, 0.28);
  --text-strong: #e5edf7;
  --text-muted: #93a4b8;
  --text-dim: #718198;
  --accent-indigo: #6d5efc;
  --accent-purple: #8b5cf6;
  --ok: #22c55e;
  --warn: #f59e0b;
  --fail: #ef4444;
  --unknown: #94a3b8;
  --info: #38bdf8;
  --shadow-1: 0 1px 2px rgba(0,0,0,0.22);
  --shadow-2: 0 12px 24px rgba(0,0,0,0.28);
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 14px;
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 24px;
  --font-ui: "Geist Sans", "IBM Plex Sans", "SF Pro Text", "Inter", sans-serif;
  --font-mono: "Berkeley Mono", "JetBrains Mono", "SF Mono", "Menlo", monospace;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: linear-gradient(180deg, var(--bg-0), var(--bg-1)); color: var(--text-strong); }
body { font-family: var(--font-ui); line-height: 1.5; }
a { color: #c8d3f7; text-decoration: none; }
a:hover { text-decoration: underline; }
main.page {
  width: min(1600px, calc(100vw - 24px));
  margin: 0 auto;
  padding: 16px 0 40px;
}
.shell {
  display: grid;
  gap: 16px;
}
.topbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  padding: 18px 20px;
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: linear-gradient(180deg, rgba(17,24,39,0.94), rgba(17,24,39,0.78));
  box-shadow: var(--shadow-2);
}
.topbar-left { display: grid; gap: 8px; }
.eyebrow {
  font-size: 11px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--accent-indigo);
}
.title {
  margin: 0;
  font-size: clamp(26px, 3.2vw, 40px);
  line-height: 1.05;
  font-weight: 650;
}
.subtitle {
  margin: 0;
  color: var(--text-muted);
  font-size: 14px;
  max-width: 880px;
}
.page-nav {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.workspace-grid {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr) 360px;
  gap: 16px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
}
.panel {
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: var(--panel);
  box-shadow: var(--shadow-1);
  padding: 16px;
  min-width: 0;
}
.panel h2, .panel h3, .panel h4 {
  margin: 0 0 10px;
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0.01em;
}
.panel h2 { font-size: 15px; }
.stack { display: grid; gap: 12px; }
.substack { display: grid; gap: 8px; }
.section-sep {
  border-top: 1px solid var(--line);
  margin-top: 8px;
  padding-top: 12px;
}
.muted { color: var(--text-muted); }
.dim { color: var(--text-dim); }
.small { font-size: 12px; }
.mono, code, pre, .object-id {
  font-family: var(--font-mono);
  font-size: 12px;
}
pre.content, .content {
  white-space: pre-wrap;
  word-break: break-word;
}
.content {
  color: var(--text-strong);
  font-size: 13px;
}
.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.chip, .badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 26px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: rgba(255,255,255,0.02);
  color: var(--text-muted);
  font-size: 11px;
  line-height: 1;
}
.badge.ok, .badge.proved, .badge.tested, .badge.ready, .badge.completed, .badge.accepted, .badge.verified {
  color: #b8f5ca;
  border-color: rgba(34, 197, 94, 0.28);
  background: rgba(34, 197, 94, 0.12);
}
.badge.warn, .badge.heuristic, .badge.needs_more_detail, .badge.auth_required, .badge.running, .badge.verify {
  color: #ffd58a;
  border-color: rgba(245, 158, 11, 0.28);
  background: rgba(245, 158, 11, 0.12);
}
.badge.fail, .badge.failed, .badge.refuted, .badge.error {
  color: #ffc0c0;
  border-color: rgba(239, 68, 68, 0.28);
  background: rgba(239, 68, 68, 0.12);
}
.badge.neutral, .badge.unknown, .badge.blocked, .badge.tool {
  color: #c9d4e7;
  border-color: rgba(148, 163, 184, 0.22);
  background: rgba(148, 163, 184, 0.08);
}
.badge.arena, .badge.discovery {
  color: #d4cbff;
  border-color: rgba(139, 92, 246, 0.28);
  background: rgba(139, 92, 246, 0.14);
}
.warning-banner {
  border: 1px solid var(--line-strong);
  border-left: 3px solid var(--warn);
  border-radius: var(--radius-md);
  padding: 12px 14px;
  background: rgba(245, 158, 11, 0.08);
}
.warning-banner.error { border-left-color: var(--fail); background: rgba(239, 68, 68, 0.1); }
.warning-banner.info { border-left-color: var(--info); background: rgba(56, 189, 248, 0.08); }
.warning-banner.success { border-left-color: var(--ok); background: rgba(34, 197, 94, 0.08); }
.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.action, .action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 34px;
  padding: 0 12px;
  border-radius: 10px;
  border: 1px solid var(--line);
  background: rgba(255,255,255,0.02);
  color: var(--text-strong);
  font-size: 12px;
  font-weight: 520;
}
button.action, button.action-btn { cursor: pointer; }
.action.primary, .action-btn.primary {
  border-color: rgba(109, 94, 252, 0.32);
  background: linear-gradient(180deg, rgba(109, 94, 252, 0.24), rgba(109, 94, 252, 0.16));
}
.action.disabled, .action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.field-label {
  display: block;
  margin-bottom: 6px;
  color: var(--text-muted);
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.field, textarea, select, input[type='text'] {
  width: 100%;
  border-radius: 10px;
  border: 1px solid var(--line);
  background: rgba(11,16,32,0.72);
  color: var(--text-strong);
  padding: 10px 12px;
  font: inherit;
}
textarea { min-height: 120px; resize: vertical; }
.participants {
  display: grid;
  gap: 10px;
}
.participant-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 10px;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: rgba(255,255,255,0.02);
}
.participant-card input { margin-top: 3px; }
.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
}
.status-card {
  border: 1px solid var(--line);
  border-radius: 12px;
  background: rgba(255,255,255,0.02);
  padding: 12px;
}
.status-card h4 { margin: 0 0 8px; font-size: 12px; }
.phase-stepper {
  display: grid;
  gap: 6px;
}
.phase-step {
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: rgba(255,255,255,0.02);
}
.phase-step.active {
  border-color: rgba(109, 94, 252, 0.36);
  background: rgba(109, 94, 252, 0.12);
}
.turn, .object-card, .list-card, .discovery-card, .request-card {
  border: 1px solid var(--line);
  border-radius: 12px;
  background: rgba(255,255,255,0.02);
  padding: 14px;
  min-width: 0;
}
.turn.tool { background: rgba(56, 189, 248, 0.06); }
.turn.critic { background: rgba(139, 92, 246, 0.08); }
.turn-alert {
  border: 1px solid rgba(239, 68, 68, 0.24);
  border-radius: 10px;
  background: rgba(239, 68, 68, 0.08);
  padding: 10px 12px;
  margin-bottom: 10px;
}
.phase-section {
  border: 1px solid var(--line);
  border-radius: 12px;
  background: rgba(255,255,255,0.02);
  padding: 14px;
}
.phase-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}
.turn-discoveries {
  display: grid;
  gap: 8px;
  margin-bottom: 10px;
}
.turn-discovery {
  border: 1px solid var(--line);
  border-radius: 10px;
  background: rgba(255,255,255,0.02);
  padding: 10px 12px;
}
.turn-discovery.refuted {
  border-color: rgba(239, 68, 68, 0.25);
  background: rgba(239, 68, 68, 0.08);
}
.turn-discovery.verified, .turn-discovery.accepted {
  border-color: rgba(34, 197, 94, 0.25);
  background: rgba(34, 197, 94, 0.08);
}
.discovery-grid {
  display: grid;
  gap: 10px;
}
.report-preview {
  display: grid;
  gap: 10px;
}
.kv-list {
  display: grid;
  gap: 8px;
}
.kv {
  display: grid;
  gap: 3px;
}
.kv-label {
  color: var(--text-dim);
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.kv-value {
  font-size: 13px;
}
.split {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.workspace-left, .workspace-center, .workspace-right {
  display: grid;
  align-content: start;
  gap: 12px;
}
.workspace-left, .workspace-right {
  position: sticky;
  top: 16px;
  max-height: calc(100vh - 32px);
  overflow: auto;
  padding-right: 2px;
}
.report-markdown, .notebook-markdown {
  border: 1px solid var(--line);
  border-radius: 12px;
  background: rgba(11, 16, 32, 0.48);
  padding: 12px;
  white-space: pre-wrap;
}
.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.filter-row form {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  width: 100%;
}
.inline-form {
  display: inline-flex;
}
@media (max-width: 1180px) {
  .workspace-grid { grid-template-columns: 250px minmax(0, 1fr); }
  .workspace-right { grid-column: 1 / -1; position: static; max-height: none; overflow: visible; }
}
@media (max-width: 900px) {
  .workspace-grid { grid-template-columns: 1fr; }
  .workspace-left, .workspace-right { position: static; max-height: none; overflow: visible; }
  .topbar { grid-template-columns: 1fr; display: grid; }
}
</style>
"""


LAB_PHASE_SEQUENCE = [
    ("problem_intake", "Problem Intake"),
    ("background_scan", "Background Scan"),
    ("hypothesis_generation", "Hypothesis Generation"),
    ("experiment_design", "Experiment Design"),
    ("simulation_or_execution", "Simulation / Execution"),
    ("referee_review", "Referee Review"),
    ("failure_archive", "Failure Archive"),
    ("knowledge_update", "Knowledge Update"),
    ("next_experiment_planning", "Next Experiment Planning"),
    ("report_generation", "Report Generation"),
]


def layout(*, title: str, subtitle: str, body: str, nav: str = "") -> str:
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{escape(title)}</title>{BASE_CSS}</head><body>"
        "<main class='page'><div class='shell'>"
        "<section class='topbar'>"
        "<div class='topbar-left'>"
        "<div class='eyebrow'>Mystic Research OS</div>"
        f"<h1 class='title'>{escape(title)}</h1>"
        f"<p class='subtitle'>{escape(subtitle)}</p>"
        "</div>"
        f"{nav}"
        "</section>"
        f"{body}</div></main></body></html>"
    )


def StatusBadge(status: str, *, label: str | None = None) -> str:
    normalized = _normalize_status_key(status)
    badge_class = {
        "proved": "proved",
        "tested": "tested",
        "ready": "ready",
        "completed": "completed",
        "verified": "verified",
        "accepted": "accepted",
        "supports": "tested",
        "heuristic": "heuristic",
        "needs_more_detail": "needs_more_detail",
        "auth_required": "auth_required",
        "running": "running",
        "draft_only": "heuristic",
        "revision": "running",
        "failed": "failed",
        "refuted": "refuted",
        "error": "error",
        "invalid": "refuted",
        "auth_req": "auth_required",
        "unknown": "unknown",
        "blocked": "blocked",
        "inconclusive": "unknown",
        "saved": "completed",
        "verification_result": "verified",
        "model_outputs_only": "unknown",
    }.get(normalized, "neutral")
    return f"<span class='badge {badge_class}'>{escape(label or _display_status_label(status))}</span>"


def WarningBanner(*, message: str, level: str = "warning", title: str | None = None) -> str:
    heading = f"<strong>{escape(title)}</strong><br>" if title else ""
    return f"<section class='warning-banner {escape(level)}'>{heading}{escape(message)}</section>"


def PhaseStepper(*, current_phase: str, mode: str = "", active_room: str = "") -> str:
    steps = []
    for phase_key, phase_label in LAB_PHASE_SEQUENCE:
        active = " active" if phase_key == current_phase else ""
        steps.append(
            "<div class='phase-step%s'>" % active
            + f"<div class='meta-row'><span class='badge'>{escape(phase_label)}</span>"
            + (StatusBadge(mode, label=mode) if active and mode else "")
            + "</div>"
            + (f"<p class='small muted'>{escape(active_room)}</p>" if phase_key == current_phase and active_room else "")
            + "</div>"
        )
    return "<section class='panel'><h2>Phase Navigation</h2><div class='phase-stepper'>" + "".join(steps) + "</div></section>"


def ProviderStatusPanel(*, status: dict[str, Any]) -> str:
    models = status.get("models", {})
    cards = [
        _status_card("MCP Server", str(status.get("mcp_server_status", "unknown"))),
        _status_card("Local Backend", "READY" if status.get("mcp_server_status") == "ready" else "UNKNOWN"),
        _status_card("Verifier", _tool_ready_label(status, "mystic_verify_answer")),
        _status_card("Research Table", _tool_ready_label(status, "mystic_run_research_table")),
        _status_card("Raven Training", "READY" if status.get("adapter_status", {}).get("available") else "UNKNOWN"),
    ]
    for model_id in ["gemini_cli", "claude_cli"]:
        if model_id in models:
            cards.append(_provider_card(model_id, models[model_id]))
    local_models = [
        _provider_card(model_id, payload)
        for model_id, payload in models.items()
        if str(payload.get("provider", "")) in {"ollama", "local_adapter"}
    ][:4]
    cards.extend(local_models)
    return "<section class='panel'><h2>Provider / MCP Settings</h2><div class='status-grid'>" + "".join(cards) + "</div></section>"


def AgentTurnCard(*, turn: dict[str, Any], prelude_html: str = "", session_id: str = "", room_override: str = "") -> str:
    speaker_type = str(turn.get("speaker_type", "model"))
    extra_class = " tool" if speaker_type == "tool" else " critic" if str(turn.get("role", "")) in {"critique", "critic"} else ""
    room = room_override or str(turn.get("room", turn.get("phase", "")))
    extracted_claims = turn.get("extracted_claims") or []
    claim_badges = "".join(
        StatusBadge(str(item.get("status", "HEURISTIC")), label=str(item.get("status", "HEURISTIC")))
        + f"<span class='badge arena'>{escape(str(item.get('claim_type', 'claim')))}</span>"
        for item in extracted_claims[:4]
    )
    requested_tools = "".join(f"<span class='badge tool'>{escape(str(item))}</span>" for item in turn.get("requested_tools", [])[:4])
    tool_results = turn.get("tool_results") or []
    tool_preview = ""
    if tool_results:
        tool_preview = "<div class='section-sep substack'>" + "".join(
            f"<div class='small muted mono'>{escape(json.dumps(item, ensure_ascii=False)[:220])}</div>"
            for item in tool_results[:2]
        ) + "</div>"
    timestamp = str(turn.get("created_at", turn.get("timestamp", "")))
    provider = str(turn.get("provider", ""))
    model_name = _display_model_name(turn.get("model_name", ""))
    agent_role = str(turn.get("agent_role", turn.get("speaker_id", "agent")))
    header = (
        "<div class='meta-row'>"
        f"<span class='badge'>{escape(agent_role)}</span>"
        f"<span class='badge'>{escape(room)}</span>"
        f"<span class='badge'>{escape(provider)}</span>"
        f"<span class='badge'>{escape(model_name)}</span>"
        f"{StatusBadge(str(turn.get('status', 'UNKNOWN')))}"
        "</div>"
    )
    provenance = (
        "<div class='meta-row small muted'>"
        f"<span>phase: <span class='mono'>{escape(str(turn.get('phase', '')))}</span></span>"
        f"<span>role: <span class='mono'>{escape(str(turn.get('role', turn.get('agent_role', ''))))}</span></span>"
        + (f"<span>at: <span class='mono'>{escape(timestamp)}</span></span>" if timestamp else "")
        + "</div>"
    )
    extracted = f"<div class='meta-row'>{claim_badges}{requested_tools}</div>" if (claim_badges or requested_tools) else ""
    output_key = "output" if "output" in turn else "content"
    return (
        f"<article class='turn{extra_class}' id='{escape(_turn_anchor_id(str(turn.get('turn_id', ''))))}'>"
        f"{header}{provenance}"
        f"{prelude_html}"
        + (
            f"<div class='section-sep'><div class='kv'><div class='kv-label'>Input summary</div><div class='kv-value'>{escape(str(turn.get('input_summary', '')))}</div></div></div>"
            if turn.get("input_summary")
            else ""
        )
        + (f"<div class='section-sep'>{extracted}</div>" if extracted else "")
        + f"<div class='section-sep'><div class='content'>{escape(str(turn.get(output_key, '')))}</div></div>"
        + tool_preview
        + _turn_reply_footer(turn)
        + _turn_action_row(session_id=session_id, turn=turn)
        + "</article>"
    )


def ClaimCard(*, claim: dict[str, Any]) -> str:
    supporting = claim.get("supporting_evidence") or []
    refuting = claim.get("refuting_evidence") or []
    experiments = claim.get("related_experiments") or []
    failures = claim.get("related_failures") or []
    status = str(claim.get("status", "UNKNOWN"))
    return (
        "<article class='object-card'>"
        "<div class='meta-row'>"
        f"<span class='badge arena'>{escape(str(claim.get('claim_type', 'claim')))}</span>"
        f"{StatusBadge(status)}"
        f"<span class='badge'>{escape(str(claim.get('confidence', '')))}</span>"
        "</div>"
        f"<div class='section-sep'><div class='content'><strong>{escape(str(claim.get('text', '')))}</strong></div></div>"
        "<div class='section-sep kv-list'>"
        + _kv("Source turn", f"<code>{escape(str(claim.get('source_turn_id', '')))}</code>")
        + _kv("Supporting evidence", _mono_list(supporting) or "<span class='muted'>No supporting evidence</span>")
        + _kv("Refuting evidence", _mono_list(refuting) or "<span class='muted'>No refuting evidence</span>")
        + _kv("Related experiments", _mono_list(experiments) or "<span class='muted'>None</span>")
        + _kv("Related failures", _mono_list(failures) or "<span class='muted'>None</span>")
        + _kv("Updated", f"<code>{escape(str(claim.get('updated_at', '')))}</code>" if claim.get("updated_at") else "<span class='muted'>Unknown</span>")
        + "</div></article>"
    )


def ExperimentCard(*, experiment: dict[str, Any], session_id: str = "", enable_actions: bool = True) -> str:
    experiment_id = str(experiment.get("experiment_id", ""))
    action_row = ""
    if enable_actions:
        buttons = []
        if session_id and experiment_id:
            buttons.append(_action_form(action=f"/lab/sessions/{session_id}/experiments/{experiment_id}/run", label="Run Experiment"))
            buttons.append(_action_form(action=f"/lab/sessions/{session_id}/experiments/{experiment_id}/run", label="Dry Run", params={"dry_run": "true"}))
        else:
            buttons.append("<span class='action disabled'>Run unavailable</span>")
        action_row = f"<div class='action-row section-sep'>{''.join(buttons)}</div>"
    return (
        "<article class='object-card'>"
        "<div class='meta-row'>"
        f"<span class='badge arena'>{escape(str(experiment.get('method', '')))}</span>"
        f"{StatusBadge(str(experiment.get('verdict', 'inconclusive')))}"
        "</div>"
        f"<div class='section-sep'><div class='content'><strong>{escape(str(experiment.get('question', '')))}</strong></div></div>"
        "<div class='section-sep kv-list'>"
        + _kv("Linked claim", f"<code>{escape(str(experiment.get('claim_id', '')))}</code>")
        + _kv("Inputs", f"<pre class='content mono'>{escape(json.dumps(experiment.get('inputs', {}), ensure_ascii=False, indent=2))}</pre>")
        + _kv("Outputs", f"<pre class='content mono'>{escape(json.dumps(experiment.get('outputs', {}), ensure_ascii=False, indent=2))}</pre>")
        + _kv("Evidence summary", escape(str(experiment.get("evidence_summary", ""))) or "<span class='muted'>No evidence summary</span>")
        + "</div>"
        + action_row
        + "</article>"
    )


def FailureCard(*, failure: dict[str, Any], enable_export: bool = False) -> str:
    export_control = (
        "<span class='action'>Export to Raven</span>"
        if enable_export
        else "<span class='action disabled' title='Failure export is not wired yet'>Export to Raven</span>"
    )
    return (
        "<article class='object-card'>"
        "<div class='meta-row'>"
        f"{StatusBadge(str(failure.get('failure_type', 'FAILED')), label=str(failure.get('failure_type', 'failure')))}"
        f"<span class='badge'>{escape('training data' if failure.get('reusable_as_training_data') else 'local only')}</span>"
        "</div>"
        f"<div class='section-sep'><div class='content'><strong>{escape(str(failure.get('first_fatal_error', '')))}</strong></div></div>"
        "<div class='section-sep kv-list'>"
        + _kv("Failed claim", f"<code>{escape(str(failure.get('claim_id', '')))}</code>")
        + _kv("Source turn", f"<code>{escape(str(failure.get('source_turn_id', '')))}</code>")
        + _kv("Lesson", escape(str(failure.get("lesson", ""))) or "<span class='muted'>No lesson recorded</span>")
        + "</div>"
        + f"<div class='action-row section-sep'>{export_control}</div>"
        + "</article>"
    )


def MemoryEdgeList(*, edges: list[dict[str, Any]]) -> str:
    if not edges:
        return WarningBanner(message="No memory edges recorded yet.", level="info", title="Memory Graph")
    items = []
    for edge in edges:
        items.append(
            "<article class='list-card'>"
            f"<div class='meta-row'>{StatusBadge(str(edge.get('relation', 'unknown')), label=str(edge.get('relation', 'unknown')))}</div>"
            f"<p class='small mono'><code>{escape(str(edge.get('from_id', '')))}</code> -> <code>{escape(str(edge.get('to_id', '')))}</code></p>"
            f"<div class='content'>{escape(str(edge.get('evidence', '')))}</div>"
            "</article>"
        )
    return "<div class='stack'>" + "".join(items) + "</div>"


def LabActionBar(
    *,
    session_id: str,
    has_claims: bool,
    has_experiments: bool,
    model_arena_available: bool = True,
    report_available: bool = True,
    referee_available: bool = True,
) -> str:
    buttons = [
        _action_form(action=f"/lab/sessions/{session_id}/advance", label="Advance Session", button_class="action primary"),
    ]
    if referee_available:
        buttons.append(
            _action_form(
                action=f"/lab/sessions/{session_id}/referee-review",
                label="Run Referee Review",
                disabled=not has_claims,
                disabled_reason="No claims yet",
            )
        )
    if has_claims:
        buttons.append(_action_form(action=f"/lab/sessions/{session_id}/experiments/create", label="Create Experiment"))
    else:
        buttons.append("<span class='action disabled' title='No linked claim'>Create Experiment</span>")
    if has_experiments:
        buttons.append(_action_form(action=f"/lab/sessions/{session_id}/experiments/run-latest", label="Run Experiment"))
    else:
        buttons.append("<span class='action disabled' title='No experiments yet'>Run Experiment</span>")
    if model_arena_available:
        buttons.append(_action_form(action=f"/lab/sessions/{session_id}/model-arena", label="Launch Model Arena"))
    if report_available:
        buttons.append(_action_form(action=f"/lab/sessions/{session_id}/report", label="Generate Report"))
    buttons.append("<span class='action disabled' title='Memory write UI is not wired yet'>Save to Memory</span>")
    buttons.append("<span class='action disabled' title='Failure export UI is not wired yet'>Export Failure for Raven</span>")
    return "<section class='panel'><h2>LabActionBar</h2><div class='action-row'>" + "".join(buttons) + "</div></section>"


def ReportPreview(*, session: dict[str, Any], report_markdown: str) -> str:
    session_meta = session.get("session", session)
    claims = session.get("claims", [])
    experiments = session.get("experiments", [])
    failures = session.get("failures", [])
    surviving = [item for item in claims if str(item.get("status", "")).upper() in {"PROVED", "TESTED"}]
    failed = [item for item in claims if str(item.get("status", "")).upper() in {"FAILED", "REFUTED", "NEEDS_MORE_DETAIL"}]
    if not report_markdown.strip():
        return WarningBanner(message="No report generated yet.", level="info", title="Report Preview")
    return (
        "<section class='panel report-preview'><h2>ReportPreview</h2>"
        + _kv("Report title", escape(f"Mystic Lab Report {session_meta.get('session_id', '')}"))
        + _kv("Problem", escape(str(session_meta.get("problem", ""))))
        + _kv("Surviving claims", f"<code>{len(surviving)}</code>")
        + _kv("Failed claims", f"<code>{len(failed)}</code>")
        + _kv("Experiments", f"<code>{len(experiments)}</code>")
        + _kv("Limitations", "Reflected in failed claims and referee findings.")
        + _kv("Next work", ", ".join(escape(str(item)) for item in session.get("next_actions", [])) or "No next work recorded")
        + f"<div class='section-sep report-markdown'>{escape(report_markdown)}</div>"
        + "<div class='action-row'><span class='action'>Export Markdown</span></div>"
        + "</section>"
    )


def ParticipantSelector(*, participants: list[dict[str, Any]]) -> str:
    cards = []
    for participant in participants:
        auth_state = str(participant.get("auth_state", "unknown"))
        auth_badge = StatusBadge(auth_state.upper(), label=_participant_status_label(auth_state))
        auth_message = str(participant.get("auth_message", "")).strip()
        cards.append(
            "<label class='participant-card'>"
            f"<input type='checkbox' name='participants' value='{escape(str(participant['model_id']))}' "
            f"{'checked' if participant.get('checked') else ''}>"
            "<div class='substack'>"
            f"<div class='meta-row'><strong>{escape(str(participant['label']))}</strong>{auth_badge}</div>"
            f"<div class='small muted'>{escape(str(participant['provider']))} / <span class='mono'>{escape(str(participant['model_name']))}</span></div>"
            f"{f'<div class=\"small dim\">{escape(auth_message)}</div>' if auth_message else ''}"
            f"<div class='meta-row'>{''.join(f'<span class=\"chip\">{escape(role)}</span>' for role in participant.get('roles', []))}</div>"
            "</div></label>"
        )
    return "<div class='participants'>" + "".join(cards) + "</div>"


def ProviderAuthCard(*, model_id: str, status: dict[str, Any], action_href: str) -> str:
    state = str(status.get("state", "unknown"))
    message = str(status.get("message", "Authentication required."))
    if "Google" in message:
        action = f"<a class='action primary' href='{escape(action_href)}'>Login with Google</a>"
    elif "Claude" in message:
        action = f"<a class='action primary' href='{escape(action_href)}'>Login with Claude</a>"
    elif state == "ready":
        action = "<span class='action'>Ready</span>"
    elif state == "missing":
        action = "<span class='action disabled'>CLI Missing</span>"
    elif state == "error":
        action = "<span class='action disabled'>Error</span>"
    else:
        action = "<span class='action disabled'>Review Status</span>"
    return (
        "<article class='panel'>"
        f"<div class='meta-row'><strong>{escape(_display_model_name(model_id))}</strong>{StatusBadge(state.upper(), label=_participant_status_label(state))}</div>"
        f"<p class='small muted'>{escape(message)}</p>"
        f"<div class='action-row'>{action}</div>"
        "</article>"
    )


def DiscoveryCard(*, discovery: dict[str, Any], session_id: str = "") -> str:
    status = str(discovery.get("status", "proposed"))
    evidence = "Tool evidence attached" if not discovery.get("needs_verification", True) else "Needs deterministic review"
    return (
        "<article class='discovery-card'>"
        f"<div class='meta-row'><span class='badge arena'>{escape(str(discovery.get('type', 'strategy')))}</span>{StatusBadge(status)}</div>"
        f"<div class='section-sep'><div class='content'><strong>{escape(str(discovery.get('claim', '')))}</strong></div></div>"
        f"<p class='small muted'>{escape(str(discovery.get('rationale', '')))}</p>"
        f"<p class='small dim'>{escape(evidence)}</p>"
        f"{_discovery_action_row(session_id=session_id, discovery=discovery)}"
        "</article>"
    )


def VerificationRequestCard(*, request: dict[str, Any]) -> str:
    return (
        "<article class='request-card'>"
        f"<div class='meta-row'><span class='badge tool'>{escape(str(request.get('tool', 'tool')))}</span>{StatusBadge(str(request.get('status', 'pending')))}</div>"
        f"<div class='section-sep'><div class='content'>{escape(str(request.get('question', '')))}</div></div>"
        f"<p class='small muted'>Target turn: <code>{escape(str(request.get('target_turn_id', '')) or '-')}</code></p>"
        "</article>"
    )


def ToolEvidenceCard(*, turn: dict[str, Any], prelude_html: str = "", session_id: str = "") -> str:
    return AgentTurnCard(turn=turn, prelude_html=prelude_html, session_id=session_id)


def ModelTurnCard(*, turn: dict[str, Any], prelude_html: str = "", session_id: str = "") -> str:
    return AgentTurnCard(turn=turn, prelude_html=prelude_html, session_id=session_id)


def CritiqueTurnCard(*, turn: dict[str, Any], prelude_html: str = "", session_id: str = "") -> str:
    return AgentTurnCard(turn=turn, prelude_html=prelude_html, session_id=session_id)


def DebateTurnCard(*, turn: dict[str, Any], discoveries: list[dict[str, Any]] | None = None, session_id: str = "") -> str:
    discoveries = discoveries or []
    prelude = _highlighted_discoveries(discoveries)
    if discoveries:
        prelude += "<div class='turn-discoveries'>" + "".join(_turn_discovery_block(item) for item in discoveries) + "</div>"
    return AgentTurnCard(turn=turn, prelude_html=prelude, session_id=session_id)


def DebateRound(*, round_index: int, phase: str, turns: list[dict[str, Any]]) -> str:
    cards = "".join(DebateTurnCard(turn=turn) for turn in turns)
    return (
        "<section class='phase-section'>"
        f"<div class='phase-header'><h3>Round {round_index} · {escape(phase)}</h3><span class='small muted'>{len(turns)} turns</span></div>"
        f"<div class='stack'>{cards}</div></section>"
    )


def DebateTimeline(*, turns: list[dict[str, Any]]) -> str:
    grouped: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for turn in turns:
        key = (int(turn.get("round_index", 0)), str(turn.get("phase", "")))
        grouped.setdefault(key, []).append(turn)
    html = []
    for (round_index, phase) in sorted(grouped.keys()):
        html.append(DebateRound(round_index=round_index, phase=phase, turns=grouped[(round_index, phase)]))
    return "<div class='stack'>" + "".join(html) + "</div>"


def ResearchPhaseSection(*, phase: str, turns: list[dict[str, Any]], discoveries_by_turn: dict[str, list[dict[str, Any]]], session_id: str = "") -> str:
    cards = "".join(
        DebateTurnCard(turn=turn, discoveries=discoveries_by_turn.get(str(turn.get("turn_id", "")), []), session_id=session_id)
        for turn in turns
    )
    return (
        "<section class='phase-section'>"
        f"<div class='phase-header'><h3>{escape(_phase_label(phase))}</h3><span class='small muted'>{len(turns)} turns</span></div>"
        f"<div class='stack'>{cards or WarningBanner(message='No turns recorded for this phase.', level='info')}</div></section>"
    )


def FinalJudgePanel(*, content: str) -> str:
    return "<section class='panel'><h2>Final Judge</h2><div class='report-markdown'>" + escape(content) + "</div></section>"


def FinalSynthesisPanel(*, synthesis: dict[str, Any], session_id: str = "") -> str:
    accepted = "".join(DiscoveryCard(discovery=item, session_id=session_id) for item in synthesis.get("accepted_discoveries", []))
    rejected = "".join(DiscoveryCard(discovery=item, session_id=session_id) for item in synthesis.get("rejected_discoveries", []))
    return (
        "<section class='panel'>"
        "<h2>FinalSynthesisPanel</h2>"
        f"<div class='meta-row'>{StatusBadge(str(synthesis.get('final_status', 'UNKNOWN')))}<span class='badge arena'>{escape(str(synthesis.get('final_decision_source', 'model_outputs')))}</span></div>"
        "<div class='split section-sep'>"
        f"<section><h3>Accepted Discoveries</h3><div class='discovery-grid'>{accepted or WarningBanner(message='No accepted discoveries.', level='info')}</div></section>"
        f"<section><h3>Rejected Discoveries</h3><div class='discovery-grid'>{rejected or WarningBanner(message='No rejected discoveries.', level='info')}</div></section>"
        "</div></section>"
    )


def DisagreementPanel(*, rejected_discoveries: list[dict[str, Any]]) -> str:
    if not rejected_discoveries:
        return "<section class='panel'><h2>Disagreement Panel</h2>" + WarningBanner(message="No explicit rejected discoveries recorded.", level="info") + "</section>"
    body = "".join(DiscoveryCard(discovery=discovery) for discovery in rejected_discoveries)
    return f"<section class='panel'><h2>Disagreement Panel</h2><div class='discovery-grid'>{body}</div></section>"


def SaveTeacherLabelButton() -> str:
    return "<span class='action'>Save as Raven training data</span>"


def SaveRavenTrainingDataButton() -> str:
    return "<span class='action'>Save as Raven training data</span>"


def SavePrimeStrategyDataButton() -> str:
    return "<span class='action'>Save as Prime strategy data</span>"


def SaveForgeExperimentTaskButton() -> str:
    return "<span class='action'>Save as Forge experiment task</span>"


def ExportTeacherPacketButton() -> str:
    return "<span class='action'>Export teacher packet</span>"


def RunVerifierButton() -> str:
    return "<span class='action'>Re-run verifier</span>"


def AskAnotherModelToCritiqueButton() -> str:
    return "<span class='action'>Ask another model to critique</span>"


def AskModelToExtendDiscoveryButton() -> str:
    return "<span class='action'>Ask model to extend discovery</span>"


def AskModelToFormalizeDiscoveryButton() -> str:
    return "<span class='action'>Formalize as lemma</span>"


def AskModelToReviseAfterEvidenceButton() -> str:
    return "<span class='action'>Revise after evidence</span>"


def _status_card(label: str, status_value: str) -> str:
    return (
        "<article class='status-card'>"
        f"<h4>{escape(label)}</h4>"
        f"<div class='meta-row'>{StatusBadge(status_value)}</div>"
        "</article>"
    )


def _provider_card(model_id: str, payload: dict[str, Any]) -> str:
    status = payload.get("status", {})
    return (
        "<article class='status-card'>"
        f"<h4>{escape(_display_model_name(model_id))}</h4>"
        f"<div class='meta-row'>{StatusBadge(str(status.get('state', 'unknown')))}<span class='badge'>{escape(str(payload.get('provider', '')))}</span></div>"
        f"<p class='small muted mono'>{escape(str(payload.get('model_name', model_id)))}</p>"
        f"<p class='small dim'>{escape(str(status.get('message', '')))}</p>"
        "</article>"
    )


def _tool_ready_label(status: dict[str, Any], tool_name: str) -> str:
    tool_state = str(status.get("tools", {}).get(tool_name, "unknown"))
    return "READY" if tool_state == "ready" else tool_state.upper()


def _turn_discovery_block(discovery: dict[str, Any]) -> str:
    status = str(discovery.get("status", "proposed")).lower()
    return (
        f"<div class='turn-discovery {escape(status)}'>"
        f"<div class='meta-row'>{StatusBadge(status)}<span class='badge arena'>{escape(str(discovery.get('type', 'strategy')))}</span></div>"
        f"<p class='small'><strong>{escape(str(discovery.get('claim', '')))}</strong></p>"
        f"<p class='small muted'>{escape(str(discovery.get('rationale', '')))}</p>"
        "</div>"
    )


def _highlighted_discoveries(discoveries: list[dict[str, Any]]) -> str:
    refuted = [item for item in discoveries if str(item.get("status", "")).lower() == "refuted"]
    if not refuted:
        return ""
    body = "".join(f"<p class='small'><strong>{escape(str(item.get('claim', '')))}</strong></p>" for item in refuted[:3])
    return f"<div class='turn-alert'><div class='meta-row'>{StatusBadge('REFUTED')}</div>{body}</div>"


def _turn_reply_footer(turn: dict[str, Any]) -> str:
    reply_to = turn.get("reply_to", [])
    if not reply_to:
        return ""
    links = [
        f"<a href='#{escape(_turn_anchor_id(str(value)))}'><code>{escape(str(value))}</code></a>"
        for value in reply_to if str(value)
    ]
    if not links:
        return ""
    return f"<div class='section-sep small muted'>Replies to: {', '.join(links)}</div>"


def _display_model_name(value: Any) -> str:
    raw = str(value)
    lowered = raw.lower()
    if lowered in {"gemini cli", "gemini_cli"}:
        return "Gemini CLI"
    if lowered in {"claude cli", "claude_cli"}:
        return "Claude CLI"
    return raw


def _display_status_label(status: str) -> str:
    return str(status).replace("_", " ").title()


def _normalize_status_key(status: str) -> str:
    return str(status).strip().lower().replace(" ", "_")


def _phase_label(phase: str) -> str:
    lookup = {key: label for key, label in LAB_PHASE_SEQUENCE}
    if phase in lookup:
        return lookup[phase]
    return phase.replace("_", " ").title()


def _participant_status_label(state: str) -> str:
    return {
        "ready": "Ready",
        "not_authenticated": "Login Required",
        "auth_required": "Login Required",
        "missing": "CLI Missing",
        "error": "Error",
        "disabled": "Disabled",
    }.get(state, state.replace("_", " ").title())


def _turn_anchor_id(turn_id: str) -> str:
    if not turn_id:
        return "turn-unknown"
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", turn_id).strip("-")
    return f"turn-{normalized or 'unknown'}"


def _action_form(
    *,
    action: str,
    label: str,
    params: dict[str, str] | None = None,
    button_class: str = "action",
    disabled: bool = False,
    disabled_reason: str = "",
) -> str:
    if disabled:
        title = f" title='{escape(disabled_reason)}'" if disabled_reason else ""
        return f"<span class='{escape(button_class)} disabled'{title}>{escape(label)}</span>"
    query = urlencode(params or {})
    target = f"{action}?{query}" if query else action
    return (
        f"<form method='post' action='{escape(target)}' class='inline-form'>"
        f"<button class='{escape(button_class)}' type='submit'>{escape(label)}</button>"
        "</form>"
    )


def _discovery_action_row(*, session_id: str, discovery: dict[str, Any]) -> str:
    discovery_id = str(discovery.get("discovery_id", ""))
    if not session_id or not discovery_id:
        return (
            f"<div class='action-row'>{AskAnotherModelToCritiqueButton()} {AskModelToExtendDiscoveryButton()} "
            f"{AskModelToFormalizeDiscoveryButton()} {RunVerifierButton()} {SaveRavenTrainingDataButton()} "
            f"{SavePrimeStrategyDataButton()} {SaveForgeExperimentTaskButton()}</div>"
        )
    base = f"/research-table/{session_id}/discoveries/{discovery_id}"
    buttons = [
        _action_form(action=f"{base}/challenge", label="Ask another model to critique"),
        _action_form(action=f"{base}/extend", label="Ask model to extend discovery"),
        _action_form(action=f"{base}/formalize", label="Formalize as lemma"),
        _action_form(action=f"{base}/verify", label="Run verifier"),
        _action_form(action=f"{base}/save-training-item", label="Save as Raven training data", params={"target_agent": "raven"}),
        _action_form(action=f"{base}/save-training-item", label="Save as Prime strategy data", params={"target_agent": "prime"}),
        _action_form(action=f"{base}/save-training-item", label="Save as Forge experiment task", params={"target_agent": "forge"}),
    ]
    return f"<div class='action-row section-sep'>{''.join(buttons)}</div>"


def _turn_action_row(*, session_id: str, turn: dict[str, Any]) -> str:
    turn_id = str(turn.get("turn_id", ""))
    if not session_id or not turn_id:
        return ""
    buttons = []
    if str(turn.get("speaker_type", "model")) != "tool":
        base = f"/research-table/{session_id}/turns/{turn_id}"
        buttons.append(_action_form(action=f"{base}/revise", label="Revise after evidence"))
        buttons.append(_action_form(action=f"{base}/save-teacher-label", label="Save turn as teacher label"))
    return f"<div class='action-row section-sep'>{''.join(buttons)}</div>" if buttons else ""


def _kv(label: str, value_html: str) -> str:
    return f"<div class='kv'><div class='kv-label'>{escape(label)}</div><div class='kv-value'>{value_html}</div></div>"


def _mono_list(values: list[Any]) -> str:
    if not values:
        return ""
    return "<div class='meta-row'>" + "".join(f"<code class='object-id'>{escape(str(item))}</code>" for item in values) + "</div>"


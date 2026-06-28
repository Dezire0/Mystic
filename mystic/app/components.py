from __future__ import annotations

from html import escape
from typing import Any


BASE_CSS = """
<style>
:root {
  --bg: #f4efe6;
  --panel: rgba(255, 250, 242, 0.9);
  --panel-strong: #fffaf2;
  --ink: #1f1b18;
  --muted: #6f635a;
  --line: rgba(73, 52, 33, 0.18);
  --accent: #c6622a;
  --accent-2: #0b6e69;
  --warn: #ab2d2d;
  --ok: #266245;
  --shadow: 0 18px 40px rgba(63, 42, 25, 0.12);
}
* { box-sizing: border-box; }
body {
  margin: 0;
  color: var(--ink);
  background:
    radial-gradient(circle at top left, rgba(198, 98, 42, 0.16), transparent 28%),
    radial-gradient(circle at top right, rgba(11, 110, 105, 0.12), transparent 30%),
    linear-gradient(180deg, #f8f2e8 0%, var(--bg) 100%);
  font-family: "Avenir Next", "Trebuchet MS", "Segoe UI", sans-serif;
}
a { color: inherit; }
.page {
  width: min(1180px, calc(100vw - 32px));
  margin: 0 auto;
  padding: 28px 0 64px;
}
.hero {
  padding: 28px 30px;
  border-bottom: 1px solid var(--line);
  background: linear-gradient(135deg, rgba(255,255,255,0.72), rgba(255,247,235,0.92));
  border-radius: 24px;
  box-shadow: var(--shadow);
}
.eyebrow {
  font-size: 12px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--accent-2);
  margin-bottom: 10px;
}
.title {
  margin: 0;
  font-size: clamp(34px, 4vw, 56px);
  line-height: 0.96;
  font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", serif;
}
.subtitle {
  margin: 14px 0 0;
  max-width: 760px;
  color: var(--muted);
  font-size: 17px;
  line-height: 1.6;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 18px;
  margin-top: 22px;
}
.panel {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 22px;
  box-shadow: var(--shadow);
  padding: 22px;
}
.panel h2, .panel h3 {
  margin: 0 0 12px;
  font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", serif;
}
.muted { color: var(--muted); }
.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin: 10px 0 0;
}
.chip, .badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 12px;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: rgba(255,255,255,0.7);
  font-size: 12px;
  line-height: 1;
}
.badge.discovery { background: rgba(198, 98, 42, 0.12); color: #8b4319; }
.badge.verify { background: rgba(11, 110, 105, 0.12); color: #09534e; }
.badge.refuted { background: rgba(171, 45, 45, 0.12); color: var(--warn); }
.badge.accepted { background: rgba(38, 98, 69, 0.12); color: var(--ok); }
.badge.tool { background: rgba(17, 28, 61, 0.09); color: #283b72; }
.badge.auth { background: rgba(171, 45, 45, 0.08); color: var(--warn); }
.stack { display: grid; gap: 16px; }
.turn {
  position: relative;
  padding: 18px;
  border-radius: 18px;
  border: 1px solid var(--line);
  background: var(--panel-strong);
}
.turn.tool {
  background: linear-gradient(180deg, rgba(225, 235, 255, 0.7), rgba(247, 249, 255, 0.92));
}
.turn.critic {
  background: linear-gradient(180deg, rgba(255, 244, 231, 0.72), rgba(255, 250, 242, 0.92));
}
.turn .content, .discovery-claim, .request-question {
  white-space: pre-wrap;
  line-height: 1.55;
}
.round {
  border-left: 3px solid rgba(198, 98, 42, 0.32);
  padding-left: 18px;
}
.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 14px;
}
.action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 38px;
  padding: 0 14px;
  border-radius: 999px;
  border: 1px solid rgba(198, 98, 42, 0.22);
  background: white;
  color: var(--ink);
  text-decoration: none;
  font-size: 13px;
}
.action.primary {
  background: linear-gradient(135deg, var(--accent), #dd864c);
  color: white;
  border-color: transparent;
}
.field-label {
  display: block;
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 8px;
}
.field, textarea, select {
  width: 100%;
  border-radius: 14px;
  border: 1px solid var(--line);
  padding: 12px 14px;
  background: white;
  font: inherit;
}
textarea { min-height: 140px; resize: vertical; }
.participants {
  display: grid;
  gap: 12px;
}
.participant-card {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 14px;
  background: rgba(255,255,255,0.72);
}
.participant-card input { margin-top: 4px; }
.discovery-grid {
  display: grid;
  gap: 12px;
}
.discovery-card, .request-card {
  border: 1px solid var(--line);
  border-radius: 18px;
  background: rgba(255,255,255,0.78);
  padding: 16px;
}
.page-nav {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 16px;
}
.small { font-size: 13px; }
code { font-family: "SF Mono", "Menlo", "Monaco", monospace; font-size: 0.94em; }
</style>
"""


def layout(*, title: str, subtitle: str, body: str, nav: str = "") -> str:
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{escape(title)}</title>{BASE_CSS}</head><body>"
        "<main class='page'>"
        f"<section class='hero'><div class='eyebrow'>Mystic Research OS</div>"
        f"<h1 class='title'>{escape(title)}</h1>"
        f"<p class='subtitle'>{escape(subtitle)}</p>"
        f"{nav}</section>"
        f"{body}</main></body></html>"
    )


def ParticipantSelector(*, participants: list[dict[str, Any]]) -> str:
    cards = []
    for participant in participants:
        auth_badge = ""
        if participant.get("auth_state") == "not_authenticated":
            auth_badge = "<span class='badge auth'>Auth Required</span>"
        cards.append(
            "<label class='participant-card'>"
            f"<input type='checkbox' name='participants' value='{escape(str(participant['model_id']))}' "
            f"{'checked' if participant.get('checked') else ''}>"
            "<div>"
            f"<div><strong>{escape(str(participant['label']))}</strong> {auth_badge}</div>"
            f"<div class='small muted'>{escape(str(participant['provider']))} / {escape(str(participant['model_name']))}</div>"
            f"<div class='meta-row'>{''.join(f'<span class=\"chip\">{escape(role)}</span>' for role in participant.get('roles', []))}</div>"
            "</div></label>"
        )
    return "<div class='participants'>" + "".join(cards) + "</div>"


def ProviderAuthCard(*, model_id: str, status: dict[str, Any], action_href: str) -> str:
    action_label = "Login"
    message = str(status.get("message", "Authentication required."))
    if "Google" in message:
        action_label = "Login with Google"
    elif "Claude" in message:
        action_label = "Login with Claude"
    return (
        "<article class='panel'>"
        f"<h3>{escape(model_id)}</h3>"
        f"<p class='muted'>{escape(message)}</p>"
        f"<div class='action-row'><a class='action primary' href='{escape(action_href)}'>{escape(action_label)}</a></div>"
        "</article>"
    )


def _turn_shell(turn: dict[str, Any], inner: str, extra_class: str = "") -> str:
    reply_text = ", ".join(turn.get("reply_to", [])) or "none"
    classes = "turn" + (f" {extra_class}" if extra_class else "")
    return (
        f"<article class='{classes}'>"
        f"<div class='meta-row'>"
        f"<span class='badge'>{escape(str(turn.get('phase', '')))}</span>"
        f"<span class='badge'>{escape(str(turn.get('speaker_id', '')))}</span>"
        f"<span class='badge'>{escape(str(turn.get('provider', '')))}</span>"
        f"<span class='badge'>{escape(str(turn.get('model_name', '')))}</span>"
        f"<span class='badge'>{escape(str(turn.get('role', '')))}</span>"
        f"<span class='badge'>{escape(str(turn.get('status', '')))}</span>"
        f"</div>"
        f"<p class='small muted'>Replies to: <code>{escape(reply_text)}</code></p>"
        f"{inner}</article>"
    )


def ModelTurnCard(*, turn: dict[str, Any]) -> str:
    return _turn_shell(
        turn,
        f"<div class='content'>{escape(str(turn.get('content', '')))}</div>",
    )


def CritiqueTurnCard(*, turn: dict[str, Any]) -> str:
    return _turn_shell(
        turn,
        f"<div class='content'>{escape(str(turn.get('content', '')))}</div>",
        extra_class="critic",
    )


def ToolEvidenceCard(*, turn: dict[str, Any]) -> str:
    return _turn_shell(
        turn,
        f"<div class='content'>{escape(str(turn.get('content', '')))}</div>",
        extra_class="tool",
    )


def DebateTurnCard(*, turn: dict[str, Any]) -> str:
    if turn.get("speaker_type") == "tool":
        return ToolEvidenceCard(turn=turn)
    if turn.get("role") == "critic":
        return CritiqueTurnCard(turn=turn)
    return ModelTurnCard(turn=turn)


def DebateRound(*, round_index: int, phase: str, turns: list[dict[str, Any]]) -> str:
    cards = "".join(DebateTurnCard(turn=turn) for turn in turns)
    return (
        f"<section class='round'><h3>Round {round_index} · {escape(phase)}</h3>"
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


def DiscoveryCard(*, discovery: dict[str, Any]) -> str:
    status_class = {
        "verified": "accepted",
        "accepted": "accepted",
        "refuted": "refuted",
    }.get(str(discovery.get("status", "")).lower(), "discovery")
    badges = [
        "<span class='badge discovery'>New Discovery</span>",
        f"<span class='badge {status_class}'>{escape(str(discovery.get('status', 'proposed')).title())}</span>",
        f"<span class='badge verify'>{escape(str(discovery.get('type', 'strategy')))}</span>",
    ]
    if discovery.get("needs_verification"):
        badges.append("<span class='badge verify'>Needs Verification</span>")
    return (
        "<article class='discovery-card'>"
        f"<div class='meta-row'>{''.join(badges)}</div>"
        f"<p class='discovery-claim'><strong>{escape(str(discovery.get('claim', '')))}</strong></p>"
        f"<p class='small muted'>{escape(str(discovery.get('rationale', '')))}</p>"
        f"<div class='action-row'>{AskAnotherModelToCritiqueButton()} {AskModelToExtendDiscoveryButton()} "
        f"{AskModelToFormalizeDiscoveryButton()} {RunVerifierButton()} {SaveTeacherLabelButton()}</div>"
        "</article>"
    )


def VerificationRequestCard(*, request: dict[str, Any]) -> str:
    return (
        "<article class='request-card'>"
        f"<div class='meta-row'><span class='badge verify'>{escape(str(request.get('tool', '')))}</span>"
        f"<span class='badge'>{escape(str(request.get('status', 'pending')))}</span></div>"
        f"<p class='request-question'>{escape(str(request.get('question', '')))}</p></article>"
    )


def FinalJudgePanel(*, content: str) -> str:
    return f"<section class='panel'><h2>Final Judge</h2><div class='content'>{escape(content)}</div></section>"


def DisagreementPanel(*, rejected_discoveries: list[dict[str, Any]]) -> str:
    if not rejected_discoveries:
        return "<section class='panel'><h2>Disagreement Panel</h2><p class='muted'>No explicit rejected discoveries recorded.</p></section>"
    body = "".join(DiscoveryCard(discovery=discovery) for discovery in rejected_discoveries)
    return f"<section class='panel'><h2>Disagreement Panel</h2><div class='discovery-grid'>{body}</div></section>"


def SaveTeacherLabelButton() -> str:
    return "<span class='action'>Save as Raven training data</span>"


def RunVerifierButton() -> str:
    return "<span class='action'>Re-run verifier</span>"


def AskAnotherModelToCritiqueButton() -> str:
    return "<span class='action'>Ask another model to critique</span>"


def AskModelToExtendDiscoveryButton() -> str:
    return "<span class='action'>Ask another model to extend this discovery</span>"


def AskModelToFormalizeDiscoveryButton() -> str:
    return "<span class='action'>Ask model to formalize discovery</span>"


def AskModelToReviseAfterEvidenceButton() -> str:
    return "<span class='action'>Ask model to revise after evidence</span>"

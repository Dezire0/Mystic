from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Callable

from mystic.discord_dashboard import ExpertSnapshot, load_dashboard_snapshot
from mystic.llm_client import LLMClient, build_client, load_model_defaults
from mystic.parsers import parse_raven_output
from mystic.prompts import RAVEN_CRITIC_PROMPT


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "configs" / "models.json"


ROUTER_PROMPT = """You are Mystic-Router.

Choose the best primary specialist and several support specialists for the user's math or science reasoning request.
Return JSON only:
{
  "specialist": "prime | algebra | geo | analysis | probability | logic | physics | complexity | biomath | chem | lean | raven | forge | conjecture | pattern | simulator | report | core",
  "support_specialists": ["..."],
  "reason": "...",
  "strategy": "..."
}

Rules:
- Pick exactly one specialist.
- Pick 2 to 5 support specialists when they can contribute materially.
- Prefer a concrete domain specialist over core when possible.
- Use core only when the question is broad or ambiguous.
- Write reason and strategy in Korean.
- Output JSON only.
"""


SOLVER_PROMPT_TEMPLATE = """You are {specialist_name}, a Mystic specialist.

Current specialist context:
- specialist: {specialist_name}
- division: {division}
- configured model role: {model_name}
- adapter: {adapter_name}
- training coverage: {dataset_progress}
- dashboard status: {status_text}
- status detail: {status_detail}

You are running inside Mystic's local research lab.

Task:
1. Understand the user's question.
2. State a strategy before solving.
3. Execute the approach carefully.
4. Give a conclusion.
5. Do not bluff. If something is uncertain, say so.
6. Write every section in Korean.
7. Keep the answer readable and stepwise, like a math tutor explaining the work.

Output plain text with exactly these section headers:
UNDERSTANDING:
STRATEGY:
EXECUTION:
CONCLUSION:
UNCERTAINTIES:
"""


SYNTHESIS_PROMPT = """You are Mystic-Core-Synthesizer.

You will receive:
1. The user's original problem.
2. The Core routing strategy.
3. Several specialist drafts.

Your job:
1. Compare the drafts.
2. Keep the strongest useful ideas.
3. Remove contradictions and unjustified leaps.
4. Produce one integrated solution draft in Korean.
5. If the drafts disagree, say so explicitly in UNCERTAINTIES.

Output plain text with exactly these section headers:
UNDERSTANDING:
STRATEGY:
EXECUTION:
CONCLUSION:
UNCERTAINTIES:
"""


PLAN_CRITIC_PROMPT = """You are Mystic-Core-Plan-Critic.

You will receive a problem and a proposed Core routing plan.
Attack the plan before execution.

Return JSON only:
{
  "risk_summary": "...",
  "missing_specialists": ["..."],
  "weak_assumptions": ["..."],
  "revised_strategy": "..."
}

Rules:
- Be concise and concrete.
- Write in Korean.
- Output JSON only.
"""


CROSS_REVIEW_PROMPT = """You are a Mystic specialist reviewer.

You will receive:
1. The original problem.
2. The Core strategy.
3. Another specialist's draft.

Your job:
1. Point out hidden assumptions, logical gaps, or missing cases.
2. Mention any useful improvement.
3. Keep it concise.
4. Write in Korean.

Output plain text with exactly these section headers:
UNDERSTANDING:
STRATEGY:
EXECUTION:
CONCLUSION:
UNCERTAINTIES:
"""

ProgressCallback = Callable[[str, dict[str, str]], None]


@dataclass(slots=True)
class ResearchPlan:
    specialist: str
    support_specialists: list[str]
    reason: str
    strategy: str
    critic_summary: str = ""


@dataclass(slots=True)
class SpecialistDraft:
    agent: str
    specialist_name: str
    sections: ResearchSections


@dataclass(slots=True)
class CrossReviewNote:
    reviewer_agent: str
    reviewer_name: str
    target_agent: str
    sections: ResearchSections


@dataclass(slots=True)
class ResearchSections:
    understanding: str
    strategy: str
    execution: str
    conclusion: str
    uncertainties: str
    raw_text: str


@dataclass(slots=True)
class ResearchResult:
    question: str
    specialist: str
    specialist_name: str
    participating_specialists: list[str]
    backend: str
    model: str
    critic_backend: str
    critic_model: str
    plan_reason: str
    plan_strategy: str
    sections: ResearchSections
    critic_verdict: str
    critic_confidence: float
    critic_first_fatal_error: str
    final_answer: str


def critique_value(critique: Any, key: str, default: Any = "") -> Any:
    if isinstance(critique, dict):
        return critique.get(key, default)
    return getattr(critique, key, default)


def run_research_lab(
    question: str,
    *,
    base_dir: str | Path,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    progress_callback: ProgressCallback | None = None,
) -> ResearchResult:
    snapshot = load_dashboard_snapshot(base_dir)
    defaults = load_model_defaults(config_path)

    generator_backend = str(defaults.get("backend", "ollama"))
    generator_model = str(defaults.get("generator_model", "qwen2.5:7b"))
    generator_client = build_client(generator_backend, config_path=config_path)

    critic_backend, critic_model, critic_client = build_critic_client(config_path=config_path)

    plan = route_question(
        question=question,
        snapshot=snapshot,
        client=generator_client,
        model=generator_model,
    )
    plan = critique_plan(
        question=question,
        plan=plan,
        client=generator_client,
        model=generator_model,
    )
    emit_progress(
        progress_callback,
        "plan_critic_complete",
        {
            "critic_summary": plan.critic_summary,
            "strategy": plan.strategy,
        },
    )
    emit_progress(
        progress_callback,
        "routing_complete",
        {
            "specialist": plan.specialist,
            "support_specialists": ", ".join(plan.support_specialists),
            "reason": plan.reason,
            "strategy": plan.strategy,
        },
    )
    selected_agents = [plan.specialist, *plan.support_specialists]
    drafts: list[SpecialistDraft] = []
    for agent in selected_agents:
        expert = get_expert_snapshot(snapshot, agent)
        agent_backend, agent_model, agent_client = resolve_reasoning_backend(
            agent=agent,
            config_path=config_path,
            defaults=defaults,
            fallback_client=generator_client,
            fallback_backend=generator_backend,
            fallback_model=generator_model,
        )
        sections = solve_question(
            question=question,
            plan=plan,
            expert=expert,
            client=agent_client,
            model=agent_model,
        )
        drafts.append(SpecialistDraft(agent=agent, specialist_name=expert.name, sections=sections))
        emit_progress(
            progress_callback,
            "specialist_complete",
            {
                "agent": agent,
                "specialist_name": expert.name,
                "backend": agent_backend,
                "model": agent_model,
                "understanding": sections.understanding,
                "strategy": sections.strategy,
                "execution": sections.execution,
                "conclusion": sections.conclusion,
                "uncertainties": sections.uncertainties,
            },
        )
    cross_reviews = build_cross_reviews(
        question=question,
        plan=plan,
        drafts=drafts,
        snapshot=snapshot,
        defaults=defaults,
        config_path=config_path,
        fallback_client=generator_client,
        fallback_backend=generator_backend,
        fallback_model=generator_model,
        progress_callback=progress_callback,
    )
    expert = get_expert_snapshot(snapshot, plan.specialist)
    sections = synthesize_solution(
        question=question,
        plan=plan,
        drafts=drafts,
        cross_reviews=cross_reviews,
        client=generator_client,
        model=generator_model,
    )
    emit_progress(
        progress_callback,
        "synthesis_complete",
        {
            "specialist_name": expert.name,
            "understanding": sections.understanding,
            "strategy": sections.strategy,
            "execution": sections.execution,
            "conclusion": sections.conclusion,
            "uncertainties": sections.uncertainties,
        },
    )
    critique = critique_solution(
        question=question,
        sections=sections,
        client=critic_client,
        backend=critic_backend,
        model=critic_model,
    )
    emit_progress(
        progress_callback,
        "critique_complete",
        {
            "verdict": str(critique_value(critique, "verdict", "NEEDS_MORE_DETAIL")),
            "first_fatal_error": str(critique_value(critique, "first_fatal_error", "") or ""),
            "confidence": str(critique_value(critique, "confidence", 0.0) or 0.0),
        },
    )
    final_answer = build_final_answer(plan=plan, sections=sections, critique=critique)
    emit_progress(
        progress_callback,
        "final_answer_ready",
        {
            "specialist_name": expert.name,
            "final_answer": final_answer,
        },
    )
    return ResearchResult(
        question=question,
        specialist=plan.specialist,
        specialist_name=expert.name,
        participating_specialists=selected_agents,
        backend=generator_backend,
        model=generator_model,
        critic_backend=critic_backend,
        critic_model=critic_model,
        plan_reason=plan.reason,
        plan_strategy=plan.strategy,
        sections=sections,
        critic_verdict=str(critique_value(critique, "verdict", "NEEDS_MORE_DETAIL")),
        critic_confidence=float(critique_value(critique, "confidence", 0.0) or 0.0),
        critic_first_fatal_error=str(critique_value(critique, "first_fatal_error", "") or ""),
        final_answer=final_answer,
    )


def emit_progress(progress_callback: ProgressCallback | None, stage: str, payload: dict[str, str]) -> None:
    if progress_callback is None:
        return
    progress_callback(stage, payload)


def build_critic_client(*, config_path: str | Path) -> tuple[str, str, LLMClient]:
    defaults = load_model_defaults(config_path)
    active_backend = str(defaults.get("active_raven_backend", defaults.get("backend", "ollama")))
    if active_backend == "adapter":
        base_model = str(defaults.get("active_raven_base_model", "")).strip()
        adapter_path = str(defaults.get("active_raven_adapter", "")).strip()
        try:
            client = build_client(
                "adapter",
                config_path=config_path,
                base_model=base_model,
                adapter_path=adapter_path,
            )
            return "adapter", base_model, client
        except Exception as exc:
            fallback_backend = str(defaults.get("backend", "ollama"))
            fallback_model = str(defaults.get("raven_model", defaults.get("generator_model", "qwen2.5:7b")))
            print(
                "[warning] Raven adapter critic unavailable in research lab; "
                f"falling back to {fallback_backend}/{fallback_model}. "
                f"Original error: {exc}"
            )
            client = build_client(fallback_backend, config_path=config_path)
            return fallback_backend, fallback_model, client

    raven_model = str(defaults.get("raven_model", defaults.get("generator_model", "qwen2.5:7b")))
    client = build_client(active_backend, config_path=config_path)
    return active_backend, raven_model, client


def resolve_reasoning_backend(
    *,
    agent: str,
    config_path: str | Path,
    defaults: dict[str, Any],
    fallback_client: LLMClient,
    fallback_backend: str,
    fallback_model: str,
) -> tuple[str, str, LLMClient]:
    heavy_agents = {"prime", "algebra", "analysis", "geo", "logic", "complexity", "biomath", "chem", "physics"}
    remote_backend = str(os.getenv("MYSTIC_REMOTE_REASONING_BACKEND", "openai-compatible")).strip()
    remote_model = str(
        os.getenv("MYSTIC_REMOTE_REASONING_MODEL", os.getenv("MYSTIC_GENERATOR_MODEL", fallback_model))
    ).strip()
    remote_enabled = bool(os.getenv("MYSTIC_REMOTE_REASONING_MODEL", "").strip() and os.getenv("MYSTIC_API_BASE", "").strip())
    if agent in heavy_agents and remote_enabled:
        try:
            client = build_client(remote_backend, config_path=config_path)
            return remote_backend, remote_model or fallback_model, client
        except Exception:
            pass
    return fallback_backend, fallback_model, fallback_client


def route_question(*, question: str, snapshot: dict[str, Any], client: LLMClient, model: str) -> ResearchPlan:
    expert_lines = []
    for expert in snapshot["experts"]:
        expert = expert  # type: ignore[assignment]
        expert_lines.append(
            f"- {expert.agent}: {expert.name}, division={expert.division}, "
            f"status={expert.status_text}, coverage={expert.dataset_progress_text}"
        )
    user_prompt = (
        "Available specialists:\n"
        + "\n".join(expert_lines)
        + "\n\nUser question:\n"
        + question.strip()
    )
    raw = client.generate_text(model=model, system_prompt=ROUTER_PROMPT, user_prompt=user_prompt)
    payload = parse_json_object(raw)
    specialist = str(payload.get("specialist", "")).strip().lower()
    if specialist not in {str(item.agent) for item in snapshot["experts"]}:
        specialist = heuristic_specialist(question)
    support_specialists = normalize_support_specialists(
        payload.get("support_specialists"),
        specialist=specialist,
        question=question,
        available_agents={str(item.agent) for item in snapshot["experts"]},
    )
    reason = str(payload.get("reason", "")).strip() or fallback_reason(specialist)
    strategy = str(payload.get("strategy", "")).strip() or "문제를 분해하고 보수적으로 단계별 추론을 수행한다."
    return ResearchPlan(
        specialist=specialist,
        support_specialists=support_specialists,
        reason=reason,
        strategy=strategy,
    )


def critique_plan(*, question: str, plan: ResearchPlan, client: LLMClient, model: str) -> ResearchPlan:
    user_prompt = (
        f"Problem:\n{question.strip()}\n\n"
        f"Primary specialist: {plan.specialist}\n"
        f"Support specialists: {', '.join(plan.support_specialists) or '-'}\n"
        f"Reason: {plan.reason}\n"
        f"Strategy: {plan.strategy}"
    )
    raw = client.generate_text(model=model, system_prompt=PLAN_CRITIC_PROMPT, user_prompt=user_prompt)
    payload = parse_json_object(raw)
    critic_summary = str(payload.get("risk_summary", "")).strip()
    revised_strategy = str(payload.get("revised_strategy", "")).strip()
    return ResearchPlan(
        specialist=plan.specialist,
        support_specialists=plan.support_specialists,
        reason=plan.reason,
        strategy=revised_strategy or plan.strategy,
        critic_summary=critic_summary,
    )


def solve_question(
    *,
    question: str,
    plan: ResearchPlan,
    expert: ExpertSnapshot,
    client: LLMClient,
    model: str,
) -> ResearchSections:
    system_prompt = SOLVER_PROMPT_TEMPLATE.format(
        specialist_name=expert.name,
        division=expert.division,
        model_name=expert.model,
        adapter_name=expert.adapter,
        dataset_progress=expert.dataset_progress_text,
        status_text=expert.status_text,
        status_detail=expert.status_detail,
    )
    user_prompt = (
        f"Chosen specialist: {plan.specialist}\n"
        f"Routing reason: {plan.reason}\n"
        f"Initial strategy: {plan.strategy}\n\n"
        f"Question:\n{question.strip()}"
    )
    raw = client.generate_text(model=model, system_prompt=system_prompt, user_prompt=user_prompt)
    return parse_sections(raw)


def synthesize_solution(
    *,
    question: str,
    plan: ResearchPlan,
    drafts: list[SpecialistDraft],
    cross_reviews: list[CrossReviewNote],
    client: LLMClient,
    model: str,
) -> ResearchSections:
    draft_chunks = []
    for draft in drafts:
        draft_chunks.append(
            f"[{draft.specialist_name} / {draft.agent}]\n"
            f"UNDERSTANDING:\n{draft.sections.understanding}\n"
            f"STRATEGY:\n{draft.sections.strategy}\n"
            f"EXECUTION:\n{draft.sections.execution}\n"
            f"CONCLUSION:\n{draft.sections.conclusion}\n"
            f"UNCERTAINTIES:\n{draft.sections.uncertainties}"
        )
    user_prompt = (
        f"Primary specialist: {plan.specialist}\n"
        f"Support specialists: {', '.join(plan.support_specialists) or '-'}\n"
        f"Core strategy: {plan.strategy}\n\n"
        f"Problem:\n{question.strip()}\n\n"
        f"Specialist drafts:\n\n"
        + "\n\n".join(draft_chunks)
        + "\n\nCross reviews:\n\n"
        + "\n\n".join(
            f"[{note.reviewer_name} -> {note.target_agent}]\n"
            f"UNDERSTANDING:\n{note.sections.understanding}\n"
            f"STRATEGY:\n{note.sections.strategy}\n"
            f"EXECUTION:\n{note.sections.execution}\n"
            f"CONCLUSION:\n{note.sections.conclusion}\n"
            f"UNCERTAINTIES:\n{note.sections.uncertainties}"
            for note in cross_reviews
        )
    )
    raw = client.generate_text(model=model, system_prompt=SYNTHESIS_PROMPT, user_prompt=user_prompt)
    return parse_sections(raw)


def build_cross_reviews(
    *,
    question: str,
    plan: ResearchPlan,
    drafts: list[SpecialistDraft],
    snapshot: dict[str, Any],
    defaults: dict[str, Any],
    config_path: str | Path,
    fallback_client: LLMClient,
    fallback_backend: str,
    fallback_model: str,
    progress_callback: ProgressCallback | None,
) -> list[CrossReviewNote]:
    if len(drafts) < 2:
        return []
    notes: list[CrossReviewNote] = []
    for index, reviewer_draft in enumerate(drafts[1:], start=1):
        target = drafts[index - 1]
        reviewer = get_expert_snapshot(snapshot, reviewer_draft.agent)
        backend, model, client = resolve_reasoning_backend(
            agent=reviewer_draft.agent,
            config_path=config_path,
            defaults=defaults,
            fallback_client=fallback_client,
            fallback_backend=fallback_backend,
            fallback_model=fallback_model,
        )
        sections = cross_review_draft(
            question=question,
            plan=plan,
            reviewer=reviewer,
            target=target,
            client=client,
            model=model,
        )
        note = CrossReviewNote(
            reviewer_agent=reviewer_draft.agent,
            reviewer_name=reviewer.name,
            target_agent=target.agent,
            sections=sections,
        )
        notes.append(note)
        emit_progress(
            progress_callback,
            "cross_review_complete",
            {
                "reviewer_agent": reviewer_draft.agent,
                "reviewer_name": reviewer.name,
                "target_agent": target.agent,
                "backend": backend,
                "model": model,
                "conclusion": sections.conclusion,
            },
        )
    return notes


def cross_review_draft(
    *,
    question: str,
    plan: ResearchPlan,
    reviewer: ExpertSnapshot,
    target: SpecialistDraft,
    client: LLMClient,
    model: str,
) -> ResearchSections:
    system_prompt = CROSS_REVIEW_PROMPT
    user_prompt = (
        f"Problem:\n{question.strip()}\n\n"
        f"Core strategy:\n{plan.strategy}\n\n"
        f"Target specialist: {target.specialist_name} / {target.agent}\n"
        f"UNDERSTANDING:\n{target.sections.understanding}\n"
        f"STRATEGY:\n{target.sections.strategy}\n"
        f"EXECUTION:\n{target.sections.execution}\n"
        f"CONCLUSION:\n{target.sections.conclusion}\n"
        f"UNCERTAINTIES:\n{target.sections.uncertainties}\n\n"
        f"Reviewer specialist: {reviewer.name} / {reviewer.agent}"
    )
    raw = client.generate_text(model=model, system_prompt=system_prompt, user_prompt=user_prompt)
    return parse_sections(raw)


def critique_solution(
    *,
    question: str,
    sections: ResearchSections,
    client: LLMClient,
    backend: str,
    model: str,
):
    proof_attempt = (
        f"UNDERSTANDING:\n{sections.understanding}\n\n"
        f"STRATEGY:\n{sections.strategy}\n\n"
        f"EXECUTION:\n{sections.execution}\n\n"
        f"CONCLUSION:\n{sections.conclusion}\n\n"
        f"UNCERTAINTIES:\n{sections.uncertainties}"
    )
    user_prompt = f"Problem:\n{question.strip()}\n\nProof attempt:\n{proof_attempt}"
    raw = client.generate_text(model=model, system_prompt=RAVEN_CRITIC_PROMPT, user_prompt=user_prompt)
    return parse_raven_output(
        raw_output=raw,
        sample_id="discord_research_lab",
        run_id="discord_research_lab",
        backend=backend,
        model=model,
        problem=question,
        answer_text=proof_attempt,
    )


def build_final_answer(*, plan: ResearchPlan, sections: ResearchSections, critique: Any) -> str:
    caution_lines: list[str] = []
    verdict = str(critique_value(critique, "verdict", "NEEDS_MORE_DETAIL"))
    first_fatal_error = str(critique_value(critique, "first_fatal_error", "") or "")
    support_specialists = list(getattr(plan, "support_specialists", []) or [])
    if verdict != "VALID":
        caution_lines.append(f"검증 판정: {verdict}")
        if first_fatal_error:
            caution_lines.append(f"주의: {first_fatal_error}")
    if sections.uncertainties.strip():
        caution_lines.append(f"불확실성: {sections.uncertainties.strip()}")

    lines = [
        f"선택 전문가: {plan.specialist}",
        f"참여 전문가: {', '.join([plan.specialist, *support_specialists])}",
        "",
        "이해:",
        sections.understanding.strip() or "-",
        "",
        "전략:",
        sections.strategy.strip() or plan.strategy,
        "",
        "풀이:",
        sections.execution.strip() or "-",
        "",
        "결론:",
        sections.conclusion.strip() or "-",
    ]
    if caution_lines:
        lines.extend(["", "검증/주의:", *caution_lines])
    return "\n".join(lines).strip()


def get_expert_snapshot(snapshot: dict[str, Any], agent: str) -> ExpertSnapshot:
    return next(item for item in snapshot["experts"] if item.agent == agent)


def parse_json_object(raw: str) -> dict[str, Any]:
    stripped = raw.strip()
    try:
        payload = json.loads(stripped)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass
    decoder = json.JSONDecoder()
    for index, char in enumerate(stripped):
        if char != "{":
            continue
        try:
            payload, end = decoder.raw_decode(stripped[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def heuristic_specialist(question: str) -> str:
    lowered = question.lower()
    keyword_map = [
        ("triangle", "geo"),
        ("geometry", "geo"),
        ("angle", "geo"),
        ("circle", "geo"),
        ("probability", "probability"),
        ("expectation", "probability"),
        ("random", "probability"),
        ("integral", "analysis"),
        ("derivative", "analysis"),
        ("limit", "analysis"),
        ("series", "analysis"),
        ("matrix", "algebra"),
        ("polynomial", "algebra"),
        ("equation", "algebra"),
        ("group", "algebra"),
        ("logic", "logic"),
        ("contradiction", "logic"),
        ("physics", "physics"),
        ("velocity", "physics"),
        ("force", "physics"),
        ("algorithm", "complexity"),
        ("complexity", "complexity"),
        ("runtime", "complexity"),
        ("chemistry", "chem"),
        ("molecule", "chem"),
        ("biology", "biomath"),
        ("gene", "biomath"),
        ("proof", "prime"),
        ("number theory", "prime"),
        ("integer", "prime"),
        ("prime", "prime"),
    ]
    for keyword, specialist in keyword_map:
        if keyword in lowered:
            return specialist
    return "core"


def fallback_reason(specialist: str) -> str:
    return f"{specialist} specialist chosen by heuristic fallback."


def normalize_support_specialists(
    raw_value: Any,
    *,
    specialist: str,
    question: str,
    available_agents: set[str],
) -> list[str]:
    fallback = default_support_specialists(specialist, question)
    values: list[str]
    if isinstance(raw_value, list):
        values = [str(item).strip().lower() for item in raw_value if str(item).strip()]
    else:
        values = []
    ordered: list[str] = []
    for item in values + fallback:
        if item == specialist:
            continue
        if item not in available_agents:
            continue
        if item not in ordered:
            ordered.append(item)
    return ordered[:5]


def default_support_specialists(specialist: str, question: str) -> list[str]:
    lowered = question.lower()
    defaults = {
        "prime": ["logic", "pattern", "forge", "raven"],
        "algebra": ["logic", "analysis", "forge", "raven"],
        "geo": ["analysis", "logic", "forge", "raven"],
        "analysis": ["algebra", "logic", "forge", "raven"],
        "probability": ["analysis", "logic", "simulator", "raven"],
        "logic": ["prime", "algebra", "forge", "raven"],
        "physics": ["analysis", "simulator", "forge", "raven"],
        "complexity": ["logic", "pattern", "forge", "raven"],
        "biomath": ["analysis", "simulator", "forge", "raven"],
        "chem": ["analysis", "simulator", "forge", "raven"],
        "core": ["logic", "pattern", "forge", "raven"],
    }
    support = defaults.get(specialist, ["logic", "forge", "raven"])
    if "counterexample" in lowered or "classify" in lowered or "all solutions" in lowered:
        for extra in ["pattern", "forge", "simulator"]:
            if extra not in support:
                support.append(extra)
    return support


def parse_sections(raw: str) -> ResearchSections:
    sections = {
        "UNDERSTANDING": "",
        "STRATEGY": "",
        "EXECUTION": "",
        "CONCLUSION": "",
        "UNCERTAINTIES": "",
    }
    current_key: str | None = None
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped in {f"{key}:" for key in sections}:
            current_key = stripped[:-1]
            continue
        if current_key is None:
            continue
        sections[current_key] += (line + "\n")

    if not any(value.strip() for value in sections.values()):
        return ResearchSections(
            understanding="질문을 해석했지만 모델 출력이 구조화되지 않았다.",
            strategy="핵심 개념을 분해해 다시 검토한다.",
            execution=raw.strip(),
            conclusion="출력을 구조적으로 재정리하지 못했다.",
            uncertainties="모델이 지정된 섹션 형식을 따르지 않았다.",
            raw_text=raw,
        )

    return ResearchSections(
        understanding=sections["UNDERSTANDING"].strip(),
        strategy=sections["STRATEGY"].strip(),
        execution=sections["EXECUTION"].strip(),
        conclusion=sections["CONCLUSION"].strip(),
        uncertainties=sections["UNCERTAINTIES"].strip(),
        raw_text=raw,
    )

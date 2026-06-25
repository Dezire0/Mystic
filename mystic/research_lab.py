from __future__ import annotations

from dataclasses import dataclass, field
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
  "reason": "..."
}

Rules:
- Pick exactly one specialist.
- Pick 2 to 5 support specialists when they can contribute materially.
- Prefer a concrete domain specialist over core when possible.
- Use core only when the question is broad or ambiguous.
- Do not write the full solving strategy. Routing only.
- Write reason in Korean.
- Output JSON only.
"""


PLANNER_PROMPT = """You are Mystic-Core-Planner.

You will receive:
1. The original user problem.
2. The chosen primary specialist.
3. The support specialists.
4. The routing reason.

Your job:
1. Write the first executable solving strategy.
2. Break the work into a small number of concrete phases.
3. Keep the plan realistic before critic review.

Return JSON only:
{
  "strategy": "...",
  "phases": ["..."]
}

Rules:
- Write in Korean.
- Keep the plan concrete.
- Output JSON only.
"""


CRITIC_PROMPT_TEMPLATE = """You are {critic_name}.

You will receive:
1. The original user problem.
2. The current primary specialist.
3. The support specialists.
4. The current plan.

Your focus:
{focus}

Return JSON only:
{{
  "summary": "...",
  "findings": ["..."],
  "revision": "..."
}}

Rules:
- Be concrete and concise.
- Write in Korean.
- Output JSON only.
"""


METHOD_PROPOSAL_PROMPT = """You are a Mystic specialist.

Given the user problem and the current Core plan, propose what your specialty can contribute.

Return JSON only:
{
  "method_summary": "...",
  "task_candidate": "...",
  "dependencies": ["..."],
  "deliverable": "..."
}

Rules:
- Think from your own specialty only.
- Propose one concrete method and one concrete task candidate.
- Write in Korean.
- Output JSON only.
"""


TASK_ASSIGNMENT_PROMPT = """You are Mystic-Core-Task-Orchestrator.

You will receive:
1. The original problem.
2. The primary specialist and support specialists.
3. Core critic outputs.
4. Specialist method proposals.

Your job:
1. Combine the strongest methods.
2. Redistribute concrete tasks across the selected specialists.
3. Keep the plan realistic and non-redundant.

Return JSON only:
{
  "combined_strategy": "...",
  "handoff_notes": ["..."],
  "task_assignments": [
    {
      "agent": "prime",
      "task": "...",
      "deliverable": "..."
    }
  ]
}

Rules:
- Assign a task to every selected specialist.
- Write in Korean.
- Output JSON only.
"""


TASK_EXECUTION_PROMPT_TEMPLATE = """You are {specialist_name}, a Mystic specialist.

Current specialist context:
- specialist: {specialist_name}
- division: {division}
- configured model role: {model_name}
- adapter: {adapter_name}
- training coverage: {dataset_progress}
- dashboard status: {status_text}
- status detail: {status_detail}

You are executing your assigned role inside Mystic's local research lab.

Assigned task:
{assigned_task}

Expected deliverable:
{deliverable}

Method proposal:
{method_summary}

Dependencies:
{dependencies}

Task:
1. State what your assigned role is solving.
2. Explain your local strategy.
3. Execute only your assigned task carefully.
4. Give the local conclusion.
5. Mention what must be handed off to the next step.
6. Write every section in Korean.

Output plain text with exactly these section headers:
UNDERSTANDING:
STRATEGY:
EXECUTION:
CONCLUSION:
UNCERTAINTIES:
"""


OBJECTION_PROMPT = """You are a Mystic specialist reviewer in a debate phase.

You will receive:
1. The original problem.
2. The current combined strategy.
3. Another selected specialist's assigned task and execution.

Your job:
1. Raise one concrete objection or risk from your specialty.
2. Identify what could break or what case may be missing.
3. Request one concrete fix.

Return JSON only:
{
  "objection": "...",
  "risk": "...",
  "requested_fix": "..."
}

Rules:
- This debate is only among the selected specialists.
- Write in Korean.
- Output JSON only.
"""


REVISION_PROMPT_TEMPLATE = """You are {specialist_name}, a Mystic specialist.

You previously executed an assigned task. Now you must revise it after objections from other selected specialists.

Assigned task:
{assigned_task}

Previous draft:
UNDERSTANDING:
{understanding}
STRATEGY:
{strategy}
EXECUTION:
{execution}
CONCLUSION:
{conclusion}
UNCERTAINTIES:
{uncertainties}

Objections received:
{objections_text}

Task:
1. Keep valid parts.
2. Patch the draft where objections are legitimate.
3. Explicitly note if an objection does not apply.
4. Write every section in Korean.

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
2. The selected specialists.
3. Core critic outputs.
4. Method proposals.
5. Task assignments.
6. Revised specialist task results.
7. Pairwise objections among the selected specialists.

Your job:
1. Combine the strongest arguments.
2. Remove contradictions and unsupported claims.
3. Keep useful objections in mind.
4. Produce one integrated solution draft in Korean.
5. If uncertainty remains, state it explicitly.

Output plain text with exactly these section headers:
UNDERSTANDING:
STRATEGY:
EXECUTION:
CONCLUSION:
UNCERTAINTIES:
"""


ProgressCallback = Callable[[str, dict[str, Any]], None]


@dataclass(slots=True)
class CriticReview:
    critic_key: str
    critic_name: str
    summary: str
    findings: list[str]
    revision: str


@dataclass(slots=True)
class MethodProposal:
    agent: str
    specialist_name: str
    method_summary: str
    task_candidate: str
    dependencies: list[str]
    deliverable: str
    raw_text: str


@dataclass(slots=True)
class TaskAssignment:
    agent: str
    specialist_name: str
    task: str
    deliverable: str


@dataclass(slots=True)
class ResearchPlan:
    specialist: str
    support_specialists: list[str]
    reason: str
    strategy: str
    phases: list[str] = field(default_factory=list)
    critic_summary: str = ""
    critic_reviews: list[CriticReview] = field(default_factory=list)
    handoff_notes: list[str] = field(default_factory=list)
    task_assignments: list[TaskAssignment] = field(default_factory=list)


@dataclass(slots=True)
class ResearchSections:
    understanding: str
    strategy: str
    execution: str
    conclusion: str
    uncertainties: str
    raw_text: str


@dataclass(slots=True)
class TaskExecution:
    agent: str
    specialist_name: str
    assignment: TaskAssignment
    sections: ResearchSections


@dataclass(slots=True)
class DebateNote:
    reviewer_agent: str
    reviewer_name: str
    target_agent: str
    target_name: str
    objection: str
    risk: str
    requested_fix: str
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


def remote_reasoning_state(*, fallback_model: str) -> tuple[bool, str, str]:
    remote_backend = str(os.getenv("MYSTIC_REMOTE_REASONING_BACKEND", "openai-compatible")).strip()
    remote_model = str(
        os.getenv("MYSTIC_REMOTE_REASONING_MODEL", os.getenv("MYSTIC_GENERATOR_MODEL", fallback_model))
    ).strip()
    remote_enabled = bool(os.getenv("MYSTIC_REMOTE_REASONING_MODEL", "").strip() and os.getenv("MYSTIC_API_BASE", "").strip())
    return remote_enabled, remote_backend, remote_model or fallback_model


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
    remote_enabled, remote_backend, remote_model = remote_reasoning_state(fallback_model=generator_model)

    critic_backend, critic_model, critic_client = build_critic_client(config_path=config_path)

    plan = route_question(
        question=question,
        snapshot=snapshot,
        client=generator_client,
        model=generator_model,
    )
    emit_progress(
        progress_callback,
        "routing_complete",
        {
            "specialist": plan.specialist,
            "support_specialists": ", ".join(plan.support_specialists),
            "reason": plan.reason,
            "lines": [
                f"주 전문가: {plan.specialist}",
                f"보조 전문가: {', '.join(plan.support_specialists) or '-'}",
                f"선정 이유: {plan.reason}",
            ],
        },
    )
    plan = plan_question(
        question=question,
        plan=plan,
        client=generator_client,
        model=generator_model,
    )
    emit_progress(
        progress_callback,
        "planning_complete",
        {
            "strategy": plan.strategy,
            "phases": plan.phases,
            "remote_enabled": remote_enabled,
            "remote_backend": remote_backend,
            "remote_model": remote_model,
            "lines": [
                f"Core 초기 전략: {plan.strategy}",
                *[f"초기 단계: {phase}" for phase in plan.phases[:4]],
                f"원격 reasoning 사용 가능: {'yes' if remote_enabled else 'no'}",
                f"원격 backend/model: {remote_backend} / {remote_model}",
            ],
        },
    )
    plan = run_core_critics(
        question=question,
        plan=plan,
        client=generator_client,
        model=generator_model,
        progress_callback=progress_callback,
    )

    selected_agents = [plan.specialist, *plan.support_specialists]
    proposals = build_method_proposals(
        question=question,
        plan=plan,
        selected_agents=selected_agents,
        snapshot=snapshot,
        defaults=defaults,
        config_path=config_path,
        fallback_client=generator_client,
        fallback_backend=generator_backend,
        fallback_model=generator_model,
        progress_callback=progress_callback,
    )
    plan = assign_tasks(
        question=question,
        plan=plan,
        proposals=proposals,
        client=generator_client,
        model=generator_model,
        snapshot=snapshot,
        progress_callback=progress_callback,
    )
    executions = execute_assigned_tasks(
        question=question,
        plan=plan,
        proposals=proposals,
        snapshot=snapshot,
        defaults=defaults,
        config_path=config_path,
        fallback_client=generator_client,
        fallback_backend=generator_backend,
        fallback_model=generator_model,
        progress_callback=progress_callback,
    )
    objections = build_pairwise_objections(
        question=question,
        plan=plan,
        executions=executions,
        snapshot=snapshot,
        defaults=defaults,
        config_path=config_path,
        fallback_client=generator_client,
        fallback_backend=generator_backend,
        fallback_model=generator_model,
        progress_callback=progress_callback,
    )
    executions = revise_executions(
        question=question,
        plan=plan,
        executions=executions,
        objections=objections,
        proposals=proposals,
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
        proposals=proposals,
        executions=executions,
        objections=objections,
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
            "lines": [
                f"Core 통합 이해: {compact_line(sections.understanding, 240)}",
                f"Core 통합 전략: {compact_line(sections.strategy, 240)}",
                f"Core 통합 결론: {compact_line(sections.conclusion, 240)}",
            ],
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
            "lines": [
                f"Raven 판정: {critique_value(critique, 'verdict', 'NEEDS_MORE_DETAIL')}",
                f"신뢰도: {critique_value(critique, 'confidence', 0.0)}",
                f"치명 오류: {str(critique_value(critique, 'first_fatal_error', '') or '-')}",
            ],
        },
    )
    final_answer = build_final_answer(plan=plan, sections=sections, critique=critique)
    emit_progress(
        progress_callback,
        "final_answer_ready",
        {
            "specialist_name": expert.name,
            "final_answer": final_answer,
            "lines": [
                f"최종 주 전문가: {expert.name}",
                f"최종 결론: {compact_line(sections.conclusion, 240)}",
            ],
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


def emit_progress(progress_callback: ProgressCallback | None, stage: str, payload: dict[str, Any]) -> None:
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
    remote_enabled, remote_backend, remote_model = remote_reasoning_state(fallback_model=fallback_model)
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
    return ResearchPlan(
        specialist=specialist,
        support_specialists=support_specialists,
        reason=reason,
        strategy="",
    )


def plan_question(*, question: str, plan: ResearchPlan, client: LLMClient, model: str) -> ResearchPlan:
    user_prompt = (
        f"Problem:\n{question.strip()}\n\n"
        f"Primary specialist: {plan.specialist}\n"
        f"Support specialists: {', '.join(plan.support_specialists) or '-'}\n"
        f"Routing reason: {plan.reason}\n"
    )
    raw = client.generate_text(model=model, system_prompt=PLANNER_PROMPT, user_prompt=user_prompt)
    payload = parse_json_object(raw)
    strategy = str(payload.get("strategy", "")).strip() or "문제를 분해하고 보수적으로 단계별 추론을 수행한다."
    phases = parse_string_list(payload.get("phases"))
    if not phases:
        phases = ["문제 구조 파악", "필요한 경우 분기", "검산 및 완전성 확인"]
    return ResearchPlan(
        specialist=plan.specialist,
        support_specialists=plan.support_specialists,
        reason=plan.reason,
        strategy=strategy,
        phases=phases,
        critic_summary=plan.critic_summary,
        critic_reviews=plan.critic_reviews,
        handoff_notes=plan.handoff_notes,
        task_assignments=plan.task_assignments,
    )


def run_core_critics(
    *,
    question: str,
    plan: ResearchPlan,
    client: LLMClient,
    model: str,
    progress_callback: ProgressCallback | None,
) -> ResearchPlan:
    critic_specs = [
        (
            "plan",
            "Mystic-CorePlan-Critic",
            "Attack whether the routing and plan are coherent, domain-appropriate, and well sequenced.",
            "plan_critic_complete",
        ),
        (
            "completeness",
            "Mystic-Completeness-Critic",
            "Attack missing cases, unclassified branches, and proof completeness failures.",
            "completeness_critic_complete",
        ),
        (
            "counterexample",
            "Mystic-Counterexample-Critic",
            "Attack the plan by searching for likely counterexamples, boundary cases, and failure modes.",
            "counterexample_critic_complete",
        ),
        (
            "cost_latency",
            "Mystic-Cost-Latency-Critic",
            "Attack the plan from execution cost, redundancy, and latency. Keep quality while reducing wasted work.",
            "cost_latency_critic_complete",
        ),
    ]
    reviews: list[CriticReview] = []
    strategy = plan.strategy
    all_notes: list[str] = []
    for critic_key, critic_name, focus, stage_name in critic_specs:
        prompt = CRITIC_PROMPT_TEMPLATE.format(critic_name=critic_name, focus=focus)
        user_prompt = (
            f"Problem:\n{question.strip()}\n\n"
            f"Primary specialist: {plan.specialist}\n"
            f"Support specialists: {', '.join(plan.support_specialists) or '-'}\n"
            f"Reason: {plan.reason}\n"
            f"Strategy: {strategy}\n"
        )
        raw = client.generate_text(model=model, system_prompt=prompt, user_prompt=user_prompt)
        payload = parse_json_object(raw)
        review = CriticReview(
            critic_key=critic_key,
            critic_name=critic_name,
            summary=str(payload.get("summary", "")).strip() or "요약 없음",
            findings=parse_string_list(payload.get("findings")),
            revision=str(payload.get("revision", "")).strip() or strategy,
        )
        reviews.append(review)
        all_notes.append(f"{critic_name}: {review.summary}")
        if review.revision and review.revision != strategy:
            strategy = review.revision
        emit_progress(
            progress_callback,
            stage_name,
            {
                "critic_name": critic_name,
                "critic_summary": review.summary,
                "findings": review.findings,
                "strategy": strategy,
                "lines": [
                    f"{critic_name} 요약: {review.summary}",
                    *[f"{critic_name} 지적: {item}" for item in review.findings[:3]],
                    f"{critic_name} 반영 전략: {strategy}",
                ],
            },
        )
    return ResearchPlan(
        specialist=plan.specialist,
        support_specialists=plan.support_specialists,
        reason=plan.reason,
        strategy=strategy,
        phases=plan.phases,
        critic_summary=" | ".join(all_notes),
        critic_reviews=reviews,
        handoff_notes=plan.handoff_notes,
        task_assignments=plan.task_assignments,
    )


def build_method_proposals(
    *,
    question: str,
    plan: ResearchPlan,
    selected_agents: list[str],
    snapshot: dict[str, Any],
    defaults: dict[str, Any],
    config_path: str | Path,
    fallback_client: LLMClient,
    fallback_backend: str,
    fallback_model: str,
    progress_callback: ProgressCallback | None,
) -> list[MethodProposal]:
    proposals: list[MethodProposal] = []
    for agent in selected_agents:
        expert = get_expert_snapshot(snapshot, agent)
        backend, model, client = resolve_reasoning_backend(
            agent=agent,
            config_path=config_path,
            defaults=defaults,
            fallback_client=fallback_client,
            fallback_backend=fallback_backend,
            fallback_model=fallback_model,
        )
        user_prompt = (
            f"Problem:\n{question.strip()}\n\n"
            f"Primary specialist: {plan.specialist}\n"
            f"Support specialists: {', '.join(plan.support_specialists) or '-'}\n"
            f"Current strategy: {plan.strategy}\n"
            f"Your specialist: {expert.name} / {expert.agent}\n"
            f"Division: {expert.division}\n"
        )
        raw = client.generate_text(model=model, system_prompt=METHOD_PROPOSAL_PROMPT, user_prompt=user_prompt)
        payload = parse_json_object(raw)
        proposal = MethodProposal(
            agent=agent,
            specialist_name=expert.name,
            method_summary=str(payload.get("method_summary", "")).strip() or f"{expert.name} 관점 분해",
            task_candidate=str(payload.get("task_candidate", "")).strip() or f"{expert.name} 관점 핵심 부분 검토",
            dependencies=parse_string_list(payload.get("dependencies")),
            deliverable=str(payload.get("deliverable", "")).strip() or "국소 결론과 다음 handoff",
            raw_text=raw,
        )
        proposals.append(proposal)
        emit_progress(
            progress_callback,
            "method_proposal_complete",
            {
                "agent": agent,
                "specialist_name": expert.name,
                "backend": backend,
                "model": model,
                "method_summary": proposal.method_summary,
                "task_candidate": proposal.task_candidate,
                "deliverable": proposal.deliverable,
                "lines": [
                    f"{expert.name} backend/model: {backend} / {model}",
                    f"{expert.name} 방법: {proposal.method_summary}",
                    f"{expert.name} 제안 태스크: {proposal.task_candidate}",
                    f"{expert.name} 산출물: {proposal.deliverable}",
                ],
            },
        )
    return proposals


def assign_tasks(
    *,
    question: str,
    plan: ResearchPlan,
    proposals: list[MethodProposal],
    client: LLMClient,
    model: str,
    snapshot: dict[str, Any],
    progress_callback: ProgressCallback | None,
) -> ResearchPlan:
    critic_blocks = "\n".join(
        f"- {review.critic_name}: {review.summary} / {', '.join(review.findings) or '-'} / revision={review.revision}"
        for review in plan.critic_reviews
    )
    proposal_blocks = "\n".join(
        f"- {proposal.agent} ({proposal.specialist_name})\n"
        f"  method={proposal.method_summary}\n"
        f"  task_candidate={proposal.task_candidate}\n"
        f"  dependencies={', '.join(proposal.dependencies) or '-'}\n"
        f"  deliverable={proposal.deliverable}"
        for proposal in proposals
    )
    user_prompt = (
        f"Problem:\n{question.strip()}\n\n"
        f"Primary specialist: {plan.specialist}\n"
        f"Support specialists: {', '.join(plan.support_specialists) or '-'}\n"
        f"Current strategy: {plan.strategy}\n\n"
        f"Core critics:\n{critic_blocks}\n\n"
        f"Method proposals:\n{proposal_blocks}"
    )
    raw = client.generate_text(model=model, system_prompt=TASK_ASSIGNMENT_PROMPT, user_prompt=user_prompt)
    payload = parse_json_object(raw)
    combined_strategy = str(payload.get("combined_strategy", "")).strip() or plan.strategy
    handoff_notes = parse_string_list(payload.get("handoff_notes"))
    assignment_map = {str(item.get("agent", "")).strip().lower(): item for item in ensure_list(payload.get("task_assignments"))}
    assignments: list[TaskAssignment] = []
    for proposal in proposals:
        assignment_payload = assignment_map.get(proposal.agent, {})
        specialist_name = get_expert_snapshot(snapshot, proposal.agent).name
        assignments.append(
            TaskAssignment(
                agent=proposal.agent,
                specialist_name=specialist_name,
                task=str(assignment_payload.get("task", "")).strip() or proposal.task_candidate,
                deliverable=str(assignment_payload.get("deliverable", "")).strip() or proposal.deliverable,
            )
        )
    emit_progress(
        progress_callback,
        "task_assignment_complete",
        {
            "strategy": combined_strategy,
            "handoff_notes": handoff_notes,
            "lines": [
                f"Core 재배분 전략: {combined_strategy}",
                *[f"{assignment.specialist_name} 담당: {assignment.task}" for assignment in assignments],
            ],
        },
    )
    return ResearchPlan(
        specialist=plan.specialist,
        support_specialists=plan.support_specialists,
        reason=plan.reason,
        strategy=combined_strategy,
        phases=plan.phases,
        critic_summary=plan.critic_summary,
        critic_reviews=plan.critic_reviews,
        handoff_notes=handoff_notes,
        task_assignments=assignments,
    )


def execute_assigned_tasks(
    *,
    question: str,
    plan: ResearchPlan,
    proposals: list[MethodProposal],
    snapshot: dict[str, Any],
    defaults: dict[str, Any],
    config_path: str | Path,
    fallback_client: LLMClient,
    fallback_backend: str,
    fallback_model: str,
    progress_callback: ProgressCallback | None,
) -> list[TaskExecution]:
    proposal_map = {proposal.agent: proposal for proposal in proposals}
    executions: list[TaskExecution] = []
    for assignment in plan.task_assignments:
        expert = get_expert_snapshot(snapshot, assignment.agent)
        proposal = proposal_map[assignment.agent]
        backend, model, client = resolve_reasoning_backend(
            agent=assignment.agent,
            config_path=config_path,
            defaults=defaults,
            fallback_client=fallback_client,
            fallback_backend=fallback_backend,
            fallback_model=fallback_model,
        )
        system_prompt = TASK_EXECUTION_PROMPT_TEMPLATE.format(
            specialist_name=expert.name,
            division=expert.division,
            model_name=expert.model,
            adapter_name=expert.adapter,
            dataset_progress=expert.dataset_progress_text,
            status_text=expert.status_text,
            status_detail=expert.status_detail,
            assigned_task=assignment.task,
            deliverable=assignment.deliverable,
            method_summary=proposal.method_summary,
            dependencies=", ".join(proposal.dependencies) or "-",
        )
        user_prompt = (
            f"Problem:\n{question.strip()}\n\n"
            f"Combined strategy:\n{plan.strategy}\n\n"
            f"All selected specialists: {', '.join([plan.specialist, *plan.support_specialists])}\n"
        )
        raw = client.generate_text(model=model, system_prompt=system_prompt, user_prompt=user_prompt)
        sections = parse_sections(raw)
        execution = TaskExecution(
            agent=assignment.agent,
            specialist_name=expert.name,
            assignment=assignment,
            sections=sections,
        )
        executions.append(execution)
        emit_progress(
            progress_callback,
            "task_execution_complete",
            {
                "agent": assignment.agent,
                "specialist_name": expert.name,
                "backend": backend,
                "model": model,
                "task": assignment.task,
                "deliverable": assignment.deliverable,
                "understanding": sections.understanding,
                "strategy": sections.strategy,
                "execution": sections.execution,
                "conclusion": sections.conclusion,
                "uncertainties": sections.uncertainties,
                "lines": [
                    f"{expert.name} backend/model: {backend} / {model}",
                    f"{expert.name} 담당 태스크: {assignment.task}",
                    f"{expert.name} 작업 전략: {compact_line(sections.strategy, 220)}",
                    f"{expert.name} 작업 결론: {compact_line(sections.conclusion, 220)}",
                ],
            },
        )
    return executions


def build_pairwise_objections(
    *,
    question: str,
    plan: ResearchPlan,
    executions: list[TaskExecution],
    snapshot: dict[str, Any],
    defaults: dict[str, Any],
    config_path: str | Path,
    fallback_client: LLMClient,
    fallback_backend: str,
    fallback_model: str,
    progress_callback: ProgressCallback | None,
) -> list[DebateNote]:
    notes: list[DebateNote] = []
    if len(executions) < 2:
        return notes
    for reviewer_execution in executions:
        reviewer = get_expert_snapshot(snapshot, reviewer_execution.agent)
        backend, model, client = resolve_reasoning_backend(
            agent=reviewer_execution.agent,
            config_path=config_path,
            defaults=defaults,
            fallback_client=fallback_client,
            fallback_backend=fallback_backend,
            fallback_model=fallback_model,
        )
        for target_execution in executions:
            if target_execution.agent == reviewer_execution.agent:
                continue
            user_prompt = (
                f"Problem:\n{question.strip()}\n\n"
                f"Combined strategy:\n{plan.strategy}\n\n"
                f"Target specialist: {target_execution.specialist_name} / {target_execution.agent}\n"
                f"Assigned task: {target_execution.assignment.task}\n"
                f"Deliverable: {target_execution.assignment.deliverable}\n"
                f"UNDERSTANDING:\n{target_execution.sections.understanding}\n"
                f"STRATEGY:\n{target_execution.sections.strategy}\n"
                f"EXECUTION:\n{target_execution.sections.execution}\n"
                f"CONCLUSION:\n{target_execution.sections.conclusion}\n"
                f"UNCERTAINTIES:\n{target_execution.sections.uncertainties}\n\n"
                f"Reviewer specialist: {reviewer.name} / {reviewer.agent}"
            )
            raw = client.generate_text(model=model, system_prompt=OBJECTION_PROMPT, user_prompt=user_prompt)
            payload = parse_json_object(raw)
            note = DebateNote(
                reviewer_agent=reviewer_execution.agent,
                reviewer_name=reviewer.name,
                target_agent=target_execution.agent,
                target_name=target_execution.specialist_name,
                objection=str(payload.get("objection", "")).strip() or "구체 objection 없음",
                risk=str(payload.get("risk", "")).strip() or "잠재 위험 설명 없음",
                requested_fix=str(payload.get("requested_fix", "")).strip() or "추가 보완 요청 없음",
                raw_text=raw,
            )
            notes.append(note)
            emit_progress(
                progress_callback,
                "debate_objection_complete",
                {
                    "reviewer_agent": note.reviewer_agent,
                    "reviewer_name": note.reviewer_name,
                    "target_agent": note.target_agent,
                    "target_name": note.target_name,
                    "backend": backend,
                    "model": model,
                    "objection": note.objection,
                    "risk": note.risk,
                    "requested_fix": note.requested_fix,
                    "lines": [
                        f"{note.reviewer_name} -> {note.target_name} objection: {note.objection}",
                        f"위험: {note.risk}",
                        f"수정 요청: {note.requested_fix}",
                    ],
                },
            )
    return notes


def revise_executions(
    *,
    question: str,
    plan: ResearchPlan,
    executions: list[TaskExecution],
    objections: list[DebateNote],
    proposals: list[MethodProposal],
    snapshot: dict[str, Any],
    defaults: dict[str, Any],
    config_path: str | Path,
    fallback_client: LLMClient,
    fallback_backend: str,
    fallback_model: str,
    progress_callback: ProgressCallback | None,
) -> list[TaskExecution]:
    proposal_map = {proposal.agent: proposal for proposal in proposals}
    objection_map: dict[str, list[DebateNote]] = {}
    for note in objections:
        objection_map.setdefault(note.target_agent, []).append(note)
    revised: list[TaskExecution] = []
    for execution in executions:
        received = objection_map.get(execution.agent, [])
        if not received:
            revised.append(execution)
            emit_progress(
                progress_callback,
                "revision_complete",
                {
                    "agent": execution.agent,
                    "specialist_name": execution.specialist_name,
                    "lines": [f"{execution.specialist_name} revision: 수신 objection 없음, 기존 초안 유지"],
                },
            )
            continue
        expert = get_expert_snapshot(snapshot, execution.agent)
        proposal = proposal_map[execution.agent]
        backend, model, client = resolve_reasoning_backend(
            agent=execution.agent,
            config_path=config_path,
            defaults=defaults,
            fallback_client=fallback_client,
            fallback_backend=fallback_backend,
            fallback_model=fallback_model,
        )
        objections_text = "\n".join(
            f"- {note.reviewer_name}: objection={note.objection}; risk={note.risk}; requested_fix={note.requested_fix}"
            for note in received
        )
        system_prompt = REVISION_PROMPT_TEMPLATE.format(
            specialist_name=expert.name,
            assigned_task=execution.assignment.task,
            understanding=execution.sections.understanding,
            strategy=execution.sections.strategy,
            execution=execution.sections.execution,
            conclusion=execution.sections.conclusion,
            uncertainties=execution.sections.uncertainties,
            objections_text=objections_text,
        )
        user_prompt = (
            f"Problem:\n{question.strip()}\n\n"
            f"Combined strategy:\n{plan.strategy}\n\n"
            f"Method proposal:\n{proposal.method_summary}\n"
            f"Expected deliverable:\n{execution.assignment.deliverable}\n"
        )
        raw = client.generate_text(model=model, system_prompt=system_prompt, user_prompt=user_prompt)
        sections = parse_sections(raw)
        revised_execution = TaskExecution(
            agent=execution.agent,
            specialist_name=execution.specialist_name,
            assignment=execution.assignment,
            sections=sections,
        )
        revised.append(revised_execution)
        emit_progress(
            progress_callback,
            "revision_complete",
            {
                "agent": execution.agent,
                "specialist_name": execution.specialist_name,
                "backend": backend,
                "model": model,
                "lines": [
                    f"{execution.specialist_name} revision 반영 수: {len(received)}",
                    f"{execution.specialist_name} 수정 전략: {compact_line(sections.strategy, 220)}",
                    f"{execution.specialist_name} 수정 결론: {compact_line(sections.conclusion, 220)}",
                ],
            },
        )
    return revised


def synthesize_solution(
    *,
    question: str,
    plan: ResearchPlan,
    proposals: list[MethodProposal],
    executions: list[TaskExecution],
    objections: list[DebateNote],
    client: LLMClient,
    model: str,
) -> ResearchSections:
    critic_blocks = "\n".join(
        f"[{review.critic_name}]\nsummary={review.summary}\nfindings={', '.join(review.findings) or '-'}\nrevision={review.revision}"
        for review in plan.critic_reviews
    )
    proposal_blocks = "\n".join(
        f"[{proposal.specialist_name} / {proposal.agent}]\n"
        f"method={proposal.method_summary}\n"
        f"task_candidate={proposal.task_candidate}\n"
        f"dependencies={', '.join(proposal.dependencies) or '-'}\n"
        f"deliverable={proposal.deliverable}"
        for proposal in proposals
    )
    execution_blocks = "\n\n".join(
        f"[{execution.specialist_name} / {execution.agent}]\n"
        f"Assigned task: {execution.assignment.task}\n"
        f"Deliverable: {execution.assignment.deliverable}\n"
        f"UNDERSTANDING:\n{execution.sections.understanding}\n"
        f"STRATEGY:\n{execution.sections.strategy}\n"
        f"EXECUTION:\n{execution.sections.execution}\n"
        f"CONCLUSION:\n{execution.sections.conclusion}\n"
        f"UNCERTAINTIES:\n{execution.sections.uncertainties}"
        for execution in executions
    )
    objection_blocks = "\n".join(
        f"[{note.reviewer_name} -> {note.target_name}] objection={note.objection}; risk={note.risk}; requested_fix={note.requested_fix}"
        for note in objections
    )
    assignment_blocks = "\n".join(
        f"- {assignment.specialist_name} ({assignment.agent}): task={assignment.task}; deliverable={assignment.deliverable}"
        for assignment in plan.task_assignments
    )
    user_prompt = (
        f"Primary specialist: {plan.specialist}\n"
        f"Support specialists: {', '.join(plan.support_specialists) or '-'}\n"
        f"Combined strategy: {plan.strategy}\n"
        f"Handoff notes: {', '.join(plan.handoff_notes) or '-'}\n\n"
        f"Problem:\n{question.strip()}\n\n"
        f"Core critics:\n{critic_blocks}\n\n"
        f"Method proposals:\n{proposal_blocks}\n\n"
        f"Task assignments:\n{assignment_blocks}\n\n"
        f"Revised task results:\n{execution_blocks}\n\n"
        f"Pairwise objections:\n{objection_blocks or '-'}"
    )
    raw = client.generate_text(model=model, system_prompt=SYNTHESIS_PROMPT, user_prompt=user_prompt)
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
        "Core 비평:",
        plan.critic_summary or "-",
        "",
        "태스크 배분:",
        *(
            [f"- {assignment.specialist_name}: {assignment.task}" for assignment in getattr(plan, "task_assignments", [])]
            or ["- 태스크 배분 정보 없음"]
        ),
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
            payload, _ = decoder.raw_decode(stripped[index:])
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
    support = list(defaults.get(specialist, ["logic", "forge", "raven"]))
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


def parse_string_list(raw_value: Any) -> list[str]:
    if isinstance(raw_value, list):
        return [str(item).strip() for item in raw_value if str(item).strip()]
    if isinstance(raw_value, str) and raw_value.strip():
        return [raw_value.strip()]
    return []


def ensure_list(raw_value: Any) -> list[dict[str, Any]]:
    if isinstance(raw_value, list):
        return [item for item in raw_value if isinstance(item, dict)]
    return []


def compact_line(value: str, limit: int = 220) -> str:
    text = " ".join(value.strip().split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"

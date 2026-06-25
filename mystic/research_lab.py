from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from mystic.discord_dashboard import ExpertSnapshot, load_dashboard_snapshot
from mystic.llm_client import LLMClient, build_client, load_model_defaults
from mystic.parsers import parse_raven_output
from mystic.prompts import RAVEN_CRITIC_PROMPT


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "configs" / "models.json"


ROUTER_PROMPT = """You are Mystic-Router.

Choose the single best specialist for the user's math or science reasoning request.
Return JSON only:
{
  "specialist": "prime | algebra | geo | analysis | probability | logic | physics | complexity | biomath | chem | lean | raven | forge | conjecture | pattern | simulator | report | core",
  "reason": "...",
  "strategy": "..."
}

Rules:
- Pick exactly one specialist.
- Prefer a concrete domain specialist over core when possible.
- Use core only when the question is broad or ambiguous.
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

Output plain text with exactly these section headers:
UNDERSTANDING:
STRATEGY:
EXECUTION:
CONCLUSION:
UNCERTAINTIES:
"""


@dataclass(slots=True)
class ResearchPlan:
    specialist: str
    reason: str
    strategy: str


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


def run_research_lab(question: str, *, base_dir: str | Path, config_path: str | Path = DEFAULT_CONFIG_PATH) -> ResearchResult:
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
    expert = get_expert_snapshot(snapshot, plan.specialist)
    sections = solve_question(
        question=question,
        plan=plan,
        expert=expert,
        client=generator_client,
        model=generator_model,
    )
    critique = critique_solution(
        question=question,
        sections=sections,
        client=critic_client,
        backend=critic_backend,
        model=critic_model,
    )
    final_answer = build_final_answer(plan=plan, sections=sections, critique=critique)
    return ResearchResult(
        question=question,
        specialist=plan.specialist,
        specialist_name=expert.name,
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
    reason = str(payload.get("reason", "")).strip() or fallback_reason(specialist)
    strategy = str(payload.get("strategy", "")).strip() or "문제를 분해하고 보수적으로 단계별 추론을 수행한다."
    return ResearchPlan(specialist=specialist, reason=reason, strategy=strategy)


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
    )


def build_final_answer(*, plan: ResearchPlan, sections: ResearchSections, critique: Any) -> str:
    caution_lines: list[str] = []
    verdict = str(critique_value(critique, "verdict", "NEEDS_MORE_DETAIL"))
    first_fatal_error = str(critique_value(critique, "first_fatal_error", "") or "")
    if verdict != "VALID":
        caution_lines.append(f"검증 판정: {verdict}")
        if first_fatal_error:
            caution_lines.append(f"주의: {first_fatal_error}")
    if sections.uncertainties.strip():
        caution_lines.append(f"불확실성: {sections.uncertainties.strip()}")

    lines = [
        f"선택 전문가: {plan.specialist}",
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

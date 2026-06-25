"""Prepare architecture-aligned train_ready datasets from real public raw rows."""

from __future__ import annotations

from collections import defaultdict
from hashlib import md5
import json
from pathlib import Path
import re
from typing import Any

from mystic.training.blueprints import AGENT_DIVISIONS


PUBLIC_AGENT_SOURCES: dict[str, list[str]] = {
    "core": ["numinamath_cot", "openmathinstruct_1", "openmathinstruct_2", "openr1_mixture_of_thoughts", "openthoughts"],
    "prime": ["numinamath_cot", "openmathinstruct_1", "openmathinstruct_2", "openr1_mixture_of_thoughts", "openthoughts"],
    "algebra": ["numinamath_cot", "openmathinstruct_1", "openmathinstruct_2", "openr1_mixture_of_thoughts"],
    "geo": ["numinamath_cot", "openmathinstruct_2", "openr1_mixture_of_thoughts"],
    "analysis": ["numinamath_cot", "openmathinstruct_2", "openr1_mixture_of_thoughts"],
    "probability": ["numinamath_cot", "openmathinstruct_1", "openmathinstruct_2", "openr1_mixture_of_thoughts"],
    "logic": ["proofnet", "leandojo", "lean_github", "openr1_mixture_of_thoughts"],
    "physics": ["openr1_mixture_of_thoughts", "openthoughts", "numinamath_cot"],
    "complexity": ["openthoughts", "openr1_mixture_of_thoughts"],
    "biomath": ["openthoughts", "openr1_mixture_of_thoughts", "numinamath_cot"],
    "chem": ["openthoughts", "openr1_mixture_of_thoughts", "numinamath_cot"],
    "lean": ["proofnet", "leandojo", "lean_github", "openr1_mixture_of_thoughts"],
    "raven": ["proofnet", "numinamath_cot", "openmathinstruct_2", "openr1_mixture_of_thoughts"],
    "forge": ["openthoughts", "openr1_mixture_of_thoughts", "openmathinstruct_2"],
    "conjecture": ["numinamath_cot", "openmathinstruct_2", "openr1_mixture_of_thoughts", "openthoughts"],
    "pattern": ["numinamath_cot", "openmathinstruct_2", "openr1_mixture_of_thoughts", "openthoughts"],
    "simulator": ["openthoughts", "openr1_mixture_of_thoughts", "openmathinstruct_2"],
    "report": ["numinamath_cot", "openmathinstruct_2", "openr1_mixture_of_thoughts", "openthoughts", "proofnet"],
}


SOURCE_PATH_CANDIDATES: dict[str, list[str]] = {
    "numinamath_cot": ["raw/numina_math_cot_100.jsonl", "raw/numinamath_cot/sample.jsonl"],
    "openmathinstruct_1": ["raw/openmathinstruct_1/sample.jsonl"],
    "openmathinstruct_2": ["raw/openmathinstruct_2/sample.jsonl"],
    "openr1_mixture_of_thoughts": ["raw/openr1_mixture_of_thoughts/sample.jsonl"],
    "openthoughts": ["raw/openthoughts/sample.jsonl"],
    "proofnet": ["raw/proofnet/sample.jsonl"],
    "leandojo": ["raw/leandojo/sample.jsonl"],
    "lean_github": ["raw/lean_github/sample.jsonl"],
}


def prepare_public_train_ready_datasets(
    base_dir: str | Path,
    *,
    max_rows_per_agent: int = 300,
    overwrite: bool = False,
    preserve_existing: bool = True,
) -> dict[str, Any]:
    root = Path(base_dir)
    train_ready_root = root / "train_ready"
    eval_root = root / "eval_holdout"
    train_ready_root.mkdir(parents=True, exist_ok=True)
    eval_root.mkdir(parents=True, exist_ok=True)

    rows_by_agent: dict[str, list[dict[str, Any]]] = {}
    fingerprints_by_agent: dict[str, set[str]] = {}
    preserved_counts: dict[str, int] = {}
    added_counts: dict[str, int] = defaultdict(int)
    source_counts: dict[str, int] = defaultdict(int)
    candidates_by_agent: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)

    for agent in sorted(PUBLIC_AGENT_SOURCES):
        path = train_ready_root / f"{agent}_train_ready.jsonl"
        existing_rows = []
        if preserve_existing and path.exists():
            for row in _iter_jsonl(path):
                if overwrite and bool(row.get("metadata", {}).get("bootstrap")):
                    continue
                existing_rows.append(row)
        rows_by_agent[agent] = existing_rows
        fingerprints_by_agent[agent] = {_row_fingerprint(row) for row in existing_rows}
        preserved_counts[agent] = len(existing_rows)

    for source_slug, candidate_paths in SOURCE_PATH_CANDIDATES.items():
        source_path = _first_existing(root, candidate_paths)
        if source_path is None:
            continue
        source_rows_added = 0
        for raw_row in _iter_jsonl(source_path):
            normalized = _normalize_public_row(source_slug, raw_row)
            if normalized is None:
                continue
            for agent, allowed_sources in PUBLIC_AGENT_SOURCES.items():
                if source_slug not in allowed_sources:
                    continue
                for row in _to_train_ready_rows(agent, source_slug, normalized):
                    fingerprint = _row_fingerprint(row)
                    if fingerprint in fingerprints_by_agent[agent]:
                        continue
                    fingerprints_by_agent[agent].add(fingerprint)
                    candidates_by_agent[agent].append((int(row["metadata"].get("quality_score", 0)), row))
                    source_rows_added += 1
        source_counts[source_slug] = source_rows_added

    for agent, candidates in candidates_by_agent.items():
        candidates.sort(key=lambda item: item[0], reverse=True)
        remaining = max(max_rows_per_agent - len(rows_by_agent[agent]), 0)
        for _, row in candidates[:remaining]:
            rows_by_agent[agent].append(row)
            added_counts[agent] += 1

    split_buckets: dict[str, list[dict[str, Any]]] = {"train": [], "validation": [], "test": []}
    written_files: list[str] = []
    final_counts: dict[str, int] = {}
    for agent, rows in rows_by_agent.items():
        for row in rows:
            row["metadata"]["split"] = _split_for_row(row)
        path = train_ready_root / f"{agent}_train_ready.jsonl"
        _write_jsonl(path, rows)
        written_files.append(str(path))
        final_counts[agent] = len(rows)
        for row in rows:
            split_buckets[str(row["metadata"]["split"])].append(row)

    train_path = train_ready_root / "train.jsonl"
    validation_path = eval_root / "validation.jsonl"
    test_path = eval_root / "test.jsonl"
    _write_jsonl(train_path, split_buckets["train"])
    _write_jsonl(validation_path, split_buckets["validation"])
    _write_jsonl(test_path, split_buckets["test"])

    return {
        "written_files": written_files,
        "split_files": [str(train_path), str(validation_path), str(test_path)],
        "preserved_counts": preserved_counts,
        "added_counts": dict(added_counts),
        "final_counts": final_counts,
        "source_counts": dict(source_counts),
        "max_rows_per_agent": max_rows_per_agent,
        "overwrite": overwrite,
    }


def _first_existing(root: Path, candidates: list[str]) -> Path | None:
    for candidate in candidates:
        path = root / candidate
        if path.exists():
            return path
    return None


def _normalize_public_row(source_slug: str, row: dict[str, Any]) -> dict[str, str] | None:
    problem = _clean_text(
        _first_nonempty(
            row,
            ["problem", "question", "instruction", "input", "prompt"],
        )
        or _conversation_text(row, role="user")
        or _messages_text(row, role="user")
    )
    solution = _clean_text(
        _first_nonempty(
            row,
            ["solution", "generated_solution", "output", "response", "answer", "expected_answer"],
        )
        or _first_generation(row)
        or _conversation_text(row, role="assistant")
        or _messages_text(row, role="assistant")
    )
    if not problem or not solution:
        return None
    quality_score = _quality_score(problem, solution)
    if quality_score < 4:
        return None
    return {
        "problem": problem,
        "solution": solution,
        "source_slug": source_slug,
        "quality_score": str(quality_score),
    }


def _first_nonempty(row: dict[str, Any], keys: list[str]) -> str | None:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _messages_text(row: dict[str, Any], *, role: str) -> str | None:
    messages = row.get("messages")
    if not isinstance(messages, list):
        return None
    for message in messages:
        if not isinstance(message, dict):
            continue
        if str(message.get("role", "")).lower() != role:
            continue
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content
    return None


def _conversation_text(row: dict[str, Any], *, role: str) -> str | None:
    conversations = row.get("conversations")
    if not isinstance(conversations, list):
        return None
    aliases = {
        "user": {"user", "human"},
        "assistant": {"assistant", "gpt", "model"},
    }
    expected = aliases[role]
    for item in conversations:
        if not isinstance(item, dict):
            continue
        sender = str(item.get("from", "")).lower()
        if sender not in expected:
            continue
        value = item.get("value")
        if isinstance(value, str) and value.strip():
            return value
    return None


def _first_generation(row: dict[str, Any]) -> str | None:
    generations = row.get("generations")
    if not isinstance(generations, list):
        return None
    for item in generations:
        if isinstance(item, str) and item.strip():
            return item
    return None


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return str(value).strip()


def _quality_score(problem: str, solution: str) -> int:
    score = 0
    combined = f"{problem}\n{solution}".lower()
    if len(problem) >= 24:
        score += 2
    if len(solution) >= 24:
        score += 2
    if len(solution.split()) >= 8:
        score += 1
    if re.search(r"[0-9=+\-*/^]|\\frac|\\sum|\\int|prime|proof|theorem|lemma|probab|matrix|limit|integral", combined):
        score += 1
    if any(token in combined for token in ["sorry", "as an ai", "i can't", "cannot help", "not sure"]):
        score -= 4
    return score


def _to_train_ready_rows(agent: str, source_slug: str, normalized: dict[str, str]) -> list[dict[str, Any]]:
    quality_score = int(normalized.get("quality_score", "0") or 0)
    if agent != "core":
        return [
            {
                "agent": agent,
                "division": AGENT_DIVISIONS.get(agent, "unknown"),
                "instruction": _instruction_for_agent(agent),
                "input": (
                    f"Dataset source: {source_slug}\n"
                    f"Problem:\n{normalized['problem']}"
                ),
                "output": _output_for_agent(agent, normalized["solution"]),
                "status": "PUBLIC_REAL",
                "metadata": {
                    "dataset": source_slug,
                    "split": "train",
                    "source_type": "public_real",
                    "target_agent": agent,
                    "bootstrap": False,
                    "quality_score": quality_score,
                    "curation": "quality_filtered_public",
                },
            }
        ]

    specialist = _router_specialist(normalized["problem"])
    support_specialists = _router_support_specialists(specialist)
    return [
        {
            "agent": "core",
            "division": AGENT_DIVISIONS.get("core", "unknown"),
            "instruction": "Select the best primary specialist and support specialists. Return JSON with specialist, support_specialists, reason.",
            "input": f"Dataset source: {source_slug}\nProblem:\n{normalized['problem']}",
            "output": json.dumps(
                {
                    "specialist": specialist,
                    "support_specialists": support_specialists,
                    "reason": _router_reason(specialist),
                },
                ensure_ascii=True,
            ),
            "status": "PUBLIC_REAL",
            "metadata": {
                "dataset": source_slug,
                "split": "train",
                "source_type": "public_real",
                "target_agent": "core",
                "bootstrap": False,
                "quality_score": quality_score,
                "curation": "quality_filtered_public",
                "role_variant": "router",
            },
        },
        {
            "agent": "core",
            "division": AGENT_DIVISIONS.get("core", "unknown"),
            "instruction": "Write the first executable solving strategy. Return JSON with strategy and phases.",
            "input": (
                f"Dataset source: {source_slug}\n"
                f"Primary specialist: {specialist}\n"
                f"Support specialists: {', '.join(support_specialists)}\n"
                f"Problem:\n{normalized['problem']}"
            ),
            "output": json.dumps(
                {
                    "strategy": _planner_strategy(specialist),
                    "phases": _planner_phases(normalized["problem"]),
                },
                ensure_ascii=True,
            ),
            "status": "PUBLIC_REAL",
            "metadata": {
                "dataset": source_slug,
                "split": "train",
                "source_type": "public_real",
                "target_agent": "core",
                "bootstrap": False,
                "quality_score": quality_score,
                "curation": "quality_filtered_public",
                "role_variant": "planner",
            },
        },
    ]


def _router_specialist(problem: str) -> str:
    lowered = problem.lower()
    keyword_map = [
        ("triangle", "geo"),
        ("geometry", "geo"),
        ("probability", "probability"),
        ("random", "probability"),
        ("integral", "analysis"),
        ("limit", "analysis"),
        ("matrix", "algebra"),
        ("equation", "algebra"),
        ("logic", "logic"),
        ("contradiction", "logic"),
        ("physics", "physics"),
        ("velocity", "physics"),
        ("chem", "chem"),
        ("molecule", "chem"),
        ("biology", "biomath"),
        ("gene", "biomath"),
        ("prime", "prime"),
        ("integer", "prime"),
        ("proof", "prime"),
    ]
    for keyword, agent in keyword_map:
        if keyword in lowered:
            return agent
    return "core"


def _router_support_specialists(specialist: str) -> list[str]:
    defaults = {
        "prime": ["logic", "pattern", "forge", "raven"],
        "algebra": ["logic", "analysis", "forge", "raven"],
        "geo": ["analysis", "logic", "forge", "raven"],
        "analysis": ["algebra", "logic", "forge", "raven"],
        "probability": ["analysis", "logic", "simulator", "raven"],
        "logic": ["prime", "forge", "raven"],
        "physics": ["analysis", "simulator", "forge", "raven"],
        "chem": ["analysis", "simulator", "forge", "raven"],
        "biomath": ["analysis", "simulator", "forge", "raven"],
        "core": ["logic", "pattern", "forge", "raven"],
    }
    return defaults.get(specialist, ["logic", "forge", "raven"])


def _router_reason(specialist: str) -> str:
    reasons = {
        "prime": "정수 조건과 증명 분기가 중심이라 prime이 주도한다.",
        "algebra": "대수 변형과 기호 조작 비중이 커서 algebra가 주도한다.",
        "geo": "기하 구조와 도형 불변량이 핵심이라 geo가 주도한다.",
        "analysis": "극한/부등식 해석이 핵심이라 analysis가 주도한다.",
        "probability": "확률 구조와 사건 분해가 핵심이라 probability가 주도한다.",
        "logic": "논리 구조와 추론 위생이 핵심이라 logic이 주도한다.",
        "physics": "물리 제약과 수식 해석이 핵심이라 physics가 주도한다.",
        "chem": "화학적 제약과 수량 관계가 중요해 chem이 주도한다.",
        "biomath": "정량 생물학 가정이 핵심이라 biomath가 주도한다.",
        "core": "문제가 넓거나 혼합형이라 core가 오케스트레이션한다.",
    }
    return reasons.get(specialist, "도메인 단서를 기준으로 specialist를 선택했다.")


def _planner_strategy(specialist: str) -> str:
    strategies = {
        "prime": "정수 조건과 상한/하한을 먼저 잡고 분기별로 닫는다.",
        "algebra": "표현식을 정리하고 핵심 대수 변환을 분기별로 검증한다.",
        "geo": "도형 구조를 재구성하고 보조정리와 불변량을 정리한다.",
        "analysis": "정의역과 극한/부등식 구조를 먼저 고정한 뒤 세부 증명으로 간다.",
        "probability": "확률 공간과 사건 분해를 먼저 정의하고 계산을 닫는다.",
        "logic": "가정, 결론, 추론 단계의 누락 여부를 먼저 정리한다.",
        "physics": "변수, 단위, 보존 법칙, 경계조건 순으로 검증한다.",
        "chem": "화학 제약과 수량 관계를 먼저 정리한 뒤 계산을 수행한다.",
        "biomath": "모형 가정과 정량 관계를 먼저 명시하고 계산을 진행한다.",
        "core": "문제를 분해하고 specialist별 태스크를 배분한 뒤 검증으로 닫는다.",
    }
    return strategies.get(specialist, "핵심 구조를 먼저 분해하고 분기별로 검증한다.")


def _planner_phases(problem: str) -> list[str]:
    lowered = problem.lower()
    if "all" in lowered or "classify" in lowered or "integer" in lowered or "positive integer" in lowered:
        return ["범위 제한", "경우 분기", "후보 검산", "완전성 확인"]
    if "prove" in lowered or "theorem" in lowered or "lemma" in lowered:
        return ["핵심 보조정리 식별", "주 논증 전개", "반례/누락 점검", "결론 정리"]
    return ["문제 구조 파악", "핵심 단계 분해", "검산 및 반례 점검", "결론 정리"]


def _instruction_for_agent(agent: str) -> str:
    instructions = {
        "core": "Route and summarize the problem with explicit decomposition into specialist work.",
        "prime": "Solve the problem as a rigorous number-theory and olympiad-style math specialist.",
        "algebra": "Produce a symbolic algebra solution with explicit transformations.",
        "geo": "Reframe the task as a geometry specialist and expose construction or invariant steps.",
        "analysis": "Produce an analysis-focused derivation with clear inequality or limit logic.",
        "probability": "Solve with explicit probabilistic objects, conditioning, and expectation logic.",
        "logic": "Check the proof structure and rewrite it as a logic-specialist derivation.",
        "physics": "Translate the reasoning into physics-style mathematical derivation and constraint tracking.",
        "complexity": "Rewrite the reasoning as an algorithmic or complexity-oriented analysis.",
        "biomath": "Rewrite the reasoning as a quantitative biomath derivation with explicit assumptions.",
        "chem": "Rewrite the reasoning as chemistry-aware symbolic reasoning and derivation.",
        "lean": "Reframe the problem toward formal proof or tactic-oriented reasoning.",
        "raven": "Critique or validate the reasoning conservatively and expose failure points if any.",
        "forge": "Turn the problem into an experiment or code-oriented reasoning plan.",
        "conjecture": "Extract a conjecture, helpful lemma, or attack direction from the problem.",
        "pattern": "Expose invariants, recurrence patterns, or modular structure suggested by the problem.",
        "simulator": "Sketch how a simulator or computational test could support the claim.",
        "report": "Summarize the problem and solution into a clean uncertainty-preserving report.",
    }
    return instructions.get(agent, f"Produce a specialist response for {agent}.")


def _output_for_agent(agent: str, solution: str) -> str:
    if agent == "raven":
        return (
            '{"verdict":"NEEDS_MORE_DETAIL","first_fatal_error":"","missing_assumptions":[],'
            '"invalid_steps":[],"valid_steps":["Reference solution available from public dataset."],'
            f'"repair_possible":true,"confidence":0.35,"final_status":"Review reference solution carefully before acceptance."}}\n\nReference solution:\n{solution}'
        )
    if agent == "forge":
        return f"Experiment plan derived from the reference solution:\n\n{solution}"
    if agent == "simulator":
        return f"Simulation-oriented sketch derived from the reference solution:\n\n{solution}"
    if agent == "report":
        return f"Report-ready summary and answer:\n\n{solution}"
    return solution


def _row_fingerprint(row: dict[str, Any]) -> str:
    payload = f"{row.get('agent')}|{row.get('instruction')}|{row.get('input')}|{row.get('output')}"
    return md5(payload.encode("utf-8")).hexdigest()


def _split_for_row(row: dict[str, Any]) -> str:
    fingerprint = _row_fingerprint(row)
    bucket = int(fingerprint, 16) % 10
    if bucket == 0:
        return "test"
    if bucket == 1:
        return "validation"
    return "train"


def _iter_jsonl(path: Path):
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            yield json.loads(stripped)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    payload = "\n".join(json.dumps(row, ensure_ascii=True) for row in rows)
    if payload:
        payload += "\n"
    path.write_text(payload, encoding="utf-8")

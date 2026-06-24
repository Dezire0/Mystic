"""Shared protocol objects for Mystic agents and sessions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


ALLOWED_STATUSES = {
    "PROVED",
    "FORMALIZED",
    "HEURISTIC",
    "GAP",
    "REFUTED",
    "UNKNOWN",
    "PROMISING",
    "DEAD_END",
}


@dataclass(slots=True)
class ModelSettings:
    provider: str
    model: str
    temperature: float | None = None
    adapter: str | None = None


@dataclass(slots=True)
class ProviderResponse:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AgentOutput:
    agent: str
    division: str
    claim: str
    status: str
    reasoning: str
    dependencies: list[str]
    obstruction: str
    experiment: str
    formalization: str
    next_move: str
    raw_response: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in ALLOWED_STATUSES:
            raise ValueError(f"Unsupported status: {self.status}")

    def to_structured_dict(self) -> dict[str, Any]:
        return {
            "CLAIM": self.claim,
            "STATUS": self.status,
            "DOMAIN": self.division,
            "REASONING": self.reasoning,
            "DEPENDENCIES": self.dependencies,
            "OBSTRUCTION": self.obstruction,
            "EXPERIMENT": self.experiment,
            "FORMALIZATION": self.formalization,
            "NEXT_MOVE": self.next_move,
        }

    def to_archive_text(self) -> str:
        payload = self.to_structured_dict()
        return "\n".join(f"{key}: {value}" for key, value in payload.items())


@dataclass(slots=True)
class CorePlan:
    problem_restatement: str
    formal_statement: str
    domain_classification: list[str]
    subproblems: list[str]
    agents_to_call: list[str]
    initial_strategy: str
    risk_factors: list[str]
    success_criteria: list[str]
    raw_response: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "PROBLEM_RESTATEMENT": self.problem_restatement,
            "FORMAL_STATEMENT": self.formal_statement,
            "DOMAIN_CLASSIFICATION": self.domain_classification,
            "SUBPROBLEMS": self.subproblems,
            "AGENTS_TO_CALL": self.agents_to_call,
            "INITIAL_STRATEGY": self.initial_strategy,
            "RISK_FACTORS": self.risk_factors,
            "SUCCESS_CRITERIA": self.success_criteria,
        }

    def to_archive_text(self) -> str:
        return "\n".join(f"{key}: {value}" for key, value in self.to_dict().items())


@dataclass(slots=True)
class PythonExecutionResult:
    success: bool
    returncode: int
    stdout: str
    stderr: str
    timeout: bool = False
    blocked: bool = False
    blocked_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SessionRunResult:
    session_id: str
    core_plan: CorePlan
    selected_agents: list[str]
    agent_outputs: list[AgentOutput]
    report_text: str
    export_paths: list[str]


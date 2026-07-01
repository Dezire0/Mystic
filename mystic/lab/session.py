from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
import uuid

from mystic.lab.schema import (
    LAB_AGENT_ROLES,
    LAB_CLAIM_STATUSES,
    LAB_CLAIM_TYPES,
    LAB_DOMAINS,
    LAB_EXPERIMENT_METHODS,
    LAB_EXPERIMENT_VERDICTS,
    LAB_FAILURE_TYPES,
    LAB_MEMORY_RELATIONS,
    LAB_PHASES,
    LAB_SESSION_MODES,
    LAB_SESSION_STATUSES,
    LAB_TURN_STATUSES,
    PHASE_TO_ROOM,
    utc_now_iso,
    validate_choice,
)


@dataclass(slots=True)
class LabSession:
    session_id: str
    problem: str
    domain: str
    goal: str
    mode: str
    status: str = "created"
    current_phase: str = "problem_intake"
    active_room: str = field(default_factory=lambda: PHASE_TO_ROOM["problem_intake"])
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    controller: dict[str, Any] = field(default_factory=dict)
    participants: list[dict[str, Any]] = field(default_factory=list)
    artifact_paths: dict[str, str] = field(default_factory=dict)
    next_actions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        validate_choice("domain", self.domain, LAB_DOMAINS)
        validate_choice("mode", self.mode, LAB_SESSION_MODES)
        validate_choice("status", self.status, LAB_SESSION_STATUSES)
        validate_choice("current_phase", self.current_phase, set(LAB_PHASES))

    def touch(self) -> None:
        self.updated_at = utc_now_iso()
        self.active_room = PHASE_TO_ROOM.get(self.current_phase, self.active_room)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LabTurn:
    session_id: str
    phase: str
    room: str
    agent_role: str
    provider: str
    model_name: str
    input_summary: str
    output: str
    extracted_claims: list[dict[str, Any]] = field(default_factory=list)
    requested_tools: list[str] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    status: str = "completed"
    error: str = ""
    reply_to: list[str] = field(default_factory=list)
    turn_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        validate_choice("phase", self.phase, set(LAB_PHASES))
        validate_choice("agent_role", self.agent_role, LAB_AGENT_ROLES)
        validate_choice("status", self.status, LAB_TURN_STATUSES)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Claim:
    session_id: str
    text: str
    claim_type: str
    status: str
    confidence: str
    source_turn_id: str
    supporting_evidence: list[str] = field(default_factory=list)
    refuting_evidence: list[str] = field(default_factory=list)
    related_experiments: list[str] = field(default_factory=list)
    related_failures: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    claim_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        validate_choice("claim_type", self.claim_type, LAB_CLAIM_TYPES)
        validate_choice("status", self.status, LAB_CLAIM_STATUSES)

    def touch(self) -> None:
        self.updated_at = utc_now_iso()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Experiment:
    session_id: str
    claim_id: str
    question: str
    method: str
    inputs: dict[str, Any]
    outputs: dict[str, Any] = field(default_factory=dict)
    tool_name: str = ""
    verdict: str = "inconclusive"
    evidence_summary: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    experiment_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        validate_choice("method", self.method, LAB_EXPERIMENT_METHODS)
        validate_choice("verdict", self.verdict, LAB_EXPERIMENT_VERDICTS)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Failure:
    session_id: str
    claim_id: str
    source_turn_id: str
    first_fatal_error: str
    failure_type: str
    lesson: str
    reusable_as_training_data: bool
    created_at: str = field(default_factory=utc_now_iso)
    failure_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        validate_choice("failure_type", self.failure_type, LAB_FAILURE_TYPES)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MemoryEdge:
    session_id: str
    from_id: str
    to_id: str
    relation: str
    evidence: str
    created_at: str = field(default_factory=utc_now_iso)
    edge_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        validate_choice("relation", self.relation, LAB_MEMORY_RELATIONS)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LabReport:
    session_id: str
    title: str
    problem: str
    domain: str
    surviving_claims: list[dict[str, Any]]
    failed_claims: list[dict[str, Any]]
    experiments: list[dict[str, Any]]
    key_lessons: list[str]
    next_actions: list[str]
    markdown: str
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LabSessionBundle:
    session: LabSession
    turns: list[LabTurn] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    experiments: list[Experiment] = field(default_factory=list)
    failures: list[Failure] = field(default_factory=list)
    memory_edges: list[MemoryEdge] = field(default_factory=list)
    notebook_markdown: str = ""
    report_markdown: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "session": self.session.to_dict(),
            "turns": [item.to_dict() for item in self.turns],
            "claims": [item.to_dict() for item in self.claims],
            "experiments": [item.to_dict() for item in self.experiments],
            "failures": [item.to_dict() for item in self.failures],
            "memory_edges": [item.to_dict() for item in self.memory_edges],
            "notebook_markdown": self.notebook_markdown,
            "report_markdown": self.report_markdown,
        }


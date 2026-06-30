from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any
import uuid


@dataclass(slots=True)
class ResearchTurn:
    session_id: str
    round_index: int
    phase: str
    speaker_type: str
    speaker_id: str
    provider: str
    model_name: str
    role: str
    status: str
    content: str
    reply_to: list[str] = field(default_factory=list)
    summary: str = ""
    claims: list[str] = field(default_factory=list)
    candidate_answers: list[str] = field(default_factory=list)
    discoveries: list[dict[str, Any]] = field(default_factory=list)
    verification_requests: list[dict[str, Any]] = field(default_factory=list)
    latency_sec: float = 0.0
    artifact_path: str = ""
    target_discovery_id: str = ""
    verification_request_id: str = ""
    turn_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ResearchTableSession:
    session_id: str
    problem: str
    participants: list[str]
    mode: str
    requested_rounds: int
    participant_models: list[dict[str, Any]] = field(default_factory=list)
    controller: dict[str, Any] = field(default_factory=dict)
    turns: list[dict[str, Any]] = field(default_factory=list)
    discoveries: list[dict[str, Any]] = field(default_factory=list)
    verification_requests: list[dict[str, Any]] = field(default_factory=list)
    accepted_discoveries: list[dict[str, Any]] = field(default_factory=list)
    rejected_discoveries: list[dict[str, Any]] = field(default_factory=list)
    verification: dict[str, Any] | None = None
    final_status: str = "MODEL_OUTPUTS_ONLY"
    final_decision_source: str = "model_outputs"
    final_synthesis_package: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["rounds"] = len({(turn["round_index"], turn["phase"]) for turn in self.turns})
        return payload

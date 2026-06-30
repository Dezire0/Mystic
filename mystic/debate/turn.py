from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any
import uuid


@dataclass(slots=True)
class DebateTurn:
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
    turn_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any
import uuid


@dataclass(slots=True)
class DebateSession:
    problem: str
    participants: list[dict[str, Any]]
    rounds: int
    tools: list[str]
    judge: str
    max_turns: int
    session_id: str = field(default_factory=lambda: f"debate-{uuid.uuid4().hex[:10]}")
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

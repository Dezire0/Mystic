from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
import uuid


@dataclass(slots=True)
class DiscoveryItem:
    claim: str
    rationale: str
    confidence: str
    needs_verification: bool
    source_turn_id: str
    type: str = "strategy"
    status: str = "proposed"
    discovery_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class VerificationRequest:
    target_discovery_id: str
    tool: str
    question: str
    status: str = "pending"
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EngineError(Exception):
    code: str
    message: str
    retryable: bool = False

    def safe_payload(self) -> dict[str, object]:
        return {"code": self.code, "message": self.message, "retryable": self.retryable, "next_action": "Correct the input or select another available engine."}

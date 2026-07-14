from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from .manifest import EngineManifest


@dataclass(frozen=True)
class ResourceEstimate:
    resource_class: str
    expected_seconds: float
    output_bytes_max: int = 262_144


@dataclass
class EngineExecutionContext:
    run_id: str
    seed: int | None = None
    cancelled: callable | None = None
    progress: callable | None = None
    resource_limits: dict[str, Any] = field(default_factory=dict)

    def check_cancelled(self) -> None:
        if self.cancelled and self.cancelled():
            from .errors import EngineError
            raise EngineError("engine_cancelled", "The engine job was cancelled.")


@dataclass
class EngineResult:
    summary: dict[str, Any]
    values: dict[str, Any]
    series: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    units: dict[str, str] = field(default_factory=dict)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    visualization: dict[str, Any] | None = None
    evidence: list[dict[str, Any]] = field(default_factory=list)


class ScientificEnginePlugin(ABC):
    @abstractmethod
    def manifest(self) -> EngineManifest: ...
    @abstractmethod
    def validate_input(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    @abstractmethod
    def estimate(self, payload: dict[str, Any]) -> ResourceEstimate: ...
    @abstractmethod
    def execute(self, payload: dict[str, Any], context: EngineExecutionContext) -> EngineResult: ...

    def summarize(self, result: EngineResult) -> dict[str, Any]:
        return result.summary

    def build_visualization(self, result: EngineResult) -> dict[str, Any] | None:
        return result.visualization

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


ResourceClass = Literal["tiny", "small", "medium", "large", "external_required"]


@dataclass(frozen=True)
class EngineManifest:
    engine_id: str
    display_name: str
    version: str
    domain: str
    description: str
    capabilities: tuple[str, ...]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    deterministic: bool
    supports_seed: bool
    supports_progress: bool
    supports_cancel: bool
    supports_visualization: bool
    execution_backend: str = "trusted_python_runner"
    expected_resource_class: ResourceClass = "tiny"
    timeout_seconds_default: int = 5
    timeout_seconds_max: int = 30
    artifact_types: tuple[str, ...] = ()
    safety_classification: str = "bounded_scientific_model"
    enabled: bool = True
    deprecated: bool = False
    metadata_safe: dict[str, Any] = field(default_factory=dict)

    def public_dict(self) -> dict[str, Any]:
        return asdict(self) | {"capabilities": list(self.capabilities), "artifact_types": list(self.artifact_types)}

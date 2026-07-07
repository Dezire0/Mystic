from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
import uuid

from mystic.lab.schema import (
    LAB_DOMAINS,
    LAB_ENGINE_ADAPTERS,
    LAB_SIMULATION_STATUSES,
    utc_now_iso,
    validate_choice,
)


def _coerce_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _coerce_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _coerce_float(value: Any, default: float) -> float:
    if isinstance(value, bool):
        return float(default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def normalize_vector(value: Any, *, default: tuple[float, float, float]) -> dict[str, float]:
    payload = _coerce_mapping(value)
    return {
        "x": _coerce_float(payload.get("x"), default[0]),
        "y": _coerce_float(payload.get("y"), default[1]),
        "z": _coerce_float(payload.get("z"), default[2]),
    }


def normalize_scene_object_payload(payload: dict[str, Any], *, scene_id: str) -> dict[str, Any]:
    object_id = str(payload.get("id", "")).strip() or f"obj-{uuid.uuid4().hex[:12]}"
    object_type = str(payload.get("type", "")).strip()
    label = str(payload.get("label", "")).strip() or object_type or object_id
    if not object_type:
        raise ValueError("scene object type is required")
    return {
        "scene_id": scene_id,
        "id": object_id,
        "type": object_type,
        "label": label,
        "position": normalize_vector(payload.get("position"), default=(0.0, 0.0, 0.0)),
        "rotation": normalize_vector(payload.get("rotation"), default=(0.0, 0.0, 0.0)),
        "scale": normalize_vector(payload.get("scale"), default=(1.0, 1.0, 1.0)),
        "geometry": _coerce_mapping(payload.get("geometry")),
        "material": _coerce_mapping(payload.get("material")),
        "data": _coerce_mapping(payload.get("data")),
        "metadata": _coerce_mapping(payload.get("metadata")),
    }


@dataclass(slots=True)
class LabScene:
    scene_id: str
    session_id: str
    domain: str
    title: str
    description: str = ""
    units: dict[str, Any] = field(default_factory=dict)
    parameters: dict[str, Any] = field(default_factory=dict)
    attached_simulations: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    report_refs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    artifact_paths: dict[str, str] = field(default_factory=dict)
    exports_json: dict[str, Any] = field(default_factory=dict)
    report_markdown: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        validate_choice("domain", self.domain, LAB_DOMAINS)
        self.units = _coerce_mapping(self.units)
        self.parameters = _coerce_mapping(self.parameters)
        self.attached_simulations = _coerce_list(self.attached_simulations)
        self.evidence_refs = _coerce_list(self.evidence_refs)
        self.report_refs = _coerce_list(self.report_refs)
        self.metadata = _coerce_mapping(self.metadata)
        self.artifact_paths = {str(key): str(value) for key, value in _coerce_mapping(self.artifact_paths).items()}
        self.exports_json = _coerce_mapping(self.exports_json)
        self.title = str(self.title).strip()
        self.description = str(self.description)
        if not self.title:
            raise ValueError("scene title is required")

    def touch(self) -> None:
        self.updated_at = utc_now_iso()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LabSceneObject:
    scene_id: str
    id: str
    type: str
    label: str
    position: dict[str, float] = field(default_factory=lambda: normalize_vector({}, default=(0.0, 0.0, 0.0)))
    rotation: dict[str, float] = field(default_factory=lambda: normalize_vector({}, default=(0.0, 0.0, 0.0)))
    scale: dict[str, float] = field(default_factory=lambda: normalize_vector({}, default=(1.0, 1.0, 1.0)))
    geometry: dict[str, Any] = field(default_factory=dict)
    material: dict[str, Any] = field(default_factory=dict)
    data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        self.scene_id = str(self.scene_id).strip()
        self.id = str(self.id).strip()
        self.type = str(self.type).strip()
        self.label = str(self.label).strip()
        if not self.scene_id:
            raise ValueError("scene_id is required")
        if not self.id:
            raise ValueError("object id is required")
        if not self.type:
            raise ValueError("object type is required")
        if not self.label:
            raise ValueError("object label is required")
        self.position = normalize_vector(self.position, default=(0.0, 0.0, 0.0))
        self.rotation = normalize_vector(self.rotation, default=(0.0, 0.0, 0.0))
        self.scale = normalize_vector(self.scale, default=(1.0, 1.0, 1.0))
        self.geometry = _coerce_mapping(self.geometry)
        self.material = _coerce_mapping(self.material)
        self.data = _coerce_mapping(self.data)
        self.metadata = _coerce_mapping(self.metadata)

    def touch(self) -> None:
        self.updated_at = utc_now_iso()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LabSimulation:
    simulation_id: str
    scene_id: str
    session_id: str
    adapter_id: str
    status: str
    inputs: dict[str, Any]
    outputs: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    attached_object_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        validate_choice("adapter_id", self.adapter_id, LAB_ENGINE_ADAPTERS)
        validate_choice("status", self.status, LAB_SIMULATION_STATUSES)
        self.inputs = _coerce_mapping(self.inputs)
        self.outputs = _coerce_mapping(self.outputs)
        self.evidence = _coerce_mapping(self.evidence)
        self.warnings = _coerce_list(self.warnings)
        self.errors = _coerce_list(self.errors)
        self.attached_object_ids = _coerce_list(self.attached_object_ids)
        self.metadata = _coerce_mapping(self.metadata)

    def touch(self) -> None:
        self.updated_at = utc_now_iso()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LabSceneBundle:
    scene: LabScene
    objects: list[LabSceneObject] = field(default_factory=list)
    simulations: list[LabSimulation] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene": self.scene.to_dict(),
            "objects": [item.to_dict() for item in self.objects],
            "simulations": [item.to_dict() for item in self.simulations],
        }

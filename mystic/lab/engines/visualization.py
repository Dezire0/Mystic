from __future__ import annotations

from typing import Any

from .errors import EngineError


SUPPORTED_LAYER_TYPES = frozenset({"point", "point_set", "line", "polyline", "trajectory", "vector", "vector_field", "scalar_label", "time_series_link", "object_state", "heatmap_points", "graph_network"})


def validate_visualization(descriptor: dict[str, Any] | None) -> dict[str, Any] | None:
    if descriptor is None:
        return None
    if not isinstance(descriptor, dict) or descriptor.get("version") != "1" or not isinstance(descriptor.get("layers"), list):
        raise EngineError("engine_output_invalid", "Visualization descriptor must be version 1 with a layers array.")
    for layer in descriptor["layers"]:
        if not isinstance(layer, dict) or not isinstance(layer.get("id"), str) or layer.get("type") not in SUPPORTED_LAYER_TYPES:
            raise EngineError("engine_output_invalid", "Visualization layer is invalid or unsupported.")
        if not isinstance(layer.get("data", {}), dict):
            raise EngineError("engine_output_invalid", "Visualization layer data must be an object.")
    return descriptor
